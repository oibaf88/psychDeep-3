import { useEffect, useState } from "react";
import { api } from "../api";

type Provider = "anthropic" | "openai_compatible";
interface PersonalStatus {
  configured: boolean;
  provider: Provider;
  chat_model: string;
  analysis_model: string;
  copilot_model: string;
  default_local_chat_model: string;
  default_local_analysis_model: string;
  max_tokens: number;
  timeout_seconds: number;
  local_available: boolean;
  lm_api_key_configured: boolean;
  anthropic_allowed: boolean;
  local_llm_approved?: boolean;
  local_llm_usable?: boolean;
  local_llm_access?: "manager" | "approved" | "pending";
}
interface FormState {
  provider: Provider;
  chat_model: string;
  analysis_model: string;
  copilot_model: string;
  max_tokens: number;
  timeout_seconds: number;
}

const endpoint = "/api/v1/settings/llm/personal";
function fromStatus(status: PersonalStatus): FormState {
  return {
    provider: status.provider,
    chat_model: status.chat_model,
    analysis_model: status.analysis_model,
    copilot_model: status.copilot_model,
    max_tokens: status.max_tokens,
    timeout_seconds: status.timeout_seconds,
  };
}

export default function SettingsPage() {
  const [status, setStatus] = useState<PersonalStatus | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [lmApiKey, setLmApiKey] = useState("");
  const [revokeLmKey, setRevokeLmKey] = useState(false);
  const [busy, setBusy] = useState<"" | "save" | "test" | "remove">("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.get<PersonalStatus>(endpoint)
      .then((next) => { setStatus(next); setForm(fromStatus(next)); })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  function patch(changes: Partial<FormState>) {
    setForm((current) => current ? { ...current, ...changes } : current);
    setError(""); setMessage("");
  }

  function chooseProvider(provider: Provider) {
    if (!form || !status) return;
    if (provider === "anthropic") {
      patch({ provider, chat_model: "claude-3-5-sonnet-20240620", analysis_model: "claude-3-5-sonnet-20240620", copilot_model: "" });
    } else {
      patch({ provider, chat_model: status.default_local_chat_model, analysis_model: status.default_local_analysis_model, copilot_model: "" });
    }
  }

  async function save() {
    if (!form) return;
    setBusy("save"); setError(""); setMessage("");
    try {
      // null preserves encrypted ciphertext; "" revokes; nonempty rotates.
      const lm_api_key = revokeLmKey ? "" : (lmApiKey.trim() || null);
      const next = await api.put<PersonalStatus>(endpoint, { ...form, lm_api_key });
      setStatus(next); setForm(fromStatus(next));
      setLmApiKey(""); setRevokeLmKey(false);
      setMessage("Preferencia y credenciales personales guardadas. No se ha modificado ninguna otra cuenta.");
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(""); }
  }

  async function test() {
    setBusy("test"); setError(""); setMessage("");
    try {
      const result = await api.post<{ ok: boolean; detail: string }>(endpoint + "/test");
      if (result.ok) setMessage(result.detail);
      else setError(result.detail);
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(""); }
  }

  async function remove() {
    if (!window.confirm("¿Eliminar tu selección y tu API key guardada? Solo afecta a tu cuenta.")) return;
    setBusy("remove"); setError(""); setMessage("");
    try {
      const next = await api.del<PersonalStatus>(endpoint);
      setStatus(next); setForm(fromStatus(next));
      setLmApiKey(""); setRevokeLmKey(false);
      setMessage("Se ha eliminado la configuración personal. Necesitarás introducir tu API key para volver a usar LM Studio.");
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(""); }
  }

  const local = form?.provider === "openai_compatible";
  const managerApproved = status?.local_llm_usable !== false;
  const keyAvailable = Boolean((status?.lm_api_key_configured && !revokeLmKey) || lmApiKey.trim());
  const maySave = Boolean(form && (!local || (status?.local_available && managerApproved && keyAvailable)));
  const mayTest = Boolean(status?.configured && (!local || (status?.local_available && managerApproved && status?.lm_api_key_configured)));

  return (
    <div className="page">
      <h1>Mis modelos</h1>
      <p className="subtitle">Cada cuenta elige su proveedor y guarda exclusivamente su propia API key de LM Studio. El modelo local exige sesión en PsychDeep y autorización del administrador clínico.</p>
      <section className="card">
        <h2>Proveedor de inferencia personal</h2>
        {status && <p className="info">{status.configured ? `Selección actual: ${status.provider === "anthropic" ? "Anthropic" : "LM Studio"}` : "Todavía no has completado tu configuración personal."}</p>}
        {status && !status.local_available && <p className="warning" role="status">El acceso al modelo local todavía no está preparado en el servidor. Contacta con la administración.</p>}
        {status && status.local_llm_usable === false && <p className="warning" role="status">Tu cuenta está conectada, pero el administrador clínico aún no ha autorizado el uso del modelo local (LM Studio).</p>}
        {form && <>
          <label className="field"><span>Proveedor</span>
            <select value={form.provider} onChange={(event) => chooseProvider(event.target.value as Provider)}>
              <option value="openai_compatible">LM Studio</option>
              <option value="anthropic" disabled={!status?.anthropic_allowed}>Anthropic / Claude</option>
            </select>
          </label>
          {local ? <>
            <p className="info">Modelos disponibles: conversación <code>{status?.default_local_chat_model || "pendiente"}</code>; análisis <code>{status?.default_local_analysis_model || "pendiente"}</code>.</p>
            <label className="field" htmlFor="personal-lm-api-key">
              <span>Tu API key de LM Studio</span>
              <input id="personal-lm-api-key" type="password" autoComplete="new-password"
                value={lmApiKey} disabled={busy !== "" || revokeLmKey}
                placeholder={status?.lm_api_key_configured ? "Configurada · deja vacío para conservar" : "Pega aquí tu API key"}
                onChange={(event) => { setLmApiKey(event.target.value); setError(""); setMessage(""); }} />
              <span className="meta">Estado: {status?.lm_api_key_configured ? "configurada" : "no configurada"}. Se envía al backend y se guarda cifrada; no se mostrará de nuevo.</span>
            </label>
            {status?.lm_api_key_configured && <label className="field">
              <span><input type="checkbox" checked={revokeLmKey} disabled={busy !== ""}
                onChange={(event) => { setRevokeLmKey(event.target.checked); setError(""); }} /> Revocar mi API key al guardar</span>
            </label>}
            {!keyAvailable && <p className="warning">Para activar LM Studio introduce tu API key personal. La clave del túnel no se comparte con los usuarios.</p>}
          </> : <div className="field-row">
            <label className="field"><span>Modelo de conversación</span><input value={form.chat_model} onChange={(event) => patch({ chat_model: event.target.value })} /></label>
            <label className="field"><span>Modelo de análisis</span><input value={form.analysis_model} onChange={(event) => patch({ analysis_model: event.target.value })} /></label>
          </div>}
          {!local && <label className="field"><span>Modelo de copiloto (vacío = conversación)</span><input value={form.copilot_model} onChange={(event) => patch({ copilot_model: event.target.value })} /></label>}
          <div className="field-row">
            <label className="field"><span>Máximo de tokens</span><input type="number" min={256} max={32768} value={form.max_tokens} onChange={(event) => patch({ max_tokens: Number(event.target.value) })} /></label>
            <label className="field"><span>Timeout (s)</span><input type="number" min={5} max={5000} value={form.timeout_seconds} onChange={(event) => patch({ timeout_seconds: Number(event.target.value) })} /></label>
          </div>
          <div className="alert-actions">
            <button disabled={busy !== "" || !maySave} onClick={save}>{busy === "save" ? "Guardando…" : "Guardar mi configuración"}</button>
            <button className="btn-secondary" disabled={busy !== "" || !mayTest} onClick={test}>{busy === "test" ? "Probando…" : "Probar mi conexión"}</button>
            <button className="btn-secondary" disabled={busy !== "" || !status?.configured} onClick={remove}>Eliminar mi configuración</button>
          </div>
        </>}
        {error && <p className="error" role="alert">{error}</p>}
        {message && <p className="info" role="status">{message}</p>}
        <p className="meta">La selección de tu cuenta no afecta a las demás. Si el modelo falla, no se envía información clínica automáticamente a otro proveedor.</p>
      </section>
    </div>
  );
}
