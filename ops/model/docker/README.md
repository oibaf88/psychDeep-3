# PsychDeep: LM Studio on Windows 11 through a Dockerized Cloudflare Tunnel

This folder builds **only `cloudflared`**. LM Studio and its model stay installed and running on Windows; the product frontend/backend and clinical database remain on Render/Supabase. No inbound router rules or Docker `ports:` are needed.

```text
PsychDeep browser -> Render backend -> Cloudflare Access (ai.bfab.io)
  -> Cloudflare Tunnel -> cloudflared Docker container
  -> http://host.docker.internal:1234 -> LM Studio on Windows
```

## 1. Prepare Windows and LM Studio

- Start Docker Desktop in **Linux containers** mode. Check `docker info --format '{{.OSType}}'` reports `linux`.
- Start LM Studio's API server in Developer, port `1234`. Enable **Serve on Local Network** so a separate Docker container can access it via `host.docker.internal`. If you use the CLI instead of the GUI, stop the existing server first and run `lms server start --bind 0.0.0.0 --port 1234`.
- **Enable LM Studio's Require Authentication and generate an LM Studio API token.** This is important because network binding exposes port 1234 beyond Windows loopback. Keep Windows Firewall rules restrictive; never port-forward TCP/1234 or publish it from Docker. If LAN exposure is unacceptable, use the existing native Windows `cloudflared` connector with LM Studio bound to 127.0.0.1 instead of this Docker variant.
- The current backend code additionally requires an LM Studio key for the `local-tunnel` provider; the existing `docs/integrations/cloudflare-access-lm-studio.md` and `.env.example` descriptions of an Access-only/no-LM-token gateway are outdated for this code revision. Store the LM key as `MODEL_LOCAL_API_KEY` in **Render backend secrets**. In account-scoped personal mode (`LLM_PERSONAL_MODE`), each authorized account must additionally configure its own LM Studio key; check backend mode and intended account separation before activation. Do not put an LM key in this container.
- Local check: `Test-NetConnection 127.0.0.1 -Port 1234`. A `/v1/models` request without an LM key should now return 401, which is normal.

## 2. Save the existing tunnel connector token without typing it

1. Open Cloudflare dashboard > **Networking > Tunnels**, select the existing dedicated model tunnel, then **Add a replica** and choose Docker.
2. Copy the complete Docker command (or just the long `eyJ...` connector token) using the dashboard's Copy button. Do not copy the tunnel UUID, short tunnel secret, Access client secret, or a truncated value.
3. Open PowerShell in this folder and run:

   ```powershell
   .\save-token-from-clipboard.ps1
   ```

   The script extracts and validates the base64 JSON connector token and saves it as `secrets/tunnel-token.txt` without displaying it. To deliberately replace it after rotation use `./save-token-from-clipboard.ps1 -Replace`.

`secrets/` is ignored by Git, and `.dockerignore` excludes it from the build context. Docker Compose mounts this file read-only as a secret at `/run/secrets/tunnel-token`. The Docker image, Compose file, command line and Git repository contain no real token. The token must remain on your Windows machine; a tunnel connector token is **not** the HTTP authentication credential for PsychDeep.

## 3. Configure the existing Cloudflare route

In the model tunnel's **Published application routes** configure exactly:

| Setting | Value |
| --- | --- |
| Hostname | `ai.bfab.io` |
| Service type | `HTTP` |
| Service URL | `http://host.docker.internal:1234` |
| HTTP path | empty (do **not** append `/v1`) |

The hostname's public API base is `https://ai.bfab.io/v1`, but the tunnel's origin is HTTP and has no `/v1` suffix. `localhost:1234` in this route would mean the **cloudflared container**, not Windows. Changing an existing route changes it for **all replicas** of that tunnel; ensure the old Windows connector isn't needed for any other hostname and stop/disable it only when that is verified. If the tunnel carries other applications, make a separate dedicated tunnel rather than changing shared routes. Confirm `ai.bfab.io` DNS actually resolves and is routed to this tunnel; if Porkbun still hosts DNS, verify Cloudflare's supported partial/CNAME setup rather than assuming dashboard routing edits alone create DNS.

## 4. Protect the hostname with Cloudflare Access

Create or check the **self-hosted Access application** covering `ai.bfab.io` and all `/v1/*` paths. Add a **Service Auth** policy selecting a dedicated service token for `psychdeep-api`. Never create an Everyone or Bypass policy. Keep its Client ID and Client Secret in Render's backend secret environment, **not** this Docker container, GitHub, Supabase, or frontend.

Required Render backend variables (real values entered privately in the Render dashboard):

