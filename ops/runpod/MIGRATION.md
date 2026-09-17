# PsychDeep: Runpod biomedical Llama 3.1 migration (STAGING ONLY)

**Status: not deployed or approved for clinical production.** Do not merge or switch providers until every gate below passes. Existing Render/Supabase services, clinical data, previous model configuration and Cloudflare Tunnel remain in place.

## Architecture / scope

Browser -> existing Render static frontend -> existing Render FastAPI backend -> existing Supabase PostgreSQL. Only **inference** moves to Runpod Serverless vLLM. Keep deterministic risk, consent checks, data provenance and audit in FastAPI/Supabase. Do not expose Runpod API keys, Supabase service-role credentials, clinical records or Cloudflare tokens to the frontend, GitHub or model container. Do not change DNS or the existing database schema for this migration.

## Exact model candidate (not clinically validated)

`empirischtech/Llama-3.1-8B-Instruct-MedQA`, https://huggingface.co/empirischtech/Llama-3.1-8B-Instruct-MedQA . Its model card states base Llama 3.1 and a medical fine-tune, identifies a Llama 3.1 license and describes research/educational use. Confirm access, license (including applicable Meta terms), architecture and compatibility with the selected vLLM worker, model revision SHA, provenance, medical/mental-health/Spanish accuracy and commercial permission before deployment. Model-card marketing is not independent validation. The similarly named `ContactDoctor/Bio-Medical-Llama-3.1-8B` redirects to `ContactDoctor/Bio-Medical-Llama-3-8B`, whose card says its base is Llama **3**, not 3.1; do not use that model as a substitute.

## Provision in Runpod (operator account required)

1. Authenticate to Runpod with its official MCP/CLI or console; do not copy the key into an issue, chat, or repository. Check billing limits and whether an EEA data center, data-processing terms and no prompt retention satisfy your data-handling requirements. For the first test send **only synthetic text**.
2. Deploy a vLLM **Serverless** worker (official vLLM Hub template, not a generic queue worker) with Hugging Face model identifier above; pin a tested exact model revision and worker image. Prefer an EEA region if available, one 24-GB-or-larger GPU as an initial **sizing hypothesis** for 8B BF16 weights (~16GB plus KV cache/overhead), and reduce context/concurrency or use a larger GPU if OOM. Use supported worker settings as displayed in the chosen Hub release rather than assuming parameter names.
3. For prototype cost control choose minimum workers **0**, maximum **1**, and configure idle timeout and execution timeout compatible with cold starts; zero workers trades latency for cost and is not a zero-cost promise. Set usage alerts/budget limits. Persist model caches on a network volume only if required and within approved data center; note storage charges can continue while workers are at zero.
4. Obtain the **actual** endpoint ID and served model ID from the deployed endpoint. The verified OpenAI-compatible base URL for the selected vLLM endpoint should be `https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1`, *not* `/run`, `/runsync`, `/chat/completions` or `/models`. Check the running worker documentation; do not invent an endpoint ID.
5. In a secure shell, set `MODEL_CLOUD_BASE_URL`, `MODEL_CLOUD_API_KEY` (Runpod API key scoped as narrowly as supported) and `MODEL_CLOUD_CHAT_MODEL` to that real URL, key and served ID. Run `python backend/scripts/smoke_runpod.py`. It sends synthetic text only and checks authenticated `/models` and `/chat/completions`. After that, separately exercise **structured analysis schema**, chat, clinical copilot, concurrency, timeout, worker cold starts, authorization and error paths with synthetic test fixtures.

## Stage Render backend, without switching live traffic

Render service: `psychdeep-api` (`backend`), not static `psychdeep-web` or unrelated services. Use its **Environment** tab to set:

