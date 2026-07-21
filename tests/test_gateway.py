import json
import threading
import time
import unittest
from backend.gateway import ActiveRequest, GatewayError, GatewayRequestManager, model_list, ollama_tags

class GatewayTests(unittest.TestCase):
    def test_openai_model_list_is_truthful_when_stopped(self):
        self.assertEqual(model_list({"state":"stopped","activeModelId":None}, []), {"object":"list","data":[]})

    def test_ollama_tags_active_model(self):
        result=ollama_tags({"state":"ready","activeModelId":"m1"}, [{"id":"m1","name":"Qwen","sizeBytes":12,"metadata":{"architecture":"qwen"}}])
        self.assertEqual(result["models"][0]["name"], "Qwen")

    def test_drain_rejects_new_requests(self):
        mgr=GatewayRequestManager(); mgr.set_draining(True)
        with self.assertRaises(GatewayError):
            mgr.begin(ActiveRequest("r1","/v1/chat/completions","openai",0))

    def test_drain_waits_for_active_request(self):
        mgr=GatewayRequestManager(); mgr.begin(ActiveRequest("r1","/v1/chat/completions","openai",0))
        threading.Timer(.05, lambda: mgr.finish("r1")).start()
        result=mgr.drain(.5)
        self.assertTrue(result["drained"])

    def test_active_cancel_is_explicitly_unsupported(self):
        mgr=GatewayRequestManager(); mgr.begin(ActiveRequest("r1","/api/chat","ollama",0))
        result=mgr.cancel("r1")
        self.assertTrue(result["cancelUnsupported"])

if __name__ == "__main__": unittest.main()
