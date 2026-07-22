import unittest
from backend.hardware import estimate_allocation

class HardwareTests(unittest.TestCase):
    def test_estimate_flags_excess_layers(self):
        model={'sizeBytes':4*1024**3,'metadata':{'headerState':'parsed','blockCount':32,'contextLength':8192,'embeddingLength':4096,'headCount':32,'headCountKv':8}}
        tele={'gpus':[{'memoryTotalBytes':8*1024**3,'memoryFreeBytes':7*1024**3}]}
        result=estimate_allocation(model,{'gpuLayers':40,'contextSize':8192,'batchSize':1,'cacheTypeK':'q8_0','cacheTypeV':'q8_0'},tele)
        self.assertTrue(any(x['code']=='GPU_LAYERS_EXCEED_MODEL' for x in result['warnings']))
        self.assertIn(result['risk'],{'safe','caution','high'})

    def test_estimate_accepts_per_layer_kv_head_counts(self):
        model={'sizeBytes':4*1024**3,'metadata':{'headerState':'parsed','blockCount':32,'contextLength':8192,'embeddingLength':4096,'headCount':32,'headCountKv':[0,8,0]}}
        tele={'gpus':[{'memoryTotalBytes':8*1024**3,'memoryFreeBytes':7*1024**3}]}
        result=estimate_allocation(model,{'gpuLayers':32,'contextSize':8192,'batchSize':1},tele)
        self.assertIsInstance(result['kvCacheBytes'],int)

    def test_kv_cache_uses_parallel_slots_not_batch_size(self):
        model={'sizeBytes':4*1024**3,'metadata':{'headerState':'parsed','blockCount':32,'contextLength':8192,'embeddingLength':4096,'headCount':32,'headCountKv':8}}
        tele={'gpus':[{'memoryTotalBytes':8*1024**3,'memoryFreeBytes':7*1024**3}]}
        low_batch=estimate_allocation(model,{'gpuLayers':32,'contextSize':8192,'batchSize':1,'parallel':2},tele)
        high_batch=estimate_allocation(model,{'gpuLayers':32,'contextSize':8192,'batchSize':512,'parallel':2},tele)
        self.assertEqual(low_batch['kvCacheBytes'],high_batch['kvCacheBytes'])
