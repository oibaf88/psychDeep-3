import { useEffect, useState } from "react";
import { api, clearLegacyApiBaseOverride, getApiBase, getLegacyApiBaseOverride } from "../api";

interface DeploymentStatus {
  alias: string;
  adapter: string;
  chat_model: string;
  analysis_model: string;
  copilot_model: string;
  policy_version: string;
  data_handling_classification: string;
  configured: boolean;
  status?: string;
  reason?: string;
}

interface StatusResponse {
  active: DeploymentStatus;
  deployments: DeploymentStatus[];
}

export default function SettingsPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [legacyOverride, setLegacyOverride] = useState("");

  useEffect(() => {
    const legacy = getLegacyApiBaseOverride();
    if (legacy) {
      clearLegacyApiBaseOverride();
      setLegacyOverride(legacy);
    }
    api.get<StatusResponse>("/api/v1/model/deployments/status")
      .then(setStatus)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="page">
      <h1>Estado del sistema</h1>
      <p className="subtitle">
        La configuración de modelos es operativa y se gestiona fuera de la interfaz clínica. Ningún usuario o administrador clínico puede cambiar endpoints, claves o saltarse guardrails desde aquí.
      </p>

      <section className="card">
        <h2>API cloud</h2>
        <p><code>{getApiBase() || "mismo origen"}</code></p>
        <p className="meta">Los datos clínicos se almacenan únicamente en la nube; el navegador no mantiene una base clínica local.</p>
        {legacyOverride && <p className="info">Se eliminó una URL de API antigua guardada en este navegador: <code>{legacyOverride}</code>.</p>}
      </section>

      <section className="card">
        <h2>Model Gateway</h2>
        {error && <p className="error">No se pudo obtener el estado: {error}</p>}
        {status?.active && (
          <>
            <p><strong>Deployment activo:</strong> {status.active.alias}</p>
            <dl className="llm-active-grid">
              <div><dt>Estado</dt><dd>{status.active.status || (status.active.configured ? "configurado" : "no disponible")}</dd></div>
              <div><dt>Conversación</dt><dd>{status.active.chat_model || "sin configurar"}</dd></div>
              <div><dt>Análisis</dt><dd>{status.active.analysis_model || "sin configurar"}</dd></div>
              <div><dt>Política</dt><dd>{status.active.policy_version}</dd></div>
            </dl>
            <p className="meta">
              Si este modelo está caído, el registro de datos, el plan de seguridad y el motor de riesgo determinista siguen funcionando. No existe cambio silencioso a otro proveedor.
            </p>
          </>
        )}
      </section>

      <section className="card">
        <h2>Perfiles aprobados</h2>
        <ul>
          {(status?.deployments || []).map((item) => (
            <li key={item.alias}>
              <strong>{item.alias}</strong> — {item.adapter} — {item.configured ? "configurado" : "sin configurar"}
            </li>
          ))}
        </ul>
        <p className="meta">Las URLs privadas, tokens y claves no se muestran ni se guardan en la configuración clínica.</p>
      </section>
    </div>
  );
}
