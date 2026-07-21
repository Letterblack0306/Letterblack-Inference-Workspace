const BASE='/api/v1';
export class ApiError extends Error{constructor(code,message,status=0,details=null){super(message||code);this.code=code;this.status=status;this.details=details}}
async function req(path,options={}){const r=await fetch(BASE+path,{...options,headers:{'Content-Type':'application/json','X-Letterblack-UI':'truthful-ui-v1',...(options.headers||{})}});const p=await r.json().catch(()=>null);if(!r.ok||!p||p.ok===false){const e=p?.error||{};throw new ApiError(e.code||`HTTP_${r.status}`,e.message||r.statusText,r.status,e.details)}return p.data}
const body=v=>JSON.stringify(v??{});
export const api={
 capabilities:()=>req('/capabilities'),status:()=>req('/system/status'),machines:()=>req('/machines'),
 createMachine:v=>req('/machines',{method:'POST',body:body(v)}),testMachine:id=>req(`/machines/${encodeURIComponent(id)}/test`,{method:'POST',body:'{}'}),
 rpcStart:id=>req(`/machines/${encodeURIComponent(id)}/rpc/start`,{method:'POST',body:'{}'}),rpcStop:id=>req(`/machines/${encodeURIComponent(id)}/rpc/stop`,{method:'POST',body:'{}'}),
 models:()=>req('/models'),scan:()=>req('/models/scan',{method:'POST',body:'{}'}),profiles:()=>req('/profiles'),
 preflight:v=>req('/runtime/preflight',{method:'POST',body:body(v)}),launch:v=>req('/runtime/launch',{method:'POST',body:body(v)}),stop:v=>req('/runtime/stop',{method:'POST',body:body(v)}),
 jobs:()=>req('/jobs'),job:id=>req(`/jobs/${encodeURIComponent(id)}`),telemetry:()=>req('/telemetry'),logs:()=>req('/logs'),requests:()=>req('/requests'),gateway:()=>req('/gateway/status'),
 cancel:id=>req(`/requests/${encodeURIComponent(id)}/cancel`,{method:'POST',body:'{}'})};
