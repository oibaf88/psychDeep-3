import { useEffect, useState } from "react";
import { api, clearLegacyApiBaseOverride, getApiBase, getLegacyApiBaseOverride } from "../api";

type Provider = "anthropic" | "openai_compatible";
type Credential = "lm_api_key" | "cf_client_id" | "cf_client_secret";

interface PersonalStatus {
  configured: boolean;
  provider: Provider;
  base_url: string;
  chat_model: string;
  analysis_model: string;
  copilot_model: string;
  max_tokens: number;
  timeout_seconds: number;
  lm_api_key_configured: boolean;
  cf_client_id_configured: boolean;
  cf_client_secret_configured: boolean;
  anthropic_allowed: boolean;
}

interface FormState {
  provider: Provider;
  base_url: string;
  chat_model: string;
  analysis_model: string;
  copilot_model: string;
  max_tokens: number;
  timeout_seconds: number;
}

const endpoint = "/api/v1/settings/llm/personal";
const credentialFields: { key: Credential; title: string; hint: string; status: keyof PersonalStatus }[] = [
  { key: "cf_client_id", title: "Cloudflare Access · Client ID", hint: "Service Token individual, no es el token de cloudflared.", status: "cf_client_id_configured" },
  { key: "cf_client_secret", title: "Cloudflare Access · Client Secret", hint: "Se envía exclusivamente al backend para su almacenamiento cifrado.", status: "cf_client_secret_configured" },
  { key: "lm_api_key", title: "LM Studio · API token", hint: "Token propio que LM Studio valida después de Cloudflare Access.", status: "lm_api_key_configured" },
];

