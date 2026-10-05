import { useEffect, useMemo, useState } from "react";
import { api, formatDay, PatientTimelineOut } from "../api";
import { PatientTrajectoryChart } from "../components/ClinicalCharts";
import { PatientTrendSummary } from "../components/PatientTrendSummary";
import {
  baselineCoverage,
  baselineHero,
  baselineReady,
  baselineStabilityLabel,
  baselineStatusLabel,
  calculatedChangeText,
  featureLabel,
  insufficientChangeNotice,
  latestByFeature,
  patientBand,
  signalWasCalculated,
  type BaselineSnapshot,
  type TrajectorySignal,
} from "./trendReading";

interface BaselineResponse extends BaselineSnapshot {
  baseline: null | BaselineSnapshot["baseline"] & {
    id: string;
    feature?: string | null;
    window: { start: string; end: string };
  };
}

export default function TrendsPage() {
  const [timeline, setTimeline] = useState<PatientTimelineOut | null>(null);
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null);
  const [changes, setChanges] = useState<TrajectorySignal[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<PatientTimelineOut>("/api/v1/timeline?window_days=30"),
      api.get<BaselineResponse>("/api/v1/baselines/current"),
      api.get<TrajectorySignal[]>("/api/v1/changes?limit=20"),
    ])
      .then(([timelineData, baselineData, changeData]) => {
        if (timelineData && timelineData.points) {
          timelineData.points.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
        }
        setTimeline(timelineData);
        setBaseline(baselineData);
        setChanges(latestByFeature(changeData));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const latest = useMemo(() => {
    if (!timeline?.points?.length) return null;
    return timeline.points[timeline.points.length - 1];
  }, [timeline]);
  const comparableChanges = changes.filter((change) => change.feature !== "structural_composite");
  const calculatedChanges = comparableChanges.filter(signalWasCalculated);
  const whole = changes.find((change) => change.feature === "structural_composite" && signalWasCalculated(change));

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
          <p className="trends-baseline__value">{baselineHero(baseline)}</p>
          <span className="meta">{baselineCoverage(baseline)}</span>
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
            <PatientTrendSummary
              point={latest}
              moodLabel="Ánimo actual"
              cravingLabel="Craving actual"
            />

            <div className="chart-shell" aria-label="Tendencia longitudinal" role="region">
              <PatientTrajectoryChart
                points={timeline.points}
                height={340}
                margin={{ top: 8, right: 12, bottom: 8, left: -10 }}
                dotRadius={2}
              />
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

        {!baselineReady(baseline) ? (
          <p>
            Todavía no hay datos suficientes para describir cómo sueles estar. Mientras la referencia sea
            insuficiente, no se calcula un cambio y esa ausencia no se interpreta como normalidad.
          </p>
        ) : (
          <div className="trend-summary">
            <div className="trend-summary__item">
              <span className="trend-summary__label">Estado</span>
              <span className="trend-summary__value">{baselineStatusLabel(baseline?.status ?? "")}</span>
            </div>
            <div className="trend-summary__item">
              <span className="trend-summary__label">Referencia</span>
              <span className="trend-summary__value">{baselineStabilityLabel(baseline?.baseline?.stability ?? "")}</span>
            </div>
            <div className="trend-summary__item">
              <span className="trend-summary__label">Cobertura</span>
              <span className="trend-summary__value">{baselineCoverage(baseline)}</span>
            </div>
          </div>
        )}

        <p className="meta">
          Periodo mirado:{" "}
          {baseline?.baseline?.window
            ? formatDay(baseline.baseline.window.start) + " – " + formatDay(baseline.baseline.window.end)
            : "no disponible"}
        </p>
      </section>

      <section className="card" aria-labelledby="signals-heading">
        <div className="today-separator">3 · Preguntar antes de concluir</div>
        <h2 id="signals-heading">Señales de cambio</h2>

        {calculatedChanges.length === 0 ? (
          <p>{insufficientChangeNotice(comparableChanges)}</p>
        ) : (
          <>
            {whole && <p>{patientBand(whole.band)}. {calculatedChangeText(whole)}</p>}
            <div className="wave-tool-grid">
              {calculatedChanges.map((change) => (
                <article className="card wave-tool-card" key={change.signal_id}>
                  <p className="patient-action-card__eyebrow">{featureLabel(change.feature)}</p>
                  <h3>{patientBand(change.band)}</h3>
                  <p>{calculatedChangeText(change)}</p>
                </article>
              ))}
            </div>
            {comparableChanges.some((change) => !signalWasCalculated(change)) && (
              <p>{insufficientChangeNotice(comparableChanges.filter((change) => !signalWasCalculated(change)))}</p>
            )}
          </>
        )}

        <p className="chart-reading-note">
          <strong>Importante:</strong> esto compara tus registros contigo mismo. No es una valoración de riesgo ni
          sustituye pedir ayuda si la necesitas.
        </p>
      </section>
    </div>
  );
}
