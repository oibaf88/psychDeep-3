# LM Studio via Cloudflare Tunnel and Cloudflare Access

**Windows 11 Docker deployment:** see [`ops/model/docker/README.md`](../../ops/model/docker/README.md) for ready-to-use Dockerfile, `.dockerignore`, Compose, secret-import and startup scripts.

## Three distinct credentials (current implementation)

1. **Cloudflare Tunnel connector token:** solely starts `cloudflared` on Windows/in Docker. Get it from **Networking > Tunnels > [existing tunnel] > Add a replica > Docker**. Keep it in the ignored local `ops/model/docker/secrets/tunnel-token.txt`; it is NOT an HTTP authorization key.
2. **Cloudflare Access service token (Client ID + Client Secret):** authorizes Render backend requests to `https://ai.bfab.io`. Configure the Access self-hosted application's Service Auth policy and save both values only as Render backend secret environment variables.
3. **LM Studio API key:** the current backend **requires** this in addition to Access. Enable **Require Authentication** in LM Studio and set `MODEL_LOCAL_API_KEY` privately in the Render backend for ordinary shared-mode selection. In account-scoped personal mode, each authorized account supplies its own LM Studio key using the personal credential flow; no fallback to another user's key.

An earlier version of this document said no LM Studio key was required. That is **not true for the current backend implementation** (`backend/app/services/llm/__init__.py`, `backend/app/services/personal_llm.py` and `backend/app/services/llm/cloudflare_access.py`). Do not remove the Bearer token or disable origin authentication to resolve a 401. Never send any of these credentials to the frontend, GitHub, Supabase or chat. Cloudflare Tunnel alone provides transport, not authorization.

## A. Origin and connector

Use exactly one of these two origin configurations according to **where `cloudflared` actually runs**:

| Connector | LM Studio binding | Tunnel's HTTP service URL |
| --- | --- | --- |
| Native Windows `cloudflared` | Prefer `127.0.0.1:1234` | `http://localhost:1234` |
| Docker Desktop Linux container on Windows | Enable Serve on Local Network and LM Studio API authentication; restrict firewall/LAN access | `http://host.docker.internal:1234` |

Publish hostname `ai.bfab.io`; do **not** add `/v1` to the Cloudflare service URL. External PsychDeep model base is `https://ai.bfab.io/v1`. Do not publish port 1234 in the Docker Compose file or port-forward it on your router. For Docker mode, start LM Studio on Windows first, import the tunnel connector token using the clipboard script, then run `ops/model/docker/start.ps1`. The two connector modes have different `localhost` semantics: if a tunnel has replicas in both places, one route can fail. Verify other published hostnames before disabling an old Windows service or repointing a shared route; create a dedicated tunnel if necessary.

## B. Cloudflare Access (mandatory)

1. In Cloudflare Zero Trust create a dedicated **service token** for `psychdeep-api` and save Client ID/Secret in Render's backend secret environment.
2. Create an **Access self-hosted application** for hostname `ai.bfab.io` covering all `/v1/*` requests. Add **Service Auth > Include > Service Token > the dedicated token**. No Everyone/Bypass policy.
3. A request to `https://ai.bfab.io/v1/models` without the Access headers must **not** return model IDs. The Render backend sends `CF-Access-Client-Id` and `CF-Access-Client-Secret` plus `Authorization: Bearer <LM Studio API key>` to the upstream origin.
4. Rotate service token, LM key and connector token independently. Validate DNS delegation or a supported external-DNS partial setup. A Healthy tunnel does not prove DNS, origin reachability, LM authentication or model readiness.

Reference: https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/

## C. Render backend environment

The **existing** `psychdeep-api` backend service (not the web frontend) requires these values. Enter secret values through Render's private environment editor; placeholders below are NOT real keys:

```dotenv
MODEL_DEPLOYMENT_ALIAS=local-tunnel
MODEL_LOCAL_BASE_URL=https://ai.bfab.io/v1
MODEL_LOCAL_CF_ACCESS_REQUIRED=true
MODEL_LOCAL_CF_ACCESS_HOST=ai.bfab.io
MODEL_LOCAL_CF_ACCESS_CLIENT_ID=<ACCESS_CLIENT_ID>
MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET=<ACCESS_CLIENT_SECRET>
MODEL_LOCAL_API_KEY=<LM_STUDIO_API_KEY>
LLM_ALLOW_RUNTIME_OVERRIDE=true
```

Do not configure `TUNNEL_TOKEN`, `TUNNEL_SECRET` or `CF_API_TOKEN` in Render for this integration. Never put the Access secrets in the Docker container, browser, database or tracked configuration. Check `LLM_PERSONAL_MODE` before testing account-scoped credentials; each account must provide its own LM key when this mode is active.

## D. Configure in PsychDeep

Sign in as an authorized `admin_clinical`, select the OpenAI-compatible/local provider and set:

- Base endpoint: `https://ai.bfab.io/v1` (not `/models`, not `/chat/completions`).
- Chat/analysis model IDs: exact identifiers returned by the running LM Studio server (not a guessed model name).
- Use **Probar proveedor** with synthetic prompts; only deliberately save/activate once healthy. Do not silently fall back to Anthropic during an outage.

The browser must never receive backend tokens. Clinical prompts may traverse the cloud backend and Cloudflare to the Windows host; evaluate patient consent, processor/region, audit and log retention separately.

## Troubleshooting

- Token `illegal base64`: use complete **Add a replica > Docker** connector token (long `eyJ...` string), not the tunnel UUID/short secret/Access Client Secret. Use the included PowerShell clipboard import; never type it character by character.
- Tunnel DOWN: check Docker process and its logs, outbound network connectivity, and whether the correct dedicated connector is running.
- `502`: check LM Studio, firewall, and `host.docker.internal:1234` inside a Docker container. `localhost` in Docker refers to Docker itself.
- `401` from LM Studio: LM key missing or wrong; verify backend `MODEL_LOCAL_API_KEY` and personal credentials when applicable.
- `403`/Access login: verify Access app and Service Auth headers/credentials; do not disable Access.
- `404`: verify `/v1` on backend base URL and **no** `/v1` on origin route.
- `NXDOMAIN`: correct domain DNS/delegation; Docker and the tunnel token cannot create a missing record.

See the Docker README for preflight commands, build/run commands, tests and safe stop/recreate procedures.
