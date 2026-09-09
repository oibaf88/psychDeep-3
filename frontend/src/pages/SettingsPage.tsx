import { useEffect, useState } from "react";
import {
  clearLegacyApiBaseOverride,
  getApiBase,
  getLegacyApiBaseOverride,
  llmSettingsApi,
  type LLMEndpointConfigIn,
  type LLMEndpointStatusOut,
  type LLMEndpointTestOut,
} from "../api";

interface FormState {
  provider: "anthropic" | "openai_compatible";
  baseUrl: string;
  chatModel: string;
  analysisModel: string;
  copilotModel: string;
  apiKey: string;
  maxTokens: number;
  timeoutSeconds: number;
  label: string;
}

const PRESETS = [
  {
    id: "lmstudio",
    name: "LM Studio local",
    baseUrl: "http://host.docker.internal:1234/v1",
    hint: "Gemma 2 en el PC. El backend Docker accede mediante host.docker.internal.",
  },
  {
    id: "tunnel",
    name: "Cloudflare Tunnel",
    baseUrl: "https://tu-tunel.ejemplo.com/v1",
    hint: "Para Render: URL HTTPS protegida por Cloudflare Access, nunca una IP de LAN.",
  },
];

function formFromStatus(status: LLMEndpointStatusOut): FormState {
  const active = status.active;
  const provider = active.provider === "anthropic" ? "anthropic" : "openai_compatible";
  return {
    provider,
    baseUrl: active.base_url || "",
    chatModel: active.chat_model || (provider === "anthropic" ? "claude-opus-5" : "gemma-2-2b-it"),
    analysisModel: active.analysis_model || (provider === "anthropic" ? "claude-opus-5" : "gemma-2-2b-it"),
    copilotModel: active.copilot_model_explicit || "",
    apiKey: "",
    maxTokens: active.max_tokens,
    timeoutSeconds: active.timeout_seconds,
    label: active.label || (provider === "anthropic" ? "Claude / Anthropic" : "Gemma 2"),
  };
}

