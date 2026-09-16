import { useEffect, useState } from "react";
import { api, clearLegacyApiBaseOverride, getApiBase, getLegacyApiBaseOverride } from "../api";
import { useAuth } from "../auth/AuthContext";

type Provider = "anthropic" | "openai_compatible";
interface PersonalStatus {
  configured: boolean;
  provider: Provider;
  base_url: string;
  chat_model: string;
  analysis_model: string;
  copilot_model: string;
  max_tokens: number;
  timeout_seconds: number;
  local_available: boolean;
  anthropic_allowed: boolean;
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
  const { user } = useAuth();
  const isAdmin = user?.role === "admin_clinical";
  const [status, setStatus] = useState<PersonalStatus | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [busy, setBusy] = useState<"" | "save" | "test" | "remove">("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (getLegacyApiBaseOverride()) clearLegacyApiBaseOverride();
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
      patch({ provider, chat_model: "claude-opus-5", analysis_model: "claude-opus-5", copilot_model: "" });
    } else {
      patch({ provider, chat_model: status.provider === "openai_compatible" ? status.chat_model : "", analysis_model: status.provider === "openai_compatible" ? status.analysis_model : "", copilot_model: "" });
    }
  }

  async function save() {
    if (!form) return;
    setBusy("save"); setError(""); setMessage("");
    try {
      const next = await api.put<PersonalStatus>(endpoint, form);
      setStatus(next); setForm(fromStatus(next));
      setMessage("Preferencia guardada. Las credenciales compartidas no se han modificado.");
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
    if (!window.confirm("¿Restaurar la selección local predeterminada de tu cuenta?")) return;
    setBusy("remove"); setError(""); setMessage("");
    try {
      const next = await api.del<PersonalStatus>(endpoint);
      setStatus(next); setForm(fromStatus(next));
      setMessage("Restaurado el proveedor predeterminado de tu cuenta.");
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(""); }
  }

  return (
    <div className="page">
      <h1>Mis modelos</h1>
      <p className="subtitle">Tu cuenta puede usar el modelo local sin introducir ninguna clave. El administrador configura el acceso una sola vez en Render.</p>
      <section className="card">
        <h2>API de PsychDeep</h2>
        <p><code>{getApiBase() || "mismo origen"}</code></p>
        <p className="meta">El token de cloudflared permanece en Windows. Las credenciales de Cloudflare Access y LM Studio solo las conoce el backend de Render.</p>
      </section>
      {isAdmin && <section className="card">
        <h2>Administración del gateway compartido</h2>
        <p>Configura una única vez en <a href="https://dashboard.render.com/" target="_blank" rel="noopener noreferrer">Render → psychdeep-api → Environment</a> los siguientes valores. No los copies en GitHub ni en variables VITE_* del frontend.</p>
        <p><code>MODEL_LOCAL_BASE_URL</code> = <code>https://ai.bfab.io/v1</code></p>
        <p><code>MODEL_LOCAL_CF_ACCESS_HOST</code> = <code>ai.bfab.io</code></p>
        <p><code>MODEL_LOCAL_CF_ACCESS_REQUIRED</code> = <code>true</code></p>
        <p><code>MODEL_LOCAL_CF_ACCESS_CLIENT_ID</code> y <code>MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET</code> = Service Token autorizado por la política Service Auth.</p>
        <p><code>MODEL_LOCAL_API_KEY</code> = un único token de inferencia de LM Studio. Mantén activado «Require Authentication» en LM Studio.</p>
        <p><code>MODEL_LOCAL_CHAT_MODEL</code> y <code>MODEL_LOCAL_ANALYSIS_MODEL</code> = IDs exactos de los modelos cargados.</p>
        <p><code>LLM_PERSONAL_MODE</code> = <code>true</code>, solo después de verificar la configuración y el despliegue.</p>
        <p className="meta">No cambies <code>LLM_USER_CREDENTIALS_KEY</code>: protege credenciales de la configuración anterior hasta su retirada controlada.</p>
      </section>}
      <section className="card">
        <h2>Proveedor de inferencia personal</h2>
        {status && <p className="info">{status.configured ? `Selección actual: ${status.provider === "anthropic" ? "Anthropic" : "LM Studio"}` : "Selección predeterminada: LM Studio compartido."}</p>}
        {status && !status.local_available && <p className="warning" role="status">El gateway local aún no está configurado por completo en Render. El administrador debe completar las dos autenticaciones antes de que pueda utilizarse.</p>}
        {status?.local_available && <p className="info">Gateway configurado en Render. No necesitas ninguna API key personal.</p>}
        {form && <>
          <label className="field"><span>Proveedor</span>
            <select value={form.provider} onChange={(event) => chooseProvider(event.target.value as Provider)}>
              <option value="openai_compatible">LM Studio compartido</option>
              <option value="anthropic" disabled={!status?.anthropic_allowed}>Anthropic / Claude</option>
            </select>
          </label>
          <div className="field-row">
            <label className="field"><span>Modelo de conversación</span><input value={form.chat_model} onChange={(event) => patch({ chat_model: event.target.value })} /></label>
            <label className="field"><span>Modelo de análisis</span><input value={form.analysis_model} onChange={(event) => patch({ analysis_model: event.target.value })} /></label>
          </div>
          <div className="field-row">
            <label className="field"><span>Copiloto (vacío = conversación)</span><input value={form.copilot_model} onChange={(event) => patch({ copilot_model: event.target.value })} /></label>
            <label className="field"><span>Máximo de tokens</span><input type="number" min={256} max={32768} value={form.max_tokens} onChange={(event) => patch({ max_tokens: Number(event.target.value) })} /></label>
            <label className="field"><span>Timeout (s)</span><input type="number" min={5} max={5000} value={form.timeout_seconds} onChange={(event) => patch({ timeout_seconds: Number(event.target.value) })} /></label>
          </div>
          <div className="alert-actions">
            <button disabled={busy !== "" || (form.provider === "openai_compatible" && !status?.local_available)} onClick={save}>{busy === "save" ? "Guardando…" : "Guardar mi preferencia"}</button>
            <button className="btn-secondary" disabled={busy !== "" || (form.provider === "openai_compatible" && !status?.local_available)} onClick={test}>{busy === "test" ? "Probando…" : "Probar mi conexión"}</button>
            <button className="btn-secondary" disabled={busy !== "" || !status?.configured} onClick={remove}>Restaurar valor predeterminado</button>
          </div>
        </>}
        {error && <p className="error" role="alert">{error}</p>}
        {message && <p className="info" role="status">{message}</p>}
        <p className="meta">La elección de una cuenta no cambia las demás. Si el modelo elegido falla, no se enviará contenido clínico automáticamente a otro proveedor.</p>
      </section>
    </div>
  );
}
