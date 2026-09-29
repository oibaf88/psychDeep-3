# PsychDeep local inference agent

The local agent is the only component that needs to run on the Windows machine.

It opens an **outbound WSS connection** to the Render API. Render never connects
inbound to the home/office network, so there is no router port-forwarding,
Cloudflare Tunnel or public LM Studio URL.

The same authenticated channel carries both directions:

1. Render sends the prompt/context to the agent.
2. The agent sends the request to LM Studio/Ollama on 127.0.0.1.
3. The agent sends the model response back through the existing WSS channel.
4. Render records the model run and application response in PostgreSQL.

## Configuration

Copy ".env.example" to ".env" and set:

- PSYCHDEEP_API_URL — normally https://psychdeep-api.onrender.com
- PSYCHDEEP_LOCAL_BRIDGE_SECRET — the same secret configured on Render
- PSYCHDEEP_LOCAL_AGENT_ID — stable name for this Windows host
- LOCAL_LLM_BASE_URL — e.g. http://127.0.0.1:1234/v1 for LM Studio
- LOCAL_LLM_API_KEY — LM Studio API key if enabled
- LOCAL_LLM_CHAT_MODEL
- LOCAL_LLM_ANALYSIS_MODEL

The Render secret is not committed to GitHub and must not be embedded in the
frontend.

## Start

PowerShell:

  cd ops/local-inference-agent
  py -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  python agent.py

Keep the local LLM server bound to localhost. The agent does not expose it.

## Security model

Messages are JSON and individually HMAC-SHA256 signed. The socket itself is
TLS (wss://). The local agent never receives Render database credentials,
JWT signing keys or model-provider cloud credentials.
