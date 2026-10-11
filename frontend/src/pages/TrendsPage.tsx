import { useEffect, useMemo, useState } from "react";
import { api, formatDay, LongitudinalStateOut, PatientTimelineOut } from "../api";
import { PatientTrajectoryChart } from "../components/ClinicalCharts";
import { PatientTrendSummary } from "../components/PatientTrendSummary";
import ComparisonDetails, { ComparisonFacts } from "../components/ComparisonDetails";
import PsychDeepLoader from "../components/PsychDeepLoader";
import { readComparison } from "./longitudinalModel";

interface PatientStateForTrends {
  longitudinal?: LongitudinalStateOut | null;
}

/**
 * Tendencias reads the same `GET /api/v1/state` payload as Hoy, so both
 * screens always show the same comparison, with the values behind it.
 */
export default function TrendsPage() {
  const [timeline, setTimeline] = useState<PatientTimelineOut | null>(null);
  const [state, setState] = useState<PatientStateForTrends | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<PatientTimelineOut>("/api/v1/timeline?window_days=30"),
      api.get<PatientStateForTrends>("/api/v1/state"),
    ])
      .then(([timelineData, stateData]) => {
        if (timelineData && timelineData.points) {
          timelineData.points.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
        }
        setTimeline(timelineData);
        setState(stateData);
      })
      .catch(() =>
        setError(
          "No se pudieron cargar tus tendencias. Inténtalo de nuevo en un momento. Esa falta no significa que no haya cambio ni que no haya riesgo.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  const latest = useMemo(() => {
    if (!timeline?.points?.length) return null;
    return timeline.points[timeline.points.length - 1];
  }, [timeline]);
  const reading = state ? readComparison(state.longitudinal, "patient") : null;

  return (
    <div className="page">
      <section className="patient-home-hero trends-hero">
        <div className="patient-home-hero__copy">
          <p className="patient-action-card__eyebrow">Tendencias</p>
          <h1>Tu trayectoria, no una puntuación aislada</h1>
          <p>
            Esta vista reúne tus registros recientes con tu propia referencia. Los cambios son señales para observar
            y contextualizar; no equivalen por sí solos a riesgo clínico.
          </p>
        </div>

        <div className="trends-baseline">
          <p className="trends-baseline__title">Comparación con lo habitual en ti</p>
          <p className="trends-baseline__value">{reading ? reading.statusLabel : loading ? "Cargando…" : "No disponible"}</p>
          {reading && <span className="meta">{reading.facts[1].value} áreas comparadas</span>}
        </div>
      </section>

      {error && (
        <section className="card" role="alert">
          <p className="error">{error}</p>
        </section>
      )}

      {loading && !error && <PsychDeepLoader size="md" label="Cargando tus tendencias…" />}

      <section className="card" aria-labelledby="timeline-heading">
        <div className="today-separator">1 · Observar</div>
        <h2 id="timeline-heading">Últimos 30 días</h2>

        {timeline?.points.length ? (
          <>
            <p className="meta">Último registro: {formatDay(latest?.date)}</p>
            <PatientTrendSummary point={latest} moodLabel="Ánimo (último registro)" cravingLabel="Craving (último registro)" />

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
          !loading && <p>Todavía no hay registros en los últimos 30 días para dibujar una tendencia.</p>
        )}
      </section>

      {reading && (
        <section className="card" aria-labelledby="signals-heading">
          <div className="today-separator">2 · Comparar con lo habitual en ti</div>
          <h2 id="signals-heading">{reading.headline}</h2>
          <p>{reading.explanation}</p>
          <ComparisonFacts reading={reading} />
          <ComparisonDetails reading={reading} audience="patient" />
          <p className="chart-reading-note">
            <strong>Importante:</strong> esto compara tus registros contigo mismo. No es una valoración de riesgo ni
            sustituye pedir ayuda si la necesitas.
          </p>
        </section>
      )}
    </div>
  );
}
