# PsychDeep 3.1 — staged Runpod / biomedical Llama 3.1 migration

**Status: integration prepared, NOT deployed or clinically approved.** Do not label this migration complete until an actual endpoint, privacy clearance, contract/safety evaluation, reviewed database deployment metadata and production smoke tests are evidenced. No user/patient data may be used in smoke tests.

## 1. Scope and architecture

Keep Render `psychdeep-web` (React) and `psychdeep-api` (FastAPI), existing Supabase as the **only** clinical database and deterministic risk engine unchanged. Only the replaceable inference plane moves to Runpod. The optional local LM Studio + Cloudflare Tunnel remains a separate, deliberately selected provider; there is no silent cross-provider fallback. Do **not** migrate the production PostgreSQL database or expose secrets in frontend, GitHub or Supabase rows.

Target model candidate: `TsinghuaC3I/Llama-3.1-8B-UltraMedical` (Hugging Face). This is a publicly published **third-party biomedical fine-tune of Llama 3.1**, not a PsychDeep-specific model or a model already validated on PsychDeep. Confirm the Hugging Face model card, exact immutable commit revision, weights, tokenizer, license, provenance and any gating before deploying. Important: `ContactDoctor/Bio-Medical-Llama-3.1-8B` redirects to `ContactDoctor/Bio-Medical-Llama-3-8B` whose declared base is Llama **3**, so that redirect cannot satisfy the Llama **3.1** requirement.

## 2. Runpod deployment (operator action; may incur GPU charges)

1. Review the Runpod service region, data-processing agreement, subprocessors, data/log retention, deletion, incident response, transfer safeguards and relevant clinical/privacy approval. Prefer EEA residency and independently verify what the actual selected offering guarantees. Use synthetic data until approved for real clinical text. Set a spending ceiling/alerts and choose a `maxWorkers=1`, `minWorkers=0` prototype where supported. Scale-to-zero may cause cold starts; never automatically divert a real patient's prompt to Anthropic/local on timeout.
2. In Runpod Serverless deploy the official vLLM worker `runpod/worker-v1-vllm` with an explicitly **pinned tested image tag**, not `latest`; use the official template/Hub when suitable. Select an available GPU with enough VRAM for the model and KV cache (a 24 GB class is a reasonable initial sizing **hypothesis**, not a verified guarantee); validate availability/cost in your account. Model environment: `MODEL_NAME=TsinghuaC3I/Llama-3.1-8B-UltraMedical`; `MAX_MODEL_LEN=4096` initially; `GPU_MEMORY_UTILIZATION=0.85`; `TENSOR_PARALLEL_SIZE=1`. Do not enable tool-calling or arbitrary `trust_remote_code` unless reviewed. Supply `HF_TOKEN` as a Runpod secret **only if** the pinned model revision requires access. Pin model revision where the worker supports `MODEL_REVISION`, and record image digest, model revision, tokenizer revision and GPU SKU in release evidence.
3. For a queue-backed vLLM worker, obtain the actual endpoint ID from the Runpod console and use `https://api.runpod.ai/v2/ENDPOINT_ID/openai/v1` as the **base URL**. Do not append `/chat/completions` or `/models` to `MODEL_CLOUD_BASE_URL`. For a direct load-balanced vLLM endpoint use the actual Runpod-provided URL ending in `/v1`; the HTTP contract is different and cold-start behavior must be evaluated independently. The backend already sends `/chat/completions` and checks `/models` relative to the base URL.
4. Do not place the Runpod API key in the repository, URL, Docker image, logs or client-side `VITE_*` variables. Store it only as a protected Render server-side environment secret `MODEL_CLOUD_API_KEY`, with minimum permitted scope where supported. The local Cloudflare connector token, Cloudflare Access service credentials and local LM Studio API key must **not** be sent to Runpod.
5. From a secure operator environment set `MODEL_CLOUD_BASE_URL`, `MODEL_CLOUD_API_KEY`, `MODEL_CLOUD_CHAT_MODEL` and `MODEL_CLOUD_ANALYSIS_MODEL`, then run `python ops/model/runpod_preflight.py`. The script uses only the synthetic `OK` prompt, requires exact `/models` IDs and tests authenticated chat. A passing preflight is connectivity evidence **only**, not proof of adequate Spanish performance, structured JSON, clinical safety or privacy.

## 3. Required Render settings AFTER staging and review