```dotenv
# Values shown are templates; enter actual endpoint ID/secret in Render only.
MODEL_CLOUD_BASE_URL=https://api.runpod.ai/v2/REPLACE_WITH_REAL_ENDPOINT_ID/openai/v1
MODEL_CLOUD_API_KEY=<ENTER_IN_RENDER_ONLY>
MODEL_CLOUD_CHAT_MODEL=empirischtech/Llama-3.1-8B-Instruct-MedQA
MODEL_CLOUD_ANALYSIS_MODEL=empirischtech/Llama-3.1-8B-Instruct-MedQA
MODEL_CLOUD_COPILOT_MODEL=empirischtech/Llama-3.1-8B-Instruct-MedQA
MODEL_CLOUD_TIMEOUT_SECONDS=180
MODEL_CLOUD_MAX_TOKENS=2048
```

The actual model ID may differ if the vLLM worker advertises a `served-model-name`; use **exactly** the `/models` response. `render.yaml` declares staging variables but `sync: false` will not prompt on updates to an existing Blueprint; explicitly set them in Render. Do **not** change `MODEL_DEPLOYMENT_ALIAS=local-tunnel`, `LLM_PERSONAL_MODE`, `JWT_SECRET`, `LLM_USER_CREDENTIALS_KEY`, existing Anthropic/Cloudflare keys or the live Supabase active selection while staging. Never use `VITE_` / `NEXT_PUBLIC_` for the Runpod key.

## Two inference paths require verification

- `ModelGateway` already supports alias `cloud-tuned`, using `MODEL_CLOUD_*` settings. The legacy `llm_config` can select a stored runtime row; `build_provider` now attaches the Runpod key only if the runtime URL **exactly** matches the operator-pinned Runpod cloud URL and requested model IDs are approved. It cannot leak Cloudflare credentials to Runpod.
- `LLM_ALLOW_RUNTIME_OVERRIDE=true` means the active `psychdeep_v12.llm_endpoint_configs` row takes precedence for legacy paths. Currently that row selects Anthropic. Changing only `MODEL_DEPLOYMENT_ALIAS` in Render will **not** switch those calls. Do not alter audit/history tables directly to force a switch: use authenticated `admin_clinical` Settings only after integration tests. `LLM_PERSONAL_MODE=true` uses a separate account-scoped LM Studio resolver and will **not** automatically switch to Runpod. Decide on a properly tested personal-mode migration or operator-controlled change; do not disable per-account isolation silently.

## Promotion gates (all must pass)

- Tests: new routing allowlist tests + existing `backend` risk/consent/authorization suite + frontend tests/build + GitHub CI; run a real synthetic Runpod request from outside the worker.
- Evaluate Spanish medical/psychiatric text, clinical facts vs inferences, hallucinations, prompt injection, incorrect classifications, structured JSON tool contract and deterministic emergency response; independent clinical review before any live clinical use.
- Data handling: verify GDPR processor agreement, region, actual prompt/log retention, access controls, encryption, audit policy, and whether sending identifiable patient text to Runpod is lawful and consented. Do not infer compliance from a selectable EU region.
- Inspect `/models`, verify exact pinned model revision, chat/analysis/copilot end to end, status logging/usage, valid role authorization, 401/403/429/5xx and unavailable-worker behavior. No silent provider fallback or use of a different model.
- Only after all gates, activate the documented admin runtime selection, check actual `model_runs` records and model IDs, and keep previous settings for rollback. Roll back through the audited admin selection, not by rewriting historical rows. Retire Cloudflare/Anthropic/Render resources only in a separate review after proving no dependency remains.

## Outstanding infrastructure blocker

The Runpod official app skill is installed but its infrastructure actions are not connected in this ChatGPT session. No Runpod endpoint, GPU, paid volume or credential has been provisioned here. Therefore **do not claim that the migration is live**. Finish the Runpod provisioning through the official Runpod app in Codex or console, then pass the actual endpoint ID through secure configuration, execute live smoke tests and explicitly approve the production switch.

References: https://docs.runpod.io/ ; https://github.com/runpod-workers/worker-vllm ; https://huggingface.co/empirischtech/Llama-3.1-8B-Instruct-MedQA ; https://huggingface.co/ContactDoctor/Bio-Medical-Llama-3-8B .
