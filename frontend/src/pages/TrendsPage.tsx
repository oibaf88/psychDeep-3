import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, formatDay, PatientTimelineOut, TRAJECTORY_SERIES } from "../api";

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
        if (timelineData && timelineData.points) {
          timelineData.points.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
        }
        setTimeline(timelineData);
        setBaseline(baselineData);
        const uniqueChanges = Array.from(new Map(changeData.map((c) => [c.signal_id, c])).values());
        setChanges(uniqueChanges);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const latest = useMemo(() => {
    if (!timeline?.points?.length) return null;
    return timeline.points[timeline.points.length - 1];
  }, [timeline]);

  return (
    <div className="page">
      <section className="patient-home-hero trends-hero">
        <div className="patient-home-hero__copy">
          <p className="patient-action-card__eyebrow">Tendencias</p>
          <h1>Tu trayectoria, no una puntuación aislada</h1>
          <p>
            Esta vista reúne tus registros recientes con tu propia línea de base. Los cambios son señales para
            observar y contextualizar; no equivalen por sí solos a riesgo clínico.
          </p>
        </div>

        <div className="trends-baseline">
          <p className="trends-baseline__title">Línea de base</p>
          <p className="trends-baseline__value">
            {!baseline || !baseline.baseline ? "Aún insuficiente" : baseline.baseline.stability}
          </p>
          <span className="meta">
            {!baseline?.baseline?.data_coverage
              ? "Cobertura no disponible"
              : Math.round(baseline.baseline.data_coverage * 100) + "% de cobertura"}
          </span>
        </div>
      </section>

      {error && (
        <section className="card" role="alert">
          <p className="error">{error}</p>
        </section>
      )}

      <section className="card" aria-labelledby="timeline-heading">
        <div className="today-separator">1 · Observar</div>
        <h2 id="timeline-heading">Últimos 30 días</h2>

        {timeline?.points.length ? (
          <>
            <div className="trend-summary">
              <div className="trend-summary__item">
                <span className="trend-summary__label">Ánimo actual</span>
                <span className="trend-summary__value">{latest?.mood ?? "—"}/10</span>
              </div>
              <div className="trend-summary__item">
                <span className="trend-summary__label">Craving actual</span>
                <span className="trend-summary__value">{latest?.craving ?? "—"}/10</span>
              </div>
              <div className="trend-summary__item">
                <span className="trend-summary__label">Sueño</span>
                <span className="trend-summary__value">
                  {latest?.sleep_hours == null ? "—" : latest.sleep_hours + " h"}
                </span>
              </div>
            </div>

            <div className="chart-shell" aria-label="Tendencia longitudinal" role="region">
              <ResponsiveContainer width="100%" height={340}>
                <LineChart data={timeline.points} margin={{ top: 8, right: 12, bottom: 8, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tickFormatter={formatDay} minTickGap={24} tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="left" domain={[0, 10]} tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="sleep" orientation="right" domain={[0, 24]} tick={{ fontSize: 11 }} />
                  <Tooltip labelFormatter={formatDay} />
                  <Legend />
                  {TRAJECTORY_SERIES.map((series) => (
                    <Line
                      key={series.dataKey}
                      yAxisId={series.yAxisId}
                      type="monotone"
                      dataKey={series.dataKey}
                      name={series.name}
                      stroke={series.stroke}
                      strokeWidth={series.strokeWidth}
                      strokeDasharray={series.strokeDasharray}
                      connectNulls={false}
                      dot={{ r: 2 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>

            <p className="chart-reading-note">
              <strong>Cómo leerlo:</strong> observa tendencias y relaciones, no únicamente valores altos o bajos.
              La falta de un registro también es información sobre cobertura, no una señal de normalidad.
            </p>
          </>
        ) : (
          <p>Datos insuficientes para mostrar una tendencia.</p>
        )}
      </section>

      <section className="card" aria-labelledby="baseline-heading">
        <div className="today-separator">2 · Contextualizar</div>
        <h2 id="baseline-heading">Tu línea de base</h2>

        {!baseline || baseline.status === "insufficient_data" || !baseline.baseline ? (
          <p>
            Todavía no hay datos suficientes para construir una línea de base útil. El sistema no interpreta esta
            ausencia como normalidad.
          </p>
        ) : (
          <div className="trend-summary">
            <div className="trend-summary__item">
              <span className="trend-summary__label">Estado</span>
              <span className="trend-summary__value">{baseline.status}</span>
            </div>
            <div className="trend-summary__item">
              <span className="trend-summary__label">Estabilidad</span>
              <span className="trend-summary__value">{baseline.baseline.stability}</span>
            </div>
            <div className="trend-summary__item">
              <span className="trend-summary__label">Cobertura</span>
              <span className="trend-summary__value">
                {baseline.baseline.data_coverage == null
                  ? "Sin estimar"
                  : Math.round(baseline.baseline.data_coverage * 100) + "%"}
              </span>
            </div>
          </div>
        )}

        <p className="meta">
          Ventana:{" "}
          {baseline?.baseline
            ? formatDay(baseline.baseline.window.start) + " – " + formatDay(baseline.baseline.window.end) +
              " · versión " + baseline.baseline.algorithm_version
            : "no disponible"}
        </p>
      </section>

      <section className="card" aria-labelledby="signals-heading">
        <div className="today-separator">3 · Preguntar antes de concluir</div>
        <h2 id="signals-heading">Señales de cambio</h2>

        {changes.length === 0 ? (
          <p>No hay señales de cambio canónicas disponibles.</p>
        ) : (
          <div className="wave-tool-grid">
            {changes.map((change) => (
              <article className="card wave-tool-card" key={change.signal_id}>
                <p className="patient-action-card__eyebrow">{change.feature}</p>
                <h3>{change.band}</h3>
                <p>
                  Señal calculada con {change.algorithm_version}. Antes de interpretarla, añade el contexto que
                  consideres relevante: qué ocurrió, qué cambió y qué podría faltar en los datos.
                </p>
              </article>
            ))}
          </div>
        )}

        <p className="chart-reading-note">
          <strong>Importante:</strong> una señal describe cambio respecto a una referencia; la evaluación de seguridad
          se calcula por separado con reglas deterministas.
        </p>
      </section>
    </div>
  );
}
