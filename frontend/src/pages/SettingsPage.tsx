import { useEffect, useMemo, useState } from "react";
import {
  clearLegacyApiBaseOverride,
  getApiBase,
  getLegacyApiBaseOverride,
  llmSettingsApi,
  type LLMEndpointConfigIn,
  type LLMEndpointStatusOut,
  type LLMEndpointTestOut,
} from "../api";

type Provider = "anthropic" | "openai_compatible";

interface FormState {
  provider: Provider;
  baseUrl: string;
  chatModel: string;
  analysisModel: string;
  copilotModel: string;
  maxTokens: number;
  timeoutSeconds: number;
  label: string;
}

function formFromStatus(status: LLMEndpointStatusOut): FormState {
  const active = status.active;
  const provider: Provider = active.provider === "anthropic" ? "anthropic" : "openai_compatible";
  return {
    provider,
    baseUrl: active.base_url || "",
    chatModel: active.chat_model || (provider === "anthropic" ? "claude-opus-5" : ""),
    analysisModel: active.analysis_model || active.chat_model || (provider === "anthropic" ? "claude-opus-5" : ""),
    copilotModel: active.copilot_model_explicit || "",
    maxTokens: active.max_tokens || 8192,
    timeoutSeconds: active.timeout_seconds || 45,
    label: active.label || (provider === "anthropic" ? "Claude / Anthropic" : "Modelo local"),
  };
}

