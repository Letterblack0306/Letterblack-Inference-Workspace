from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .gguf import GgufError, parse_gguf_header


class RuntimeFailure(RuntimeError):
    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


def tcp_probe(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"reachable": True, "latencyMs": round((time.monotonic()-started)*1000, 2), "diagnostic": None}
    except OSError as exc:
        return {"reachable": False, "latencyMs": round((time.monotonic()-started)*1000, 2), "diagnostic": str(exc)}


def http_json(method: str, url: str, payload: Any = None, timeout: float = 8.0) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method, headers={'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw=res.read()
            parsed=json.loads(raw.decode('utf-8')) if raw else {}
            return {"status":res.status,"body":parsed}
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode('utf-8','replace')
        raise RuntimeFailure('CONTROLLER_HTTP_ERROR', f'Controller returned HTTP {exc.code}.', {'url':url,'body':raw[:4000]})
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeFailure('CONTROLLER_UNREACHABLE', 'Controller request failed.', {'url':url,'diagnostic':str(exc)})


def controller_url(machine: dict[str, Any], route_key: str) -> str:
    address=machine['addresses'][0]
    controller=machine.get('controller',{})
    scheme=controller.get('scheme','http')
    port=controller.get('port',50053)
    routes=controller.get('routes',{})
    defaults={'status':'/status','rpcStart':'/rpc/start','rpcStop':'/rpc/stop','diagnostics':'/diagnostics'}
    route=routes.get(route_key,defaults[route_key])
    if not route.startswith('/'): route='/'+route
    return f'{scheme}://{address}:{port}{route}'


def controller_status(machine: dict[str, Any], *, timeout: float = 8.0) -> dict[str, Any]:
    return http_json('GET', controller_url(machine,'status'), timeout=timeout)['body']


def controller_rpc(machine: dict[str, Any], action: str) -> dict[str, Any]:
    if action not in {'start','stop'}: raise ValueError(action)
    key='rpcStart' if action=='start' else 'rpcStop'
    payload={'port':machine.get('rpc',{}).get('port',50052)}
    return http_json('POST',controller_url(machine,key),payload)['body']


def scan_gguf(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found=[]
    seen=set()
    for source in sources:
        root=Path(os.path.expandvars(os.path.expanduser(str(source.get('path','')))))
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob('*.gguf'):
            if path.name.lower().startswith('mmproj-'):
                continue
            try: stat=path.stat()
            except OSError: continue
            key=str(path.resolve()).lower()
            if key in seen: continue
            seen.add(key)
            sidecar=path.with_suffix('.json')
            try:
                metadata=parse_gguf_header(path)
            except (GgufError, OSError) as exc:
                metadata={'format':'GGUF','headerState':'failed','error':str(exc)}
            found.append({
                'id':'model-'+__import__('hashlib').sha1(key.encode()).hexdigest()[:12],
                'name':metadata.get('name') or path.stem,
                'path':str(path),
                'sourceId':source.get('id','source-manual'),
                'sizeBytes':stat.st_size,
                'sidecarPath':str(sidecar) if sidecar.exists() else None,
                'metadata':metadata,
                'discoveredAt':int(time.time()*1000),
            })
    return sorted(found,key=lambda m:m['name'].lower())


class ProcessManager:
    def __init__(self, log_dir: Path):
        self.log_dir=log_dir; self.log_dir.mkdir(parents=True,exist_ok=True)
        self._lock=threading.RLock(); self._process: subprocess.Popen|None=None; self._log_handle=None

    def status(self) -> dict[str, Any]:
        with self._lock:
            p=self._process
            if not p: return {'running':False,'pid':None,'returnCode':None}
            rc=p.poll()
            return {'running':rc is None,'pid':p.pid,'returnCode':rc}

    def start(self, executable: str, args: list[str], cwd: str|None=None) -> dict[str, Any]:
        with self._lock:
            if self._process:
                rc = self._process.poll()
                if rc is not None:
                    self._process = None
                    if self._log_handle:
                        self._log_handle.close()
                        self._log_handle = None
                else:
                    raise RuntimeFailure('RUNTIME_ALREADY_RUNNING','A managed llama-server process is already running.',self.status())
            exe=Path(os.path.expandvars(executable)).expanduser()
            if not exe.exists() or not exe.is_file():
                raise RuntimeFailure('EXECUTABLE_NOT_FOUND','llama-server executable was not found.',{'path':str(exe)})
            if exe.name.lower() not in {'llama-server.exe','llama-server'}:
                raise RuntimeFailure('EXECUTABLE_NOT_ALLOWED','Only llama-server or llama-server.exe may be launched.',{'path':str(exe)})
            log_path=self.log_dir/f'llama-server-{int(time.time())}.log'
            self._log_handle=open(log_path,'ab',buffering=0)
            flags=0
            if os.name=='nt': flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
            self._process=subprocess.Popen([str(exe),*args],cwd=cwd or str(exe.parent),stdout=self._log_handle,stderr=subprocess.STDOUT,creationflags=flags)
            return {'pid':self._process.pid,'command':[str(exe),*args],'logPath':str(log_path)}

    def stop(self, timeout: float=10.0) -> dict[str, Any]:
        with self._lock:
            p=self._process
            if not p or p.poll() is not None:
                return {'stopped':True,'wasRunning':False,'returnCode':None if not p else p.returncode}
            p.terminate()
            forced=False
            try: p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                forced=True; p.kill(); p.wait(timeout=5)
            rc=p.returncode
            if self._log_handle:
                self._log_handle.close(); self._log_handle=None
            self._process=None
            return {'stopped':True,'wasRunning':True,'forced':forced,'returnCode':rc}


def build_llama_command(model: dict[str,Any], profile: dict[str,Any]|None, machines: list[dict[str,Any]], body: dict[str,Any]) -> tuple[str,list[str],str|None,int,str]:
    values={}
    if profile: values.update(profile.get('values',{}))
    values.update(body.get('overrides',{}))
    executable=values.get('executable') or body.get('executable')
    if not executable:
        runtime_path=values.get('runtimePath') or body.get('runtimePath')
        if runtime_path: executable=str(Path(runtime_path)/('llama-server.exe' if os.name=='nt' else 'llama-server'))
    if not executable: raise RuntimeFailure('EXECUTABLE_REQUIRED','A llama-server executable or runtimePath is required.')
    model_path=values.get('modelPath') or model.get('path')
    if not model_path or not Path(os.path.expandvars(model_path)).exists():
        raise RuntimeFailure('MODEL_NOT_FOUND','The selected GGUF model file was not found.',{'path':model_path})
    port=int(values.get('port',1234)); host=str(values.get('host','127.0.0.1'))
    args=['-m',model_path,'--host',host,'--port',str(port)]
    mapping=[('gpuLayers','-ngl'),('contextSize','-c'),('batchSize','-b'),('ubatchSize','-ub'),('threads','-t'),('parallel','--parallel')]
    for key,flag in mapping:
        if values.get(key) is not None: args += [flag,str(values[key])]
    if values.get('flashAttention'): args += ['-fa', 'on']
    if values.get('cacheTypeK'): args += ['-ctk',str(values['cacheTypeK'])]
    if values.get('cacheTypeV'): args += ['-ctv',str(values['cacheTypeV'])]
    rpc_ids=values.get('rpcMachineIds') or body.get('rpcMachineIds') or []
    rpc=[]
    for mid in rpc_ids:
        m=next((x for x in machines if x['id']==mid and x.get('enabled',True)),None)
        if not m: raise RuntimeFailure('RPC_MACHINE_INVALID','An RPC machine is missing or disabled.',{'machineId':mid})
        rpc.append(f"{m['addresses'][0]}:{m.get('rpc',{}).get('port',50052)}")
    if rpc: args += ['--rpc',','.join(rpc)]
    tensor=values.get('tensorSplit')
    if tensor: args += ['--tensor-split',str(tensor),'--split-mode',str(values.get('splitMode','layer'))]
    extra=values.get('extraArgs',[])
    if extra:
        if not isinstance(extra,list) or not all(isinstance(x,str) for x in extra): raise RuntimeFailure('INVALID_EXTRA_ARGS','extraArgs must be a string array.')
        forbidden={'--model','-m','--host','--port'}
        if any(x in forbidden for x in extra): raise RuntimeFailure('RESERVED_ARGUMENT','Model, host, and port must use structured profile fields.')
        args.extend(extra)
    return executable,args,values.get('cwd'),port,host
