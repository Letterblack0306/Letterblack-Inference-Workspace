from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


def _run(command: list[str], timeout: float = 3.0) -> str:
    return subprocess.check_output(command, stderr=subprocess.DEVNULL, timeout=timeout, text=True, encoding="utf-8", errors="replace")


def _memory_bytes() -> tuple[int | None, int | None]:
    if os.name == "nt":
        try:
            raw = _run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json -Compress"])
            data = json.loads(raw)
            return int(data["TotalVisibleMemorySize"]) * 1024, int(data["FreePhysicalMemory"]) * 1024
        except Exception:
            return None, None
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        total = page * os.sysconf("SC_PHYS_PAGES")
        available = page * os.sysconf("SC_AVPHYS_PAGES")
        return int(total), int(available)
    except (ValueError, OSError, AttributeError):
        return None, None


def nvidia_gpus() -> list[dict[str, Any]]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return []
    fields = ["index", "uuid", "name", "driver_version", "memory.total", "memory.used", "memory.free", "utilization.gpu", "temperature.gpu", "power.draw"]
    try:
        output = _run([executable, f"--query-gpu={','.join(fields)}", "--format=csv,noheader,nounits"], timeout=5)
    except Exception:
        return []
    result = []
    for line in output.splitlines():
        values = [part.strip() for part in line.split(",")]
        if len(values) != len(fields):
            continue
        def number(value: str, *, integer: bool = False):
            if value in {"N/A", "[Not Supported]", ""}: return None
            try: return int(float(value)) if integer else float(value)
            except ValueError: return None
        result.append({
            "index": number(values[0], integer=True), "uuid": values[1], "name": values[2], "driverVersion": values[3],
            "memoryTotalBytes": (number(values[4]) or 0) * 1024 * 1024,
            "memoryUsedBytes": (number(values[5]) or 0) * 1024 * 1024,
            "memoryFreeBytes": (number(values[6]) or 0) * 1024 * 1024,
            "utilizationPercent": number(values[7]), "temperatureC": number(values[8]), "powerWatts": number(values[9]),
        })
    return result


def local_telemetry() -> dict[str, Any]:
    total, available = _memory_bytes()
    return {
        "timestamp": int(time.time() * 1000),
        "machine": {"hostname": platform.node(), "platform": platform.platform(), "processor": platform.processor(), "cpuCount": os.cpu_count()},
        "memory": {"totalBytes": total, "availableBytes": available, "usedBytes": total - available if total is not None and available is not None else None},
        "gpus": nvidia_gpus(),
    }


def _cache_bytes_per_element(cache_type: str | None) -> float:
    return {"q4_0": 0.5, "q4_1": 0.5, "q5_0": 0.625, "q5_1": 0.625, "q8_0": 1.0, "f16": 2.0, "fp16": 2.0, "f32": 4.0}.get(str(cache_type or "f16").lower(), 2.0)


def estimate_allocation(model: dict[str, Any], values: dict[str, Any], telemetry: dict[str, Any], *, reserve_bytes: int | None = None, safety_margin: float = 0.10) -> dict[str, Any]:
    metadata = model.get("metadata") or {}
    file_size = int(model.get("sizeBytes") or 0)
    total_layers = metadata.get("blockCount")
    gpu_layers = values.get("gpuLayers")
    if gpu_layers is None:
        gpu_layers = total_layers
    try: gpu_layers_i = max(0, int(gpu_layers))
    except (TypeError, ValueError): gpu_layers_i = 0
    confidence = "high" if metadata.get("headerState") == "parsed" and total_layers and metadata.get("embeddingLength") and metadata.get("headCount") else "low"
    if total_layers:
        offload_fraction = min(1.0, gpu_layers_i / max(1, int(total_layers)))
    else:
        offload_fraction = 1.0 if gpu_layers_i > 0 else 0.0
    weights = int(file_size * offload_fraction)
    context = int(values.get("contextSize") or metadata.get("contextLength") or 4096)
    batch = int(values.get("batchSize") or 1)
    layers = int(total_layers or 0)
    embedding = int(metadata.get("embeddingLength") or 0)
    heads = int(metadata.get("headCount") or 0)
    kv_heads = int(metadata.get("headCountKv") or heads or 0)
    head_dim = int(embedding / heads) if embedding and heads else 0
    cache_precision = max(_cache_bytes_per_element(values.get("cacheTypeK")), _cache_bytes_per_element(values.get("cacheTypeV")))
    kv = int(2 * layers * kv_heads * head_dim * context * max(1, batch) * cache_precision) if all([layers, kv_heads, head_dim]) else None
    total_gpu = sum(int(g.get("memoryTotalBytes") or 0) for g in telemetry.get("gpus", []))
    free_gpu = sum(int(g.get("memoryFreeBytes") or 0) for g in telemetry.get("gpus", []))
    reserve = int(reserve_bytes if reserve_bytes is not None else max(768 * 1024**2, total_gpu * 0.05 if total_gpu else 0))
    estimated = weights + (kv or 0) + reserve
    safe_limit = int(free_gpu * (1.0 - max(0.0, min(0.5, safety_margin))))
    headroom = free_gpu - estimated
    risk = "unknown" if not total_gpu else ("safe" if estimated <= safe_limit else "caution" if estimated <= free_gpu else "high")
    warnings = []
    if total_layers and gpu_layers_i > int(total_layers): warnings.append({"code":"GPU_LAYERS_EXCEED_MODEL","message":"GPU layer count exceeds the model block count."})
    if metadata.get("contextLength") and context > int(metadata["contextLength"]): warnings.append({"code":"CONTEXT_EXCEEDS_METADATA","message":"Requested context exceeds GGUF context metadata."})
    if kv is None: warnings.append({"code":"KV_ESTIMATE_UNAVAILABLE","message":"GGUF metadata is insufficient for a KV-cache estimate."})
    if not total_gpu: warnings.append({"code":"GPU_TELEMETRY_UNAVAILABLE","message":"No NVIDIA telemetry was detected; allocation risk cannot be verified."})
    if risk == "high": warnings.append({"code":"PREDICTED_VRAM_EXCEEDED","message":"Estimated VRAM requirement exceeds currently free VRAM."})
    return {
        "confidence": confidence, "risk": risk, "modelWeightsBytes": weights, "kvCacheBytes": kv,
        "runtimeReserveBytes": reserve, "estimatedTotalBytes": estimated, "gpuTotalBytes": total_gpu,
        "gpuFreeBytes": free_gpu, "safeLimitBytes": safe_limit, "headroomBytes": headroom,
        "inputs": {"gpuLayers": gpu_layers_i, "totalLayers": total_layers, "contextSize": context, "batchSize": batch, "cacheBytesPerElement": cache_precision, "safetyMargin": safety_margin},
        "warnings": warnings,
    }
