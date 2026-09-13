import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, formatDay, PatientTimelineOut } from "../api";

interface BaselineResponse {
  status: string;
  baseline: null | {
    id: string;
    feature?: string | null;
    window: { start: string; end: string };
    stability: string;
    data_coverage?: number | null;
    algorithm_version: string;
  };
}

interface ChangeSignal {
  signal_id: string;
  feature: string;
  band: string;
  uncertainty: Record<string, unknown>;
  algorithm_version: string;
}

export default function TrendsPage() {
  const [timeline, setTimeline] = useState<PatientTimelineOut | null>(null);
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null);
  const [changes, setChanges] = useState<ChangeSignal[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<PatientTimelineOut>("/api/v1/timeline?window_days=30"),
      api.get<BaselineResponse>("/api/v1/baselines/current"),
      api.get<ChangeSignal[]>("/api/v1/changes?limit=10"),
    ])
      .then(([timelineData, baselineData, changeData]) => {
        setTimeline(timelineData);
        setBaseline(baselineData);
        setChanges(changeData);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="page">
      <h1>Tendencias</h1>
      <p className="subtitle">Cambios respecto a tu propia trayectoria. Un cambio no equivale por sí solo a riesgo clínico.</p>
      {error && <p className="error">{error}</p>}

      <section className="card">
        <h2>Últimos 30 días</h2>
        {timeline?.points.length ? (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={timeline.points} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tickFormatter={formatDay} minTickGap={24} />
              <YAxis yAxisId="left" domain={[0, 10]} />
              <YAxis yAxisId="sleep" orientation="right" domain={[0, 24]} />
              <Tooltip labelFormatter={formatDay} />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="mood" name="Ánimo" connectNulls={false} />
              <Line yAxisId="left" type="monotone" dataKey="craving" name="Craving" connectNulls={false} />
              <Line yAxisId="left" type="monotone" dataKey="self_efficacy" name="Autoeficacia" connectNulls={false} />
              <Line yAxisId="sleep" type="monotone" dataKey="sleep_hours" name="Sueño (h)" connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : <p>Datos insuficientes para mostrar una tendencia.</p>}
      </section>

      <section className="card">
        <h2>Baseline personal</h2>
        {!baseline || baseline.status === "insufficient_data" || !baseline.baseline ? (
          <p>Datos insuficientes. El sistema no interpreta la ausencia de datos como normalidad.</p>
        ) : (
          <>
            <p><strong>Estado:</strong> {baseline.status}</p>
            <p><strong>Estabilidad:</strong> {baseline.baseline.stability}</p>
            <p><strong>Cobertura:</strong> {baseline.baseline.data_coverage == null ? "sin estimar" : `${Math.round(baseline.baseline.data_coverage * 100)} %`}</p>
            <p className="meta">Versión: {baseline.baseline.algorithm_version}</p>
          </>
        )}
      </section>

      <section className="card">
        <h2>Señales de cambio</h2>
        {changes.length === 0 ? <p>No hay señales de cambio canónicas disponibles.</p> : (
          <ul>
            {changes.map((change) => (
              <li key={change.signal_id}>
                <strong>{change.feature}</strong>: {change.band} <span className="meta">({change.algorithm_version})</span>
              </li>
            ))}
          </ul>
        )}
        <p className="meta">Estas señales describen cambio. La evaluación de seguridad se calcula por separado con reglas deterministas.</p>
      </section>
    </div>
  );
}
