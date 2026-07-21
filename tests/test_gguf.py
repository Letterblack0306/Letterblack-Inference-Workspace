import struct
import tempfile
import unittest
from pathlib import Path
from backend.gguf import GgufError, parse_gguf_header

def s(value: str):
    raw=value.encode(); return struct.pack('<Q',len(raw))+raw

def entry(key, type_id, value):
    out=s(key)+struct.pack('<I',type_id)
    if type_id==8: out+=s(value)
    elif type_id==4: out+=struct.pack('<I',value)
    elif type_id==10: out+=struct.pack('<Q',value)
    return out

class GgufTests(unittest.TestCase):
    def test_parses_core_metadata(self):
        entries=[entry('general.architecture',8,'llama'),entry('llama.block_count',4,32),entry('llama.context_length',4,8192),entry('llama.embedding_length',4,4096),entry('llama.attention.head_count',4,32),entry('llama.attention.head_count_kv',4,8)]
        raw=b'GGUF'+struct.pack('<IQQ',3,100,len(entries))+b''.join(entries)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'m.gguf'; path.write_bytes(raw)
            data=parse_gguf_header(path)
            self.assertEqual(data['architecture'],'llama'); self.assertEqual(data['blockCount'],32); self.assertEqual(data['headCountKv'],8)
    def test_rejects_invalid_magic(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'m.gguf'; path.write_bytes(b'NOPE')
            with self.assertRaises(GgufError): parse_gguf_header(path)

    def test_excludes_large_tokenizer_metadata_from_summary(self):
        tokens = [f"token-{index}" for index in range(256)]
        array = struct.pack('<IQ', 8, len(tokens)) + b''.join(s(token) for token in tokens)
        entries = [
            entry('general.architecture', 8, 'llama'),
            s('tokenizer.ggml.tokens') + struct.pack('<I', 9) + array,
            entry('llama.context_length', 4, 8192),
        ]
        raw = b'GGUF' + struct.pack('<IQQ', 3, 100, len(entries)) + b''.join(entries)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'm.gguf'; path.write_bytes(raw)
            data = parse_gguf_header(path)
        self.assertEqual(data['contextLength'], 8192)
        self.assertNotIn('raw', data)
        self.assertNotIn('tokenizer.ggml.tokens', data)
