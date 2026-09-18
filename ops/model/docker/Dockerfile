# LM Studio itself runs on the Windows host. This image is ONLY the tunnel client.
# Update/review the base image periodically and pin its digest for production.
FROM cloudflare/cloudflared:latest

LABEL org.opencontainers.image.title="PsychDeep LM Studio Cloudflare Tunnel" \
      org.opencontainers.image.description="Inference-only outbound tunnel connector; no application code or model weights"

# The upstream image supplies its own non-root user and cloudflared ENTRYPOINT.
# Compose provides arguments and mounts the connector token at runtime.