function fromStatus(status: PersonalStatus): FormState {
  return {
    provider: status.provider,
    base_url: status.base_url || "https://ai.bfab.io/v1",
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
  const [secrets, setSecrets] = useState<Record<Credential, string>>({ cf_client_id: "", cf_client_secret: "", lm_api_key: "" });
  const [clear, setClear] = useState<Record<Credential, boolean>>({ cf_client_id: false, cf_client_secret: false, lm_api_key: false });
  const [busy, setBusy] = useState<"" | "save" | "test" | "remove">("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (getLegacyApiBaseOverride()) clearLegacyApiBaseOverride();
    api.get<PersonalStatus>(endpoint)
      .then((value) => { setStatus(value); setForm(fromStatus(value)); })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  function patch(changes: Partial<FormState>) {
    setForm((current) => current ? { ...current, ...changes } : current);
    setError(""); setMessage("");
  }

  function chooseProvider(provider: Provider) {
    if (!form) return;
    if (provider === "anthropic") {
      patch({ provider, chat_model: "claude-opus-5", analysis_model: "claude-opus-5", copilot_model: "" });
    } else {
      const model = status?.provider === "openai_compatible" ? status.chat_model : "";
      patch({ provider, chat_model: model, analysis_model: model, copilot_model: "", base_url: status?.base_url || "https://ai.bfab.io/v1" });
    }
  }

  function credentialValue(key: Credential): string | null {
    if (clear[key]) return "";
    return secrets[key].trim() || null; // Null means preserve an already encrypted value.
  }

  async function save() {
    if (!form) return;
    setBusy("save"); setError(""); setMessage("");
    try {
      const next = await api.put<PersonalStatus>(endpoint, {
        ...form,
        lm_api_key: credentialValue("lm_api_key"),
        cf_client_id: credentialValue("cf_client_id"),
        cf_client_secret: credentialValue("cf_client_secret"),
      });
      setStatus(next); setForm(fromStatus(next));
      // Never persist secrets in browser storage; clear them immediately after a save.
      setSecrets({ cf_client_id: "", cf_client_secret: "", lm_api_key: "" });
      setClear({ cf_client_id: false, cf_client_secret: false, lm_api_key: false });
      setMessage("Preferencia personal guardada. No se han modificado otras cuentas.");
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
    if (!window.confirm("¿Eliminar tu selección y tus credenciales de modelos? No afecta a otros usuarios.")) return;
    setBusy("remove"); setError(""); setMessage("");
    try {
      const next = await api.del<PersonalStatus>(endpoint);
      setStatus(next); setForm(fromStatus(next));
      setSecrets({ cf_client_id: "", cf_client_secret: "", lm_api_key: "" });
      setClear({ cf_client_id: false, cf_client_secret: false, lm_api_key: false });
      setMessage("Configuración personal eliminada.");
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(""); }
  }

  return (
    <div className="page">
      <h1>Mis modelos</h1>
      <p className="subtitle">Cada cuenta decide qué proveedor utilizar y administra exclusivamente sus propias credenciales.</p>
      <section className="card">
        <h2>API de PsychDeep</h2>
        <p><code>{getApiBase() || "mismo origen"}</code></p>
        <p className="meta">Las credenciales del túnel cloudflared se mantienen en el ordenador. Aquí solo se aceptan las credenciales de Cloudflare Access y LM Studio.</p>
      </section>
      <section className="card">
        <h2>Proveedor de inferencia personal</h2>
        {status && <p className="info">{status.configured ? `Selección actual: ${status.provider === "anthropic" ? "Anthropic" : "LM Studio"}` : "Todavía no has configurado un proveedor personal."}</p>}
        {form && <>
          <label className="field"><span>Proveedor</span>
            <select value={form.provider} onChange={(event) => chooseProvider(event.target.value as Provider)}>
              <option value="anthropic" disabled={!status?.anthropic_allowed}>Anthropic / Claude</option>
              <option value="openai_compatible">LM Studio mediante Cloudflare Access</option>
            </select>
          </label>
          {form.provider === "openai_compatible" ? <>
            <label className="field"><span>URL del túnel autorizada</span>
              <input type="url" value={form.base_url} onChange={(event) => patch({ base_url: event.target.value })} placeholder="https://ai.bfab.io/v1" autoComplete="off" />
              <span className="meta">El servidor solo acepta el hostname autorizado en Render; nunca URLs arbitrarias.</span>
            </label>
            {credentialFields.map(({ key, title, hint, status: statusField }) => (
              <div className="field" key={key}>
                <label htmlFor={key}>{title}</label>
                <input id={key} type="password" value={secrets[key]} autoComplete="new-password"
                  disabled={clear[key] || busy !== ""} placeholder={status?.[statusField] ? "Configurado · dejar vacío para conservar" : "Pega tu credencial"}
                  onChange={(event) => setSecrets((previous) => ({ ...previous, [key]: event.target.value }))} />
                <span className="meta">{hint} Estado: {status?.[statusField] ? "configurada" : "no configurada"}.</span>
                {status?.[statusField] && <label><input type="checkbox" checked={clear[key]} onChange={(event) => setClear((previous) => ({ ...previous, [key]: event.target.checked }))} /> Revocar esta credencial al guardar</label>}
              </div>
            ))}
            <p className="warning">Cloudflare Access debe permitir tu Service Token y LM Studio debe tener habilitada la autenticación con tu API token. Se requieren ambas.</p>
          </> : <p className="info">Anthropic utiliza la clave del servidor aprobada por el operador; tu selección no cambia la de los demás usuarios.</p>}
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
            <button disabled={busy !== ""} onClick={save}>{busy === "save" ? "Guardando…" : "Guardar mi configuración"}</button>
            <button className="btn-secondary" disabled={busy !== "" || !status?.configured} onClick={test}>{busy === "test" ? "Probando…" : "Probar mi conexión"}</button>
            <button className="btn-secondary" disabled={busy !== "" || !status?.configured} onClick={remove}>Eliminar mi configuración</button>
          </div>
        </>}
        {error && <p className="error" role="alert">{error}</p>}
        {message && <p className="info" role="status">{message}</p>}
        <p className="meta">No hay cambio automático a otro proveedor si tu modelo falla. La lógica clínica determinista sigue siendo independiente.</p>
      </section>
    </div>
  );
}