export default function SettingsPage() {
  const [apiBase] = useState(getApiBase());
  const [legacyOverride, setLegacyOverride] = useState("");
  const [apiStatus, setApiStatus] = useState<string | null>(null);
  const [apiBusy, setApiBusy] = useState(false);
  const [status, setStatus] = useState<LLMEndpointStatusOut | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<LLMEndpointTestOut | null>(null);
  const [busy, setBusy] = useState<"" | "save" | "test" | "reset">("");

  useEffect(() => {
    const stored = getLegacyApiBaseOverride();
    if (stored) {
      clearLegacyApiBaseOverride();
      setLegacyOverride(stored);
      setApiStatus("Se borró una URL de API antigua guardada en este navegador.");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    llmSettingsApi.read()
      .then((value) => {
        if (!cancelled) {
          setStatus(value);
          setForm(formFromStatus(value));
        }
      })
      .catch((error: Error) => !cancelled && setLoadError(error.message));
    return () => {
      cancelled = true;
    };
  }, []);

  function patch(changes: Partial<FormState>) {
    setForm((current) => (current ? { ...current, ...changes } : current));
    setSaved(null);
    setSaveError(null);
  }

  function preset(id: string) {
    const item = PRESETS.find((candidate) => candidate.id === id);
    if (!item) return;
    patch({
      provider: "openai_compatible",
      baseUrl: item.baseUrl,
      chatModel: "gemma-2-2b-it",
      analysisModel: "gemma-2-2b-it",
      copilotModel: "",
      label: item.id === "lmstudio" ? "Gemma 2 en LM Studio" : "Gemma 2 por Cloudflare Tunnel",
    });
    setTestResult(null);
  }

  function chooseProvider(provider: FormState["provider"]) {
    patch(provider === "anthropic" ? {
      provider,
      baseUrl: "",
      apiKey: "",
      chatModel: "claude-opus-5",
      analysisModel: "claude-opus-5",
      copilotModel: "",
      label: "Claude / Anthropic",
    } : {
      provider,
      baseUrl: "http://host.docker.internal:1234/v1",
      apiKey: "",
      chatModel: "gemma-2-2b-it",
      analysisModel: "gemma-2-2b-it",
      copilotModel: "",
      label: "Gemma 2 en LM Studio",
    });
    setTestResult(null);
  }

  function payload(current: FormState): LLMEndpointConfigIn {
    return {
      provider: current.provider,
      base_url: current.provider === "openai_compatible" ? current.baseUrl : null,
      chat_model: current.chatModel,
      analysis_model: current.analysisModel,
      copilot_model: current.copilotModel,
      // Claude's key is read only from ANTHROPIC_API_KEY on the server.
      api_key: current.provider === "openai_compatible" ? (current.apiKey || null) : null,
      max_tokens: current.maxTokens,
      timeout_seconds: current.timeoutSeconds,
      label: current.label,
    };
  }

  async function testApiConnection() {
    setApiBusy(true);
    setApiStatus(null);
    try {
      const response = await fetch(`${apiBase}/api/v1/health`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setApiStatus("Conexión con la API de PsychDeep correcta.");
    } catch (error) {
      setApiStatus(`No se pudo conectar con la API configurada: ${(error as Error).message}.`);
    } finally {
      setApiBusy(false);
    }
  }

  async function testEndpoint() {
    if (!form) return;
    setBusy("test");
    setTestResult(null);
    setSaveError(null);
    try {
      setTestResult(await llmSettingsApi.test({ ...payload(form), timeout_seconds: Math.min(form.timeoutSeconds, 60) }));
    } catch (error) {
      setSaveError((error as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function save() {
    if (!form) return;
    setBusy("save");
    setSaveError(null);
    try {
      const next = await llmSettingsApi.save(payload(form));
      setStatus(next);
      setForm(formFromStatus(next));
      setSaved(`Guardado. Las nuevas conversaciones y análisis usarán ${form.provider === "anthropic" ? "Claude por la API de Anthropic" : "Gemma 2 en este endpoint"}.`);
    } catch (error) {
      setSaveError((error as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function reset() {
    setBusy("reset");
    setSaveError(null);
    try {
      const next = await llmSettingsApi.reset();
      setStatus(next);
      setForm(formFromStatus(next));
      setTestResult(null);
      setSaved("Se ha vuelto al proveedor configurado en el despliegue.");
    } catch (error) {
      setSaveError((error as Error).message);
    } finally {
      setBusy("");
    }
  }

  const active = status?.active;
  const locked = Boolean(status && !status.can_edit);

  return (
    <div className="page">
      <h1>Ajustes</h1>
      <p className="subtitle">
        La API de PsychDeep atiende esta interfaz. Claude/Anthropic es el proveedor conectado por defecto; Gemma 2 en LM Studio es la alternativa local u offline.
      </p>

      <section className="card">
        <h2>API de PsychDeep</h2>
        <p><code>{apiBase || "mismo origen"}</code></p>
        <p className="meta">La URL se fija al desplegar y no puede redirigirse desde este navegador.</p>
        {legacyOverride && <p className="info">Se limpió una URL de API antigua: <code>{legacyOverride}</code></p>}
        <button type="button" className="btn-secondary" disabled={apiBusy} onClick={testApiConnection}>
          {apiBusy ? "Probando…" : "Probar conexión"}
        </button>
        {apiStatus && <p className="info">{apiStatus}</p>}
      </section>

      <section className="card">
        <h2>Proveedor de inferencia</h2>
        <p className="meta">
          Claude mediante Anthropic es el valor conectado por defecto. Gemma 2 usa LM Studio mediante un endpoint compatible con OpenAI. Todo cambio está restringido a administración clínica y queda auditado porque el proveedor recibe texto de inferencia.
        </p>
        {loadError && <p className="error">No se pudo leer la configuración: {loadError}</p>}

        {active && (
          <div className="llm-active">
            <span className="llm-active-label">En uso ahora</span>
            <strong>{active.chat_model}</strong><span className="meta"> · {active.provider_label}</span>
            <dl className="llm-active-grid">
              <div><dt>Análisis</dt><dd>{active.analysis_model}</dd></div>
              <div><dt>Copiloto</dt><dd>{active.copilot_model || active.chat_model}</dd></div>
              <div><dt>Endpoint</dt><dd>{active.base_url ? <code>{active.base_url}</code> : active.provider === "anthropic" ? "API de Anthropic" : "Sin endpoint configurado"}</dd></div>
              <div><dt>Clave</dt><dd>{active.uses_server_api_key ? (active.has_api_key ? "Sólo en el servidor" : "Falta ANTHROPIC_API_KEY en el servidor") : active.has_api_key ? "Guardada en el backend" : "Sin clave configurada"}</dd></div>
              <div><dt>Origen</dt><dd>{active.source === "runtime" ? "Configurado por administración" : "Configuración del despliegue"}</dd></div>
              <div><dt>Desde</dt><dd>{active.updated_at ? new Date(active.updated_at).toLocaleString() : "Inicio del despliegue"}</dd></div>
            </dl>
          </div>
        )}

        {status?.ignored_override && <p className="warning">Un endpoint local no es alcanzable desde este backend; se usa el proveedor configurado en el despliegue.</p>}
        {status?.notice && <p className={status.is_local || status.ignored_override ? "warning" : "info"}>{status.notice}</p>}
        {status && !status.override_allowed && <p className="meta">El despliegue compartido bloquea cambios de endpoint (`LLM_ALLOW_RUNTIME_OVERRIDE=false`).</p>}

        {form && !locked && (
          <>
            <label className="field">
              <span>Proveedor</span>
              <select value={form.provider} onChange={(event) => chooseProvider(event.target.value as FormState["provider"])}>
                <option value="anthropic">Claude / API de Anthropic (predeterminado)</option>
                <option value="openai_compatible">Gemma 2 / LM Studio (local u offline)</option>
              </select>
              <span className="meta">Claude toma su clave exclusivamente de <code>ANTHROPIC_API_KEY</code> en el servidor. Nunca se escribe ni se devuelve en esta pantalla.</span>
            </label>
            {form.provider === "anthropic" && <p className="info">Claude usará la API de Anthropic con la clave de servidor. No se guarda una URL ni una clave en la configuración de ejecución.</p>}
            {form.provider === "openai_compatible" && <>
            <div className="llm-presets">
              <span className="meta">Valores iniciales:</span>
              {PRESETS.map((item) => <button key={item.id} type="button" className="btn-chip" title={item.hint} onClick={() => preset(item.id)}>{item.name}</button>)}
            </div>
            {!status?.local_endpoint_supported && <p className="warning">Render no puede alcanzar una IP privada. Usa un hostname HTTPS de Cloudflare Tunnel protegido con Access, nunca `127.0.0.1` o `192.168.x`.</p>}
            <label className="field">
              <span>URI de LM Studio / túnel</span>
              <input type="url" value={form.baseUrl} placeholder={status?.local_endpoint_supported ? "http://host.docker.internal:1234/v1" : "https://tu-tunel.ejemplo.com/v1"} onChange={(event) => patch({ baseUrl: event.target.value })} />
              <span className="meta">Siempre termina en <code>/v1</code>. Local Docker: <code>http://host.docker.internal:1234/v1</code>.</span>
            </label>
            </>}
            <div className="field-row">
              <label className="field"><span>{form.provider === "anthropic" ? "Claude — conversación" : "Gemma 2 — conversación"}</span><input value={form.chatModel} onChange={(event) => patch({ chatModel: event.target.value })} /></label>
              <label className="field"><span>{form.provider === "anthropic" ? "Claude — análisis" : "Gemma 2 — análisis"}</span><input value={form.analysisModel} onChange={(event) => patch({ analysisModel: event.target.value })} /></label>
            </div>
            <div className="field-row">
              <label className="field"><span>{form.provider === "anthropic" ? "Claude — copiloto clínico" : "Gemma 2 — copiloto clínico"}</span><input value={form.copilotModel} placeholder={form.chatModel || "Igual que conversación"} onChange={(event) => patch({ copilotModel: event.target.value })} /></label>
              {form.provider === "openai_compatible" && <label className="field"><span>Token de LM Studio</span><input type="password" value={form.apiKey} placeholder={active?.has_api_key ? "Guardado — vacío conserva el existente" : "Requerido si LM Studio exige autenticación"} onChange={(event) => patch({ apiKey: event.target.value })} /></label>}
            </div>
            <div className="field-row">
              <label className="field"><span>Tokens máximos</span><input type="number" min={256} max={32768} value={form.maxTokens} onChange={(event) => patch({ maxTokens: Number(event.target.value) })} /></label>
              <label className="field"><span>Espera de inferencia (s)</span><input type="number" min={5} max={5000} value={form.timeoutSeconds} onChange={(event) => patch({ timeoutSeconds: Number(event.target.value) })} /></label>
              <label className="field"><span>Nombre de configuración</span><input value={form.label} placeholder={form.provider === "anthropic" ? "Claude / Anthropic" : "Gemma 2 en LM Studio"} onChange={(event) => patch({ label: event.target.value })} /></label>
            </div>
            <div className="alert-actions">
              <button type="button" className="btn-secondary" disabled={busy !== ""} onClick={testEndpoint}>{busy === "test" ? "Probando…" : "Probar endpoint"}</button>
              <button type="button" disabled={busy !== ""} onClick={save}>{busy === "save" ? "Guardando…" : `Guardar ${form.provider === "anthropic" ? "Claude" : "Gemma 2"}`}</button>
              {active?.source === "runtime" && <button type="button" className="btn-secondary" disabled={busy !== ""} onClick={reset}>{busy === "reset" ? "Restaurando…" : "Volver al despliegue"}</button>}
            </div>
            {testResult && <p className={testResult.ok ? "info" : "error"}>{testResult.ok ? "El endpoint responde. " : ""}{testResult.detail}</p>}
            {saveError && <p className="error">{saveError}</p>}
            {saved && <p className="info">{saved}</p>}
          </>
        )}
      </section>

      <section className="card">
        <h2>Garantías</h2>
        <ul className="plain-list">
          <li>La procedencia de cada respuesta/análisis queda registrada, incluidos proveedores históricos, para que los datos clínicos antiguos sigan siendo legibles.</li>
          <li>Ni Claude ni Gemma 2 deciden niveles de alerta: el motor de riesgo usa reglas deterministas y trazables.</li>
          <li>Las claves nunca vuelven al navegador. Claude usa <code>ANTHROPIC_API_KEY</code> sólo en el servidor; en Render, Gemma 2 requiere HTTPS protegido por Cloudflare Access.</li>
        </ul>
      </section>
    </div>
  );
}
