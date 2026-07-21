export const defaultMachines = [
  { id: 'host', name: 'Host workstation', role: 'Host', address: '192.168.1.240', controllerPort: 50053, rpcPort: 50052, gpu: 'RTX 3070 · 8 GB', cpu: 'Ryzen 7 5800H', ram: '64 GB', latency: 'Local', state: 'Online' },
  { id: 'worker-01', name: 'Worker 01', role: 'RPC worker', address: '192.168.1.155', controllerPort: 50053, rpcPort: 50052, gpu: 'GTX 1070 Ti ×2', cpu: 'Ryzen 7 3700X', ram: '48 GB', latency: '1.2 ms', state: 'Online' }
];

export const modelRows = [
  ['Qwen3.5-27B-Q4_K_M.gguf','Qwen','Q4_K_M','15.6 GB','131K','Balanced RPC','18.7 GB','Caution','Active'],
  ['Qwen3.5-9B-Q4_K_M.gguf','Qwen','Q4_K_M','5.3 GB','131K','Auto defaults','7.4 GB','Safe','Available'],
  ['Nemotron-4B-Q8_0.gguf','Nemotron','Q8_0','4.6 GB','32K','nemotron.json','6.1 GB','Safe','Available'],
  ['Gemma-3-270M-Q8_0.gguf','Gemma','Q8_0','0.4 GB','32K','Generated','1.2 GB','Safe','Available'],
  ['Llama-3.1-70B-Q4_K_M.gguf','Llama','Q4_K_M','39.5 GB','128K','None','Unknown','Unknown','Not loaded']
];

export const widgetCatalog = [
  { id:'active-model', icon:'◇', name:'Active model', desc:'Lifecycle, allocation, profile, and command preview' },
  { id:'machine-topology', icon:'⌘', name:'Machine topology', desc:'Any-number host and RPC worker graph' },
  { id:'gpu-telemetry', icon:'∿', name:'GPU & VRAM telemetry', desc:'Usage, temperature, power, and headroom' },
  { id:'request-table', icon:'↔', name:'Request table', desc:'Active, queued, history, cancellation' },
  { id:'logs', icon:'≡', name:'Logs & evidence', desc:'Searchable event and runtime evidence' },
  { id:'quick-actions', icon:'＋', name:'Custom actions', desc:'User-owned safe actions and scripts' },
  { id:'playground', icon:'›_', name:'Prompt playground', desc:'OpenAI or Ollama route testing' },
  { id:'api-health', icon:'◎', name:'API health', desc:'Configured endpoints and capability status' }
];

export const commandItems = [
  { label:'Open Models', hint:'Navigation', page:'models' },
  { label:'Open Machines', hint:'Navigation', page:'machines' },
  { label:'Add machine', hint:'Cluster action', action:'add-machine' },
  { label:'Add widget', hint:'Workspace action', action:'add-widget' },
  { label:'Create custom action', hint:'Automation', action:'add-action' },
  { label:'Rescan model sources', hint:'Model action', action:'scan' },
  { label:'Open Logs & evidence', hint:'Navigation', page:'logs' }
];
