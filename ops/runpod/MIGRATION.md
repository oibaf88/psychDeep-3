# PsychDeep: Runpod Biomedical Llama 3.1 migration (STAGING ONLY)

**Status: not deployed or approved for clinical production.** The requested model is **Biomedical Llama 3.1**, not the MedQA fine-tune proposed previously. Its exact Hugging Face repository and immutable revision have NOT yet been unambiguously established. Do not create an endpoint with an assumed model. Do not merge or switch providers until the model identity, deployment and all release gates below are verified. Existing Render/Supabase services, active provider, clinical data and Cloudflare Tunnel remain unchanged.

## Architecture / scope

Browser -> existing Render static frontend -> existing Render FastAPI backend -> existing Supabase PostgreSQL. Move **inference only** to Runpod Serverless vLLM. Keep deterministic risk, consent checks, data provenance and audit in FastAPI/Supabase. Never expose Runpod API keys, Supabase service-role credentials, clinical records or Cloudflare tokens to the frontend, GitHub or model container. Do not change DNS or database schema for this migration.

## Model identity gate (BLOCKING)

The owner explicitly requires **Biomedical Llama 3.1**. Before deploying, obtain the owner's exact Hugging Face repository URL or model ID (or a verifiable equivalent release), then check all of the following against primary model files/card and actual config:

1. The model is the intended biomedical checkpoint and its true base is Llama **3.1**, not a similarly named Llama 3 model. Record exact repository, immutable commit/revision SHA, architecture and tokenizer, declared languages, model size and license (including applicable Meta terms and commercial permissions).
2. Confirm its model weights exist and are accessible with the operator's Hugging Face account; verify whether gating and HF_TOKEN are needed. Pin the immutable SHA in the worker rather than a moving `main` revision. Verify the actual vLLM worker supports the checkpoint and the served model ID matches `/models`.
3. Assess Spanish clinical/mental-health suitability; being biomedical does not establish clinical validity. Test with synthetic data first and obtain independent clinical review before any real clinical data.

**Do not deploy these as substitutes:** `empirischtech/Llama-3.1-8B-Instruct-MedQA` is a different MedQA candidate, not the requested model. The URL `https://huggingface.co/ContactDoctor/Bio-Medical-Llama-3.1-8B` redirects to `ContactDoctor/Bio-Medical-Llama-3-8B`, whose model card states Llama **3**, not 3.1, as its base. Other biomedical models with Llama 3.1 in their name are not automatically the owner's intended checkpoint. Both `render.yaml` and `worker.env.example` deliberately leave model ID unset or as a clearly invalid replacement token. **Do not replace placeholders with guesses.**

## Provision in Runpod (operator account required; AFTER model identity gate)

1. Authenticate to Runpod via official MCP/CLI or console; do not paste credentials in a chat, issue or repository. Check billing limits, EEA data-centre availability, data-processing terms, prompt/log retention and GDPR suitability. First tests: **synthetic text only**.
2. Deploy an official vLLM Serverless worker with the exact **verified biomedical Llama 3.1** Hugging Face repo ID and pinned revision. Review the chosen Hub release's supported worker variables; `worker.env.example` is a template, not a guarantee of env names. Size the GPU based on the actual model and concurrency: a >=24 GB GPU is only an initial hypothesis for 8B BF16 weights, not a guaranteed requirement or a sufficient size for a larger model. Reduce context/concurrency or increase VRAM if required.
3. Prototype cost controls: min workers **0**, max **1**, bounded idle/execution timeout and usage alerts/budget. Zero workers does not imply zero cost; GPU start-up and persistent volumes can incur costs. Use regional network storage only if required and approved.
4. Read the actual endpoint ID and served model ID from Runpod. Where supported by the selected vLLM worker, the OpenAI-compatible base URL is `https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1`; verify the returned endpoint URLs rather than guessing the ID or appending `/models` or `/chat/completions` to the configured base.
5. In a secure shell set `MODEL_CLOUD_BASE_URL`, `MODEL_CLOUD_API_KEY` and actual model IDs. Run `python backend/scripts/smoke_runpod.py` using synthetic data to verify authenticated `/models` and `/chat/completions`. Separately exercise structured analysis schema, copilot, concurrency, timeout, cold starts, authorization and error paths with synthetic fixtures.