export default function SettingsPage() {
  const [status, setStatus] = useState<LLMEndpointStatusOut | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [legacyOverride, setLegacyOverride] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<LLMEndpointTestOut | null>(null);
  const [busy, setBusy] = useState<"" | "save" | "test" | "reset">("");

  useEffect(() => {
    const legacy = getLegacyApiBaseOverride();
    if (legacy) {
      clearLegacyApiBaseOverride();
      setLegacyOverride(legacy);
    }

    llmSettingsApi.read()
      .then((next) => {
        setStatus(next);
        setForm(formFromStatus(next));
      })
      .catch((error: Error) => setLoadError(error.message));
  }, []);

  const localPreset = useMemo(() => {
    if (!status) return null;
    if (status.active.provider === "openai_compatible") return status.active;
    if (status.environment_default.provider === "openai_compatible") return status.environment_default;
    return null;
  }, [status]);

  function patch(changes: Partial<FormState>) {
    setForm((current) => (current ? { ...current, ...changes } : current));
    setActionError(null);
    setMessage(null);
  }

  function chooseProvider(provider: Provider) {
    setTestResult(null);
    if (provider === "anthropic") {
      patch({
        provider,
        baseUrl: "",
        chatModel: status?.active.provider === "anthropic" ? status.active.chat_model : "claude-opus-5",
        analysisModel: status?.active.provider === "anthropic" ? status.active.analysis_model : "claude-opus-5",
        copilotModel: status?.active.provider === "anthropic" ? status.active.copilot_model_explicit : "",
        label: "Claude / Anthropic",
      });
      return;
    }

    patch({
      provider,
      baseUrl: localPreset?.base_url || "https://ai.bfab.io/v1",
      chatModel: localPreset?.chat_model || "gemma-2-2b-it",
      analysisModel: localPreset?.analysis_model || localPreset?.chat_model || "gemma-2-2b-it",
      copilotModel: localPreset?.copilot_model_explicit || "",
      maxTokens: localPreset?.max_tokens || 8192,
      timeoutSeconds: localPreset?.timeout_seconds || 45,
      label: "Modelo local / túnel seguro",
    });
  }

  function payload(current: FormState): LLMEndpointConfigIn {
    return {
      provider: current.provider,
      base_url: current.provider === "openai_compatible" ? current.baseUrl : null,
      chat_model: current.chatModel,
      analysis_model: current.analysisModel,
      copilot_model: current.copilotModel || null,
      api_key: null,
      max_tokens: current.maxTokens,
      timeout_seconds: current.timeoutSeconds,
      label: current.label,
    };
  }

  async function testEndpoint() {
    if (!form) return;
    setBusy("test");
    setActionError(null);
    setMessage(null);
    setTestResult(null);
    try {
      const result = await llmSettingsApi.test({
        ...payload(form),
        timeout_seconds: Math.min(form.timeoutSeconds, 60),
      });
      setTestResult(result);
    } catch (error) {
      setActionError((error as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function save() {
    if (!form) return;
    setBusy("save");
    setActionError(null);
    setMessage(null);
    try {
      const next = await llmSettingsApi.save(payload(form));
      setStatus(next);
      setForm(formFromStatus(next));
      setTestResult(null);
      setMessage(
        `Proveedor cambiado a ${next.active.provider === "anthropic" ? "Anthropic" : "modelo local"}. ` +
        "Las nuevas llamadas de inferencia usarán esta selección."
      );
    } catch (error) {
      setActionError((error as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function reset() {
    setBusy("reset");
    setActionError(null);
    setMessage(null);
    try {
      const next = await llmSettingsApi.reset();
      setStatus(next);
      setForm(formFromStatus(next));
      setTestResult(null);
      setMessage("Restaurado el proveedor definido por el despliegue.");
    } catch (error) {
      setActionError((error as Error).message);
    } finally {
      setBusy("");
    }
  }

  const active = status?.active;
  const locked = Boolean(status && !status.can_edit);

  return (
    <div className="page">
      <h1>{status?.can_edit ? "Modelos" : "Estado del sistema"}</h1>
      <p className="subtitle">
        Estado de la API y proveedor LLM. El cambio de proveedor está restringido a administración clínica y queda auditado.
      </p>

      <section className="card">
        <h2>API cloud</h2>
        <p><code>{getApiBase() || "mismo origen"}</code></p>
        <p className="meta">Los datos clínicos siguen almacenándose únicamente en la nube; este ajuste solo cambia la inferencia generativa.</p>
        {legacyOverride && <p className="info">Se eliminó una URL antigua guardada en este navegador: <code>{legacyOverride}</code>.</p>}
      </section>

      <section className="card">
        <h2>Proveedor de inferencia</h2>
        {loadError && <p className="error">No se pudo leer la configuración: {loadError}</p>}

        {active && (
          <div className="llm-active">
            <span className="llm-active-label">En uso ahora</span>
            <strong>{active.provider === "anthropic" ? "Anthropic" : "Modelo local / OpenAI-compatible"}</strong>
            <dl className="llm-active-grid">
              <div><dt>Conversación</dt><dd>{active.chat_model || "sin configurar"}</dd></div>
              <div><dt>Análisis</dt><dd>{active.analysis_model || "sin configurar"}</dd></div>
              <div><dt>Copiloto</dt><dd>{active.copilot_model || active.chat_model || "sin configurar"}</dd></div>
              <div><dt>Origen</dt><dd>{active.source === "runtime" ? "selección de administración" : "despliegue"}</dd></div>
              {active.base_url && <div><dt>Endpoint</dt><dd><code>{active.base_url}</code></dd></div>}
              <div><dt>Credencial</dt><dd>{active.has_api_key ? "configurada en backend" : "no configurada"}</dd></div>
            </dl>
          </div>
        )}

        {status?.notice && <p className={status.is_local ? "warning" : "info"}>{status.notice}</p>}
        {status && !status.override_allowed && (
          <p className="warning">El despliegue tiene <code>LLM_ALLOW_RUNTIME_OVERRIDE=false</code>.</p>
        )}
        {status && status.override_allowed && !status.can_edit && (
          <p className="meta">Solo el perfil <strong>Admin clínico</strong> puede cambiar el proveedor.</p>
        )}

        {form && !locked && (
          <>
            <label className="field">
              <span>Proveedor</span>
              <select value={form.provider} onChange={(event) => chooseProvider(event.target.value as Provider)}>
                <option value="anthropic">Anthropic / Claude</option>
                <option value="openai_compatible">Modelo local o propio / OpenAI-compatible</option>
              </select>
            </label>

            {form.provider === "anthropic" ? (
              <p className="info">La clave se toma exclusivamente de <code>ANTHROPIC_API_KEY</code> en Render.</p>
            ) : (
              <>
                {!status?.local_endpoint_supported && (
                  <p className="warning">Render no puede usar una IP privada del PC. El endpoint debe ser HTTPS y alcanzable desde la nube, por ejemplo mediante Cloudflare Tunnel.</p>
                )}
                <label className="field">
                  <span>Endpoint compatible con OpenAI</span>
                  <input type="url" value={form.baseUrl} onChange={(event) => patch({ baseUrl: event.target.value })} placeholder="https://ai.bfab.io/v1" />
                  <span className="meta">La credencial, si el endpoint la exige, se configura solo como secreto del backend.</span>
                </label>
              </>
            )}

            <div className="field-row">
              <label className="field"><span>Modelo de conversación</span><input value={form.chatModel} onChange={(event) => patch({ chatModel: event.target.value })} /></label>
              <label className="field"><span>Modelo de análisis</span><input value={form.analysisModel} onChange={(event) => patch({ analysisModel: event.target.value })} /></label>
            </div>

            <div className="field-row">
              <label className="field"><span>Modelo de copiloto</span><input value={form.copilotModel} placeholder="vacío = igual que conversación" onChange={(event) => patch({ copilotModel: event.target.value })} /></label>
              <label className="field"><span>Tokens máximos</span><input type="number" min={256} max={32768} value={form.maxTokens} onChange={(event) => patch({ maxTokens: Number(event.target.value) })} /></label>
              <label className="field"><span>Timeout (s)</span><input type="number" min={5} max={5000} value={form.timeoutSeconds} onChange={(event) => patch({ timeoutSeconds: Number(event.target.value) })} /></label>
            </div>

            <label className="field"><span>Etiqueta</span><input value={form.label} onChange={(event) => patch({ label: event.target.value })} /></label>

            <div className="alert-actions">
              <button type="button" className="btn-secondary" disabled={busy !== ""} onClick={testEndpoint}>{busy === "test" ? "Probando…" : "Probar proveedor"}</button>
              <button type="button" disabled={busy !== ""} onClick={save}>{busy === "save" ? "Guardando…" : "Guardar y activar"}</button>
              <button type="button" className="btn-secondary" disabled={busy !== ""} onClick={reset}>{busy === "reset" ? "Restaurando…" : "Volver al despliegue"}</button>
            </div>
          </>
        )}

        {testResult && <p className={testResult.ok ? "info" : "error"}>{testResult.detail}</p>}
        {message && <p className="info">{message}</p>}
        {actionError && <p className="error">{actionError}</p>}

        <p className="meta">
          No hay fallback silencioso: si el proveedor seleccionado está caído, las funciones dependientes del LLM fallan de forma controlada; almacenamiento, consentimiento y riesgo determinista siguen funcionando.
        </p>
      </section>
    </div>
  );
}
