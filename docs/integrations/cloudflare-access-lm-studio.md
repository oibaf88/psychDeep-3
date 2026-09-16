# LM Studio via Cloudflare Tunnel + Access (without LM Studio API tokens)

This integration uses **three distinct concepts**. Do not interchange them:

1. **Cloudflare Tunnel connector token/secret:** used ONLY by `cloudflared` on the Windows computer to connect `workflare` to Cloudflare. It is NOT an HTTP request credential. Do not put it in PsychDeep, Render, GitHub or the browser.
2. **Cloudflare Access service token:** its **Client ID and Client Secret** authenticate the Render backend's HTTP requests to `https://ai.bfab.io`. These are the only model-gateway credentials required in this configuration.
3. **LM Studio API key:** not required for this setup. Disable LM Studio's optional API authentication; keep the HTTP server bound to localhost and protect the *public route* using Access. The provider deliberately does not send an `Authorization: Bearer` header in Access mode even if a legacy model API key is still configured in Render.

## A. Start the connector and model on Windows

- Install/run `workflare` using Cloudflare's connector token in the local `cloudflared` Windows service. Verify the tunnel is `Healthy` in Cloudflare.
- In LM Studio, load the intended model, start the server on `127.0.0.1:1234`, and leave its optional API authentication disabled for this Access-only arrangement. Do not bind to `0.0.0.0` or port-forward 1234.
- Verify locally with `Invoke-RestMethod http://localhost:1234/v1/models`. Copy an exact model `id` from `data`.
- In Cloudflare Tunnel, publish hostname `ai.bfab.io` to service `http://localhost:1234` (without `/v1`). Confirm the hostname is actually routed to `workflare` and that the DNS is delegated correctly. Do not assume a configured route has working DNS.

## B. Require Cloudflare Access for the hostname

1. In Cloudflare Zero Trust, create an **Access service token** dedicated to `psychdeep-api`; save the Client ID and Client Secret securely. This is NOT the connector token that starts `cloudflared`.
2. Create a **self-hosted Access application** for `ai.bfab.io` (covering the model API paths). Add a **Service Auth** policy using the service token selector and this dedicated token. Do not add an Everyone/Bypass policy that would expose the model endpoint publicly.
3. Before continuing, an unauthenticated request to `https://ai.bfab.io/v1/models` must NOT return a model list. An authenticated request containing `CF-Access-Client-Id` and `CF-Access-Client-Secret` must return the list. A browser redirect or 403 on an unauthenticated request is expected.
4. Rotate the service token independently of the tunnel connector token. Keep the connector token only in `cloudflared` and the Access credentials only in the Render backend secret environment.

Cloudflare documentation: https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/ and https://developers.cloudflare.com/cloudflare-one/access-controls/policies/

## C. Set backend environment on Render

Open the existing `psychdeep-api` **backend** service (not `psychdeep-web`) → Environment. Configure:

```dotenv
MODEL_DEPLOYMENT_ALIAS=local-tunnel
MODEL_LOCAL_BASE_URL=https://ai.bfab.io/v1
MODEL_LOCAL_CF_ACCESS_REQUIRED=true
MODEL_LOCAL_CF_ACCESS_HOST=ai.bfab.io
MODEL_LOCAL_CF_ACCESS_CLIENT_ID=<ACCESS_CLIENT_ID>
MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET=<ACCESS_CLIENT_SECRET>
LLM_ALLOW_RUNTIME_OVERRIDE=true
```

Enter the Client ID and Client Secret through Render's secret environment editor. Do not paste them into GitHub, commit them in `.env.example`, or enter them in the PsychDeep browser. Remove `MODEL_LOCAL_API_KEY` and `LLM_OPENAI_COMPATIBLE_API_KEY` from the environment if no other model integration requires them: neither is needed for this gateway, and the new adapter ignores both in Access mode. Do not configure `TUNNEL_TOKEN`, `TUNNEL_SECRET`, or `CF_API_TOKEN` in Render for this feature.

`MODEL_LOCAL_CF_ACCESS_REQUIRED=true` is **fail-closed**: absent or partial Access credentials cause local-model requests to fail rather than silently falling back to a direct, unauthenticated tunnel. The integration pins credentials to precisely `https://ai.bfab.io` over standard TLS port 443. An admin changing the runtime endpoint to another host cannot send these secrets to it.

## D. Configure the model in PsychDeep

Sign in as `admin_clinical` → Modelos → choose **Modelo local o propio / OpenAI-compatible**:

- Endpoint: `https://ai.bfab.io/v1`
- Chat and analysis model IDs: exact IDs returned by LM Studio's `/v1/models`.
- Copilot: leave blank to inherit chat if appropriate.
- Run **Probar proveedor**. If successful, choose **Guardar y activar**.

Only the backend sends the Access headers; the browser never receives the Client ID or Client Secret. A connector-status `Healthy` alone does not prove LM Studio is loaded, reachable, or authorized.

## Troubleshooting

- Tunnel DOWN: start/repair the Windows `cloudflared` service; do not send the tunnel connector token as an HTTP header.
- 502: Cloudflare can reach the tunnel but `localhost:1234` is offline or mapped incorrectly.
- 403 / Access login: check the self-hosted application hostname, Service Auth policy and service token secrets.
- 401 from origin: LM Studio API authentication is still enabled or another upstream mechanism is rejecting the request.
- 404: check the hostname route and `/v1` base URL; Cloudflare's origin service must be the root `http://localhost:1234`.
- Config failure before HTTP: verify `MODEL_LOCAL_CF_ACCESS_REQUIRED`, hostname match, and both Access secret variables.

Use synthetic prompts only during acceptance testing. Cloudflare Tunnel does not mean clinical data remain exclusively on the local machine: the cloud API sends inference requests through Cloudflare to the operator's PC. Minimize LM Studio request/prompt logging, and validate applicable clinical privacy and consent requirements independently.