## Stage Render backend without switching live traffic

Configure **Render backend** service `psychdeep-api` Environment (not static `psychdeep-web`). On existing Blueprints, `sync: false` does not prompt again; set secrets and verified model names manually. These are **templates only**:

```dotenv
MODEL_CLOUD_BASE_URL=https://api.runpod.ai/v2/REPLACE_WITH_REAL_ENDPOINT_ID/openai/v1
MODEL_CLOUD_API_KEY=<SET_SECRET_ONLY_IN_RENDER>
RUNPOD_ENABLED=false
MODEL_CLOUD_CHAT_MODEL=<EXACT_VERIFIED_SERVED_MODEL_ID_FROM_MODELS>
MODEL_CLOUD_ANALYSIS_MODEL=<EXACT_VERIFIED_SERVED_MODEL_ID_FROM_MODELS>
MODEL_CLOUD_COPILOT_MODEL=<EXACT_VERIFIED_SERVED_MODEL_ID_FROM_MODELS>
MODEL_CLOUD_TIMEOUT_SECONDS=180
MODEL_CLOUD_MAX_TOKENS=2048
```

Set actual model IDs to the precise `/models` response; do not use the Hugging Face repo ID if the worker advertises a different `served-model-name`. Keep `RUNPOD_ENABLED=false`. **Do not** change `MODEL_DEPLOYMENT_ALIAS=local-tunnel`, `LLM_PERSONAL_MODE`, `JWT_SECRET`, `LLM_USER_CREDENTIALS_KEY`, existing Anthropic/Cloudflare keys or live Supabase selection while staging. Never use `VITE_` / `NEXT_PUBLIC_` for the Runpod key.

## Two inference paths and credential isolation

- `ModelGateway` already supports alias `cloud-tuned`. The `llm_config` runtime row can separately override via the Supabase configuration; the `runpod_routing` allowlist attaches a Runpod key only if the runtime URL exactly matches the operator-pinned Runpod URL and all requested model IDs belong to its allowlist. It must not leak Cloudflare credentials to Runpod.
- `LLM_ALLOW_RUNTIME_OVERRIDE=true` means an active `psychdeep_v12.llm_endpoint_configs` row can supersede Render defaults. Previously observed active provider was Anthropic; recheck before production changes. Changing only Render's alias is insufficient. Use authenticated audited `admin_clinical` Settings only after integration tests. `LLM_PERSONAL_MODE=true` uses separate account-scoped LM Studio resolution and will not automatically switch to Runpod. Test cross-account isolation and determine an explicit personal-mode transition; do not silently disable it.

## Promotion gates (ALL required)

- Exact user-requested biomedical Llama **3.1** checkpoint provenance, immutable revision and license verified; `/models` reports expected served name; model passes Spanish clinical/psychiatric review.
- Routing tests + existing backend risk/consent/authorization tests + frontend tests/build + CI pass; run an actual synthetic request through Runpod from outside the worker. Confirm chat, structured JSON analysis and copilot end to end, timeout/cold-start behavior and no silent fallback.
- Verify GDPR processor terms, EEA region where required, prompt and log retention, access controls, encryption, audit and appropriate authorization/consent for identifiable clinical text. A chosen EU region alone does not establish compliance.
- Check model revision, role authorization, 401/403/429/5xx error paths, model run records and cross-account access. Promote only through audited admin runtime selection and preserve rollback settings. Roll back through admin selection rather than rewriting history. Do not retire Cloudflare/Anthropic or Render resources until a separate review establishes they are no longer needed.

## Current blocker

Runpod infrastructure actions and credentials are not available inside this ChatGPT session, even if OAuth was completed inside Codex: the connection does not automatically transfer. No GPU or endpoint has been provisioned here. **Model identification is an additional blocking prerequisite.** Finish the model identity check and Runpod provisioning from an authenticated Codex/Runpod session, configure the actual endpoint secrets securely, then run live smoke tests and review the rollout before any production switch. Do not claim that migration is live.

References: https://docs.runpod.io/ ; https://github.com/runpod-workers/worker-vllm ; https://huggingface.co/ContactDoctor/Bio-Medical-Llama-3-8B .