Set these on the existing `psychdeep-api` service as server-side values, **not** on the public static web service. Keep the existing `DATABASE_URL`, `DATABASE_SCHEMA`, `JWT_SECRET`, CORS, Cloudflare/local settings and Supabase project unchanged.

```dotenv
# Example placeholders: do not commit real endpoint IDs or secrets.
MODEL_CLOUD_BASE_URL=https://api.runpod.ai/v2/ENDPOINT_ID/openai/v1
MODEL_CLOUD_API_KEY=<set in Render secret environment only>
MODEL_CLOUD_CHAT_MODEL=TsinghuaC3I/Llama-3.1-8B-UltraMedical
MODEL_CLOUD_ANALYSIS_MODEL=TsinghuaC3I/Llama-3.1-8B-UltraMedical
MODEL_CLOUD_COPILOT_MODEL=TsinghuaC3I/Llama-3.1-8B-UltraMedical
MODEL_CLOUD_TIMEOUT_SECONDS=120
MODEL_CLOUD_MAX_TOKENS=2048
```

**Do not set `MODEL_DEPLOYMENT_ALIAS=cloud-tuned` yet.** Cutover gate: positive preflight and complete model safety/contract tests, Spanish and JSON-schema tests, reviewed license/privacy and approved runtime/deployment metadata. The legacy main inference path uses `llm_config` and can override the deployment default: existing `llm_endpoint_configs` runtime selection (`LLM_ALLOW_RUNTIME_OVERRIDE=true`) and account-scoped personal mode (`LLM_PERSONAL_MODE=true`) may prevent the cloud default from being used. During a controlled cutover, disable those switches **only with an explicit operator decision and a reviewed local-access impact plan**, or implement an audited cloud selection in both flows. Do not claim success from changing the environment alias alone.

After approval, explicitly select `MODEL_DEPLOYMENT_ALIAS=cloud-tuned`, verify the actual model ID in a recorded `model_runs` entry, verify that all relevant inference call paths use the selected profile, and test an outage: no clinical-data loss, deterministic safety still works, and no automatic alternative provider. Run complete clinical regression checks in `AGENTS.md` / `docs/release/CHECKLIST.md` before production use. Never auto-merge this branch just to effect the cutover.

## 4. Runpod fine-tuning is a separate gated task

Serving a third-party fine-tuned model is **not** fine-tuning it on PsychDeep data. For an application-specific adapter, create a separate ephemeral training Pod only after dataset consent, lawful basis, minimisation/de-identification and the approved data processing boundary are documented. Use versioned training/evaluation splits and a pinned base revision, track dataset hashes, LoRA/QLoRA parameters, seeds and metrics, keep raw patient data out of model artifacts, and publish no weights publicly by default. Promote a reviewed immutable adapter/merged-model revision through experiment -> evaluation -> clinical review -> shadow -> canary -> production. Never train the risk engine's decision thresholds into a model or allow an LLM to override deterministic risk.

## 5. Rollback and spend controls

If deployment, safety, privacy or contract checks fail, **do not cut over**. After a later cutover, an authorised admin may deliberately restore the previous approved alias, keeping provider choice audited and credentials server-side. Retain the original local tunnel and Render/Supabase configuration until rollback is exercised. When the prototype is idle, scale Runpod workers to zero / stop temporary Pods and check whether network volumes, idle workers or other resources are still billable. Do not delete clinical data, historical model-run records or original model assets as part of a rollback.

## Evidence checklist

- [ ] Runpod authenticated endpoint ID, region, GPU, immutable worker image and model/tokenizer revision recorded **without credentials**.
- [ ] Region/DPA/retention/licence/consent/legal and security approval for real clinical data.
- [ ] `/models` and synthetic chat preflight pass from outside Runpod.
- [ ] Spanish, JSON schema, tool-use (if applicable), crisis, hallucination, prompt-injection, privacy and regression gates pass.
- [ ] Runtime override and personal mode behavior documented and tested for all call paths.
- [ ] No CF/LM Studio secrets sent to Runpod; no Runpod key exposed to browser or DB.
- [ ] Risk/deterministic core works while Runpod is offline, no silent provider failover.
- [ ] Release/rollback, data retention, spend controls and clinical sign-off recorded.

Sources: https://github.com/runpod-workers/worker-vllm ; https://docs.runpod.io ; https://huggingface.co/TsinghuaC3I/Llama-3.1-8B-UltraMedical ; https://huggingface.co/ContactDoctor/Bio-Medical-Llama-3.1-8B .