```dotenv
MODEL_DEPLOYMENT_ALIAS=local-tunnel
MODEL_LOCAL_BASE_URL=https://ai.bfab.io/v1
MODEL_LOCAL_CF_ACCESS_REQUIRED=true
MODEL_LOCAL_CF_ACCESS_HOST=ai.bfab.io
MODEL_LOCAL_CF_ACCESS_CLIENT_ID=<service-token-client-id>
MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET=<service-token-client-secret>
MODEL_LOCAL_API_KEY=<lm-studio-api-key>
```

The three credentials are distinct: (1) connector token runs `cloudflared` and stays on Windows; (2) Cloudflare Access Client ID/Secret permit backend requests through the edge; (3) LM Studio API key authenticates those requests at the Windows origin. The backend's current Cloudflare Access adapter sends both the Access headers and the LM Studio Bearer token. Check account-scoped mode separately; do not share one user's personal LM key across accounts without a deliberate design decision.

## 5. Build, create and run the container

From PowerShell in this directory:

```powershell
.\start.ps1
```

Equivalently, from the repo root:

```powershell
docker compose -f ops/model/docker/compose.yaml config --quiet
docker compose -f ops/model/docker/compose.yaml up -d --build
docker compose -f ops/model/docker/compose.yaml ps
docker compose -f ops/model/docker/compose.yaml logs --tail=50 cloudflared
```

The image is named `psychdeep-cloudflared:local`, the container `psychdeep-lmstudio-tunnel`, with `restart: unless-stopped` and **zero published ports**. The LM Studio GUI/API must remain running; Docker does not launch it.

## 6. Verify every hop (use synthetic prompts only)

1. Windows LM server listening: `Test-NetConnection 127.0.0.1 -Port 1234`.
2. From a disposable Docker container, test host routing without sending an API key:

   ```powershell
   docker run --rm curlimages/curl:latest -sS -o /dev/null -w '%{http_code}' http://host.docker.internal:1234/v1/models
   ```

   HTTP `401` proves LM Studio is reachable but authentication is required; `200` means reachable but check why authentication is off; `000` or a connection error means wrong bind/firewall/port.
3. Docker: `docker compose -f ops/model/docker/compose.yaml ps` must show `Up`; inspect `logs --tail=50 cloudflared` for a registered connection. A running container is **not** proof the model origin works.
4. Cloudflare dashboard: tunnel connection should be **Healthy** and DNS should resolve `ai.bfab.io`.
5. Unauthenticated external check: `curl.exe -i https://ai.bfab.io/v1/models` must **not** reveal a model list (expect denial/login). Never turn off Access to make a 403 disappear.
6. Render backend: check that all Access + LM Studio secret values are configured and the model name is an **exact model ID** from LM Studio. In PsychDeep, an authorized `admin_clinical` can use **Probar proveedor** and then deliberately activate the configured provider. No automatic switch from local to Anthropic should occur.

## Troubleshooting

- `Provided tunnel token is not valid (illegal base64 ...)`: a UUID, short secret or truncated string was saved; copy **Add a replica > Docker** again, run `save-token-from-clipboard.ps1 -Replace` and restart Docker Compose. Never paste the token into chat or commit it.
- Tunnel `DOWN` / container exiting: check `docker compose ... logs`; Docker Desktop must be running, the connector token valid, and outbound connectivity allowed. Do not repeatedly run the old Windows service and the Docker replica with conflicting origin configurations.
- Cloudflare `502`: the edge/tunnel cannot reach LM Studio; check `host.docker.internal`, bind settings, firewall, and the Docker-origin check above.
- Origin `401`: LM Studio API key missing/invalid; ensure Require Authentication is on and the correct key is configured in Render (and for users when personal mode is enabled).
- Cloudflare `403` / Access login: confirm the Service Auth policy and both Access headers/credentials are present on backend requests. The tunnel token is NOT an Access service token.
- `NXDOMAIN`: fix the DNS record/delegation. The container cannot repair DNS.
- `404`: confirm public base URL `/v1`, the route service URL without `/v1`, and exact model IDs.
- To stop only this connector: `docker compose -f ops/model/docker/compose.yaml stop`; to recreate after token rotation: `docker compose -f ops/model/docker/compose.yaml up -d --force-recreate`. Avoid `down -v` or deleting volumes/images without need.

### Reference documentation

- Cloudflare: https://developers.cloudflare.com/tunnel/get-started/ and https://developers.cloudflare.com/tunnel/reference/run-parameters/
- Cloudflare service tokens: https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/
- Docker Windows host routing: https://docs.docker.com/desktop/features/networking/networking-how-tos/
- LM Studio network/auth settings: https://lmstudio.ai/docs/developer/core/server/serve-on-network and https://lmstudio.ai/docs/developer/core/server/settings
