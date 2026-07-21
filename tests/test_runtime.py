import tempfile
import unittest
from pathlib import Path
from backend.runtime import ProcessManager, RuntimeFailure, build_llama_command, scan_gguf

class RuntimeTests(unittest.TestCase):
    def test_scan_gguf_recursive(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'nested').mkdir(); (root/'nested'/'a.gguf').write_bytes(b'GGUF')
            models=scan_gguf([{'id':'s','path':td,'enabled':True}])
            self.assertEqual(len(models),1); self.assertEqual(models[0]['name'],'a')

    def test_command_is_structured(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); exe=root/('llama-server.exe'); exe.write_text('x'); model=root/'m.gguf'; model.write_bytes(b'x')
            profile={'values':{'executable':str(exe),'port':1234,'host':'127.0.0.1','gpuLayers':99,'contextSize':8192,'flashAttention':True}}
            result=build_llama_command({'path':str(model)},profile,[],{})
            self.assertIn('-ngl',result[1]); self.assertIn('-fa',result[1])

    def test_reserved_extra_args_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); exe=root/'llama-server.exe'; exe.write_text('x'); model=root/'m.gguf'; model.write_bytes(b'x')
            with self.assertRaises(RuntimeFailure):
                build_llama_command({'path':str(model)},{'values':{'executable':str(exe),'extraArgs':['--port','9999']}},[],{})

if __name__=='__main__': unittest.main()
