"""Read the model ids LM Studio is actually serving through the tunnel.

PsychDeep must not invent a model id. The identifier sent to chat
completions is either one the account chose from this catalog or, when
nothing was chosen, the single model LM Studio reports as loaded.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.services.llm.openai_compatible import API_USER_AGENT

_CACHE_SECONDS = 20.0
_cache: dict[str, tuple[float, "Catalog"]] = {}
# Historical library/blueprint default. It is not a configured choice unless
# the live LM Studio catalog actually advertises it.
UNCONFIRMED_DEFAULTS = frozenset({"gemma-2-2b-it"})


@dataclass(frozen=True)
class LocalModel:
    id: str
    loaded: bool


@dataclass(frozen=True)
class Catalog:
    models: tuple[LocalModel, ...]
    reachable: bool


def clear_catalog_cache() -> None:
    _cache.clear()


def select_model(requested: str, catalog: Catalog) -> str:
    """Pick an id the running server advertised.

    An unreachable catalog keeps the requested id: a tunnel blip must not
    erase a choice. A reachable catalog never returns an id the server did
    not list, so a retired default cannot be sent after the loaded model
    changes.
    """
    requested = (requested or "").strip()
    if not catalog.reachable:
        if requested in UNCONFIRMED_DEFAULTS:
            return ""
        return requested
    ids = [model.id for model in catalog.models if model.id]
    if not ids:
        return requested
    if requested in ids:
        return requested
    loaded = [model.id for model in catalog.models if model.loaded and model.id]
    if len(loaded) == 1:
        return loaded[0]
    if len(ids) == 1:
        return ids[0]
    return ""


def fetch_catalog(
    *,
    endpoint: str,
    api_key: str,
    access_client_id: str,
    access_client_secret: str,
    access_hostname: str,
) -> Catalog:
    """GET the approved tunnel only. Failures are an empty unreachable catalog."""
    parsed = urlsplit((endpoint or "").strip())
    host = (access_hostname or "").strip().lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != host
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or not api_key.strip()
        or not access_client_id.strip()
        or not access_client_secret.strip()
        or not host
    ):
        return Catalog((), False)

    now = time.monotonic()
    cached = _cache.get(host)
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]

    origin = f"https://{host}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key.strip()}",
        "CF-Access-Client-Id": access_client_id.strip(),
        "CF-Access-Client-Secret": access_client_secret.strip(),
        "User-Agent": API_USER_AGENT,
    }
    timeout = httpx.Timeout(8.0, connect=5.0)
    discovered: dict[str, LocalModel] = {}
    saw_json = False
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            for path in ("/api/v0/models", "/v1/models"):
                response = client.get(f"{origin}{path}", headers=headers)
                content_type = (response.headers.get("content-type") or "").lower()
                if response.status_code != 200 or "json" not in content_type:
                    continue
                try:
                    payload = response.json()
                except ValueError:
                    continue
                saw_json = True
                for model in _models_from_payload(payload):
                    current = discovered.get(model.id)
                    if current is None or (model.loaded and not current.loaded):
                        discovered[model.id] = model
    except httpx.HTTPError:
        return Catalog((), False)

    if not saw_json:
        return Catalog((), False)
    catalog = Catalog(tuple(discovered.values()), True)
    _cache[host] = (now, catalog)
    return catalog


def _models_from_payload(payload: object) -> list[LocalModel]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        data = payload.get("models")
    if not isinstance(data, list):
        return []
    found: list[LocalModel] = []
    for item in data[:50]:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id or len(model_id) > 192 or any(char in model_id for char in "\r\n"):
            continue
        state = str(item.get("state") or "").strip().lower()
        loaded = bool(item.get("loaded")) or state == "loaded"
        found.append(LocalModel(model_id, loaded))
    return found
