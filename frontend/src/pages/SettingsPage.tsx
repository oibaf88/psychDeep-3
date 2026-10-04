import { useEffect, useState } from "react";
import { api } from "../api";
import PsychDeepLoader from "../components/PsychDeepLoader";

type Provider = "anthropic" | "openai" | "openai_compatible";

interface PersonalStatus {
  configured: boolean;
  provider: Provider;
  max_tokens: number;
  timeout_seconds: number;
  local_available: boolean;
  lm_api_key_configured: boolean;
  anthropic_allowed: boolean;
  openai_allowed: boolean;
  local_llm_usable?: boolean;
}

const PROVIDER_LABEL: Record<Provider, string> = {
  openai_compatible: "Local",
  anthropic: "Anthropic",
  openai: "Codex / ChatGPT",
};

const endpoint = "/api/v1/settings/llm/personal";

export default function SettingsPage() {
  const [status, setStatus] = useState<PersonalStatus | null>(null);
  const [provider, setProvider] = useState<Provider>("openai_compatible");
  const [lmApiKey, setLmApiKey] = useState("");
  const [revokeLmKey, setRevokeLmKey] = useState(false);
  const [busy, setBusy] = useState<"" | "save" | "test" | "remove">("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.get<PersonalStatus>(endpoint)
      .then((next) => {
        setStatus(next);
        setProvider(next.provider);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  function chooseProvider(next: Provider) {
    setProvider(next);
    setError("");
    setMessage("");
  }

  async function save() {
    if (!status) return;
    setBusy("save");
    setError("");
    setMessage("");
    try {
      const lm_api_key = revokeLmKey ? "" : (lmApiKey.trim() || null);
      const next = await api.put<PersonalStatus>(endpoint, {
        provider,
        chat_model: "",
        analysis_model: "",
        copilot_model: "",
        max_tokens: status.max_tokens,
        timeout_seconds: status.timeout_seconds,
        lm_api_key,
      });
      setStatus(next);
      setProvider(next.provider);
      setLmApiKey("");
      setRevokeLmKey(false);
      setMessage("Conexión guardada. No se elige un modelo desde aquí.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function test() {
    setBusy("test");
    setError("");
    setMessage("");
    try {
      const result = await api.post<{ ok: boolean; detail: string }>(endpoint + "/test");
      if (result.ok) setMessage(result.detail);
      else setError(result.detail);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function remove() {
    if (!window.confirm("¿Eliminar la conexión guardada de esta cuenta de administración?")) return;
    setBusy("remove");
    setError("");
    setMessage("");
    try {
      const next = await api.del<PersonalStatus>(endpoint);
      setStatus(next);
      setProvider(next.provider);
      setLmApiKey("");
      setRevokeLmKey(false);
      setMessage("Se ha eliminado la conexión guardada.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy("");
    }
  }

  const local = provider === "openai_compatible";
  const openai = provider === "openai";
  const keyAvailable = Boolean((status?.lm_api_key_configured && !revokeLmKey) || lmApiKey.trim());
  const maySave = Boolean(status && (
    openai
      ? status.openai_allowed
      : provider === "anthropic"
        ? status.anthropic_allowed
        : status.local_available && status.local_llm_usable !== false && keyAvailable
  ));
  const mayTest = Boolean(status?.configured && (!local || (status.local_available && status.local_llm_usable !== false && status.lm_api_key_configured)));

  return (
    <div className="page">
      <h1>Mis modelos</h1>
      <p className="subtitle">
        Solo el administrador clínico conecta la inferencia y elige el proveedor: local, Anthropic o Codex / ChatGPT.
      </p>
      <section className="card">
        <h2>Conexión de inferencia</h2>
        {status && (
          <p className="info">
            {status.configured
              ? `Selección actual: ${PROVIDER_LABEL[status.provider] ?? status.provider}`
              : "Todavía no hay una conexión guardada."}
          </p>
        )}
        {status && !status.local_available && (
          <p className="warning" role="status">El acceso local todavía no está preparado en el servidor.</p>
        )}
        {status && (
          <>
            <label className="field">
              <span>Proveedor</span>
              <select value={provider} onChange={(event) => chooseProvider(event.target.value as Provider)}>
                <option value="openai_compatible">Local</option>
                <option value="anthropic" disabled={!status.anthropic_allowed}>Anthropic</option>
                <option value="openai" disabled={!status.openai_allowed}>Codex / ChatGPT</option>
              </select>
            </label>
            {local ? (
              <>
                <p className="info">
                  Local usa el modelo que tengas cargado en tu ordenador. Desde aquí no se elige ni se cambia de modelo.
                </p>
                <label className="field" htmlFor="personal-lm-api-key">
                  <span>API key de LM Studio</span>
                  <input
                    id="personal-lm-api-key"
                    type="password"
                    autoComplete="new-password"
                    value={lmApiKey}
                    disabled={busy !== "" || revokeLmKey}
                    placeholder={status.lm_api_key_configured ? "Configurada · deja vacío para conservar" : "Pega aquí tu API key"}
                    onChange={(event) => {
                      setLmApiKey(event.target.value);
                      setError("");
                      setMessage("");
                    }}
                  />
                  <span className="meta">
                    Estado: {status.lm_api_key_configured ? "configurada" : "no configurada"}. Se envía al backend y se guarda cifrada; no se mostrará de nuevo.
                  </span>
                </label>
                {status.lm_api_key_configured && (
                  <label className="field">
                    <span>
                      <input
                        type="checkbox"
                        checked={revokeLmKey}
                        disabled={busy !== ""}
                        onChange={(event) => {
                          setRevokeLmKey(event.target.checked);
                          setError("");
                        }}
                      />{" "}
                      Revocar mi API key al guardar
                    </span>
                  </label>
                )}
                {!keyAvailable && (
                  <p className="warning">Para conectar en local introduce la API key de LM Studio. La clave del túnel no sale del servidor.</p>
                )}
              </>
            ) : (
              <p className="info">
                {openai
                  ? "Codex / ChatGPT usa la API de OpenAI configurada en el servidor. La clave no sale del backend y no se elige un modelo desde aquí."
                  : "Anthropic usa la clave configurada en el servidor. No se elige un modelo desde aquí."}
              </p>
            )}
            <div className="alert-actions">
              <button disabled={busy !== "" || !maySave} onClick={save}>{busy === "save" ? "Guardando…" : "Guardar conexión"}</button>
              <button className="btn-secondary" disabled={busy !== "" || !mayTest} onClick={test}>{busy === "test" ? "Probando…" : "Probar conexión"}</button>
              <button className="btn-secondary" disabled={busy !== "" || !status.configured} onClick={remove}>Eliminar conexión</button>
            </div>
          </>
        )}
        {busy === "test" && <PsychDeepLoader size="sm" label="Probando la conexión…" />}
        {error && <p className="error" role="alert">{error}</p>}
        {message && <p className="info" role="status">{message}</p>}
        <p className="meta">Si el proveedor elegido no responde, no se envía información clínica a otro proveedor.</p>
      </section>
    </div>
  );
}
