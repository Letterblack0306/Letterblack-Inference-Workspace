from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, BinaryIO

GGUF_TYPES = {
    0: ("uint8", "<B"), 1: ("int8", "<b"), 2: ("uint16", "<H"), 3: ("int16", "<h"),
    4: ("uint32", "<I"), 5: ("int32", "<i"), 6: ("float32", "<f"), 7: ("bool", "<?"),
    10: ("uint64", "<Q"), 11: ("int64", "<q"), 12: ("float64", "<d"),
}

class GgufError(ValueError):
    pass


def _read_exact(fp: BinaryIO, n: int) -> bytes:
    data = fp.read(n)
    if len(data) != n:
        raise GgufError("Unexpected end of GGUF header.")
    return data


def _u32(fp: BinaryIO) -> int:
    return struct.unpack("<I", _read_exact(fp, 4))[0]


def _u64(fp: BinaryIO) -> int:
    return struct.unpack("<Q", _read_exact(fp, 8))[0]


def _string(fp: BinaryIO, *, max_length: int = 8_000_000) -> str:
    length = _u64(fp)
    if length > max_length:
        raise GgufError(f"GGUF string length {length} exceeds safety limit.")
    return _read_exact(fp, length).decode("utf-8", "replace")


def _value(fp: BinaryIO, value_type: int, *, depth: int = 0) -> Any:
    if depth > 3:
        raise GgufError("GGUF array nesting exceeds safety limit.")
    if value_type == 8:
        return _string(fp)
    if value_type == 9:
        item_type = _u32(fp)
        count = _u64(fp)
        if count > 1_000_000:
            raise GgufError("GGUF array exceeds safety limit.")
        values = [_value(fp, item_type, depth=depth + 1) for _ in range(count)]
        return values
    spec = GGUF_TYPES.get(value_type)
    if not spec:
        raise GgufError(f"Unsupported GGUF metadata type {value_type}.")
    _, fmt = spec
    return struct.unpack(fmt, _read_exact(fp, struct.calcsize(fmt)))[0]


def _skip_value(fp: BinaryIO, value_type: int, *, depth: int = 0) -> None:
    """Advance over a GGUF value without retaining it in process or state."""
    if depth > 3:
        raise GgufError("GGUF array nesting exceeds safety limit.")
    if value_type == 8:
        _string(fp)
        return
    if value_type == 9:
        item_type = _u32(fp)
        count = _u64(fp)
        if count > 1_000_000:
            raise GgufError("GGUF array exceeds safety limit.")
        for _ in range(count):
            _skip_value(fp, item_type, depth=depth + 1)
        return
    spec = GGUF_TYPES.get(value_type)
    if not spec:
        raise GgufError(f"Unsupported GGUF metadata type {value_type}.")
    _read_exact(fp, struct.calcsize(spec[1]))


def _is_summary_metadata(key: str) -> bool:
    return key in {
        "general.architecture",
        "general.name",
        "general.quantization_version",
        "general.file_type",
    } or key.endswith((
        ".block_count",
        ".context_length",
        ".embedding_length",
        ".attention.head_count",
        ".attention.head_count_kv",
    ))


def parse_gguf_header(path: str | Path, *, max_metadata: int = 100_000) -> dict[str, Any]:
    model_path = Path(path)
    with model_path.open("rb") as fp:
        if _read_exact(fp, 4) != b"GGUF":
            raise GgufError("File does not start with the GGUF magic number.")
        version = _u32(fp)
        if version not in {2, 3}:
            raise GgufError(f"Unsupported GGUF version {version}.")
        tensor_count = _u64(fp)
        metadata_count = _u64(fp)
        if metadata_count > max_metadata:
            raise GgufError("GGUF metadata count exceeds safety limit.")
        metadata: dict[str, Any] = {}
        for _ in range(metadata_count):
            key = _string(fp, max_length=65_536)
            value_type = _u32(fp)
            if _is_summary_metadata(key):
                metadata[key] = _value(fp, value_type)
            else:
                _skip_value(fp, value_type)

    architecture = metadata.get("general.architecture")
    prefix = str(architecture) if architecture else None
    def first(*keys: str):
        for key in keys:
            if key in metadata:
                return metadata[key]
        return None
    result = {
        "format": "GGUF",
        "headerState": "parsed",
        "version": version,
        "tensorCount": tensor_count,
        "metadataCount": metadata_count,
        "architecture": architecture,
        "name": metadata.get("general.name"),
        "quantizationVersion": metadata.get("general.quantization_version"),
        "fileType": metadata.get("general.file_type"),
        "blockCount": first(f"{prefix}.block_count" if prefix else "", "llama.block_count"),
        "contextLength": first(f"{prefix}.context_length" if prefix else "", "llama.context_length"),
        "embeddingLength": first(f"{prefix}.embedding_length" if prefix else "", "llama.embedding_length"),
        "headCount": first(f"{prefix}.attention.head_count" if prefix else "", "llama.attention.head_count"),
        "headCountKv": first(f"{prefix}.attention.head_count_kv" if prefix else "", "llama.attention.head_count_kv"),
    }
    return result
