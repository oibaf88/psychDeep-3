import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, AssignmentOut, CheckInIn, PatientTimelineOut, formatDay } from "../api";
import { PatientTrajectoryChart } from "../components/ClinicalCharts";
import { PatientTrendSummary } from "../components/PatientTrendSummary";
import { longitudinalFraming, type PatientStateResponse } from "./longitudinalReading";

const emptyForm: CheckInIn = { mood: 5, craving: 3, sleep_hours: 7, self_efficacy: 5, notes: "" };

type SuggestedAction = {
  title: string;
  body: string;
  button: string;
  route: string;
};

export default function PatientDashboard() {
  const navigate = useNavigate();
  const [timeline, setTimeline] = useState<PatientTimelineOut | null>(null);
  const [patientState, setPatientState] = useState<PatientStateResponse | null>(null);
  const [stateError, setStateError] = useState<string | null>(null);
  const [form, setForm] = useState<CheckInIn>(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pendingLinks, setPendingLinks] = useState<AssignmentOut[]>([]);
  const [showSuggestedAction, setShowSuggestedAction] = useState(true);

  async function loadTimeline() {
    const data = await api.get<PatientTimelineOut>("/api/v1/timeline?window_days=30");
    setTimeline(data);
  }

  async function loadState() {
    try {
      const data = await api.get<PatientStateResponse>("/api/v1/state");
      setPatientState(data);
      setStateError(null);
    } catch {
      setStateError(
        "No se pudo cargar la comparación con tu línea de base. Esa falta no significa que no haya cambio ni que no haya riesgo.",
      );
    }
  }

  useEffect(() => {
    loadTimeline().catch(() => setMessage("No se pudo cargar tu historial."));
    loadState().catch(() => undefined);
    api
      .get<AssignmentOut[]>("/api/v1/assignments/mine")
      .then((rows) => setPendingLinks(rows.filter((r) => r.status === "pending")))
      .catch(() => undefined);
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setMessage(null);

    try {
      await api.post("/api/v1/checkins", form);
      setMessage("Check-in registrado.");
      setForm(emptyForm);
      setShowSuggestedAction(true);
      await Promise.all([loadTimeline(), loadState()]);
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const latestPoint = timeline?.points?.length ? timeline.points[timeline.points.length - 1] : null;
  const framing = patientState ? longitudinalFraming(patientState) : null;
  const heroHeadline = framing?.headline ?? (stateError ? "No disponible" : "Leyendo tu referencia");
  const heroMeta = framing
    ? `${framing.baselineStatus} · ${framing.coverage}`
    : stateError
      ? "Comparación no disponible"
      : "Leyendo tu línea de base";
  const heroExplanation = framing
    ? framing.explanation
    : stateError
      ? "No se pudo cargar la comparación. Esa falta no significa que no haya cambio ni que no haya riesgo."
      : "Leyendo cómo está tu registro reciente respecto a lo habitual en ti.";

  const suggestedAction = useMemo<SuggestedAction>(() => {
    if (form.craving >= 7) {
      return {
        title: "Regular una ola",
        body: "Tienes una urgencia alta en este momento. Puedes probar la práctica de la ola sin necesidad de resolver nada más ahora.",
        button: "Ir a Regular",
        route: "/wave",
      };
    }

    if (form.self_efficacy <= 3) {
      return {
        title: "Bajar el ritmo",
        body: "Cuando la confianza está baja, una práctica breve puede ayudarte a recuperar espacio antes de decidir el siguiente paso.",
        button: "Ir a Regular",
        route: "/wave",
      };
    }

    return {
      title: "Registrar y observar",
      body: "No necesitas hacer más ahora. Puedes dejar este registro y volver a él más tarde para observar tu propia trayectoria.",
      button: "Ver Tendencias",
      route: "/trends",
    };
  }, [form.craving, form.self_efficacy]);

  return (
    <main className="page hoy" aria-label="Panel del paciente">
      <section className="hoy-lead" role="region" aria-label="Resumen del cambio respecto a tu línea de base">
        <p className="hoy-kicker">Hoy</p>
        <h1>{heroHeadline}</h1>
        <p className="hoy-lead__explain">{heroExplanation}</p>
        {framing?.missingNotice && <p className="hoy-missing">{framing.missingNotice}</p>}
        {framing ? (
          <dl className="hoy-facts">
            <div>
              <dt>Referencia</dt>
              <dd>{framing.baselineStatus}</dd>
            </div>
            <div>
              <dt>Calidad</dt>
              <dd>{framing.referenceQuality}</dd>
            </div>
            <div>
              <dt>Cobertura</dt>
              <dd>{framing.coverage}</dd>
            </div>
          </dl>
        ) : (
          <p className="hoy-lead__waiting">{heroMeta}</p>
        )}
      </section>

      {pendingLinks.length > 0 && (
        <section className="card patient-notice patient-notice--accent">
          <p className="patient-action-card__eyebrow">Decisión pendiente</p>
          <h2>Solicitudes de vinculación</h2>
          <p>
            Tienes {pendingLinks.length} profesional(es) pidiendo acceso a tu seguimiento. Puedes aceptar o rechazar
            desde Vinculaciones.
          </p>
          <button type="button" className="btn-secondary" onClick={() => navigate("/assignments")}>
            Revisar vinculaciones
          </button>
        </section>
      )}

      <section className="hoy-next" aria-label="Siguiente paso">
        {showSuggestedAction ? (
          <article className="hoy-next__card">
            <div>
              <p className="hoy-kicker">Una opción para ahora</p>
              <h2 className="hoy-next__title">{suggestedAction.title}</h2>
              <p className="hoy-next__body">{suggestedAction.body}</p>
            </div>
            <div className="hoy-next__controls">
              <button type="button" onClick={() => navigate(suggestedAction.route)}>
                {suggestedAction.button}
              </button>
              <button
                type="button"
                className="btn-quiet"
                onClick={() => setShowSuggestedAction(false)}
                aria-label="Ocultar sugerencia por ahora"
              >
                No ahora
              </button>
            </div>
          </article>
        ) : (
          <article className="hoy-next__card hoy-next__card--quiet">
            <div>
              <p className="hoy-kicker">Sin siguiente paso</p>
              <h2 className="hoy-next__title">Puedes dejarlo aquí</h2>
              <p className="hoy-next__body">
                La aplicación no necesita que hagas nada más ahora. Puedes continuar cuando te resulte útil.
              </p>
            </div>
            <div className="hoy-next__controls">
              <button type="button" className="btn-secondary" onClick={() => setShowSuggestedAction(true)}>
                Mostrar una opción
              </button>
            </div>
          </article>
        )}
      </section>

      <section className="hoy-checkin" aria-labelledby="checkin-heading">
        <h2 id="checkin-heading">Check-in de hoy</h2>
        <p className="hoy-checkin__intro">
          Una lectura rápida de cuatro señales. Puedes corregirlas antes de guardar; no hay puntuación ni racha que mantener.
        </p>

        <form onSubmit={onSubmit} className="checkin-form hoy-checkin__form">
          <div className="hoy-scale">
            <div className="hoy-scale__head">
              <label htmlFor="checkin-mood">Estado de ánimo</label>
              <output className="hoy-scale__value" htmlFor="checkin-mood">{form.mood}</output>
            </div>
            <input
              id="checkin-mood"
              type="range"
              min={0}
              max={10}
              value={form.mood}
              onChange={(e) => setForm({ ...form, mood: Number(e.target.value) })}
              aria-valuemin={0}
              aria-valuemax={10}
              aria-valuenow={form.mood}
              aria-label="Escala de estado de ánimo de 0 a 10"
            />
            <div className="range-labels" aria-hidden="true">
              <span>0 (Peor)</span>
              <span>10 (Mejor)</span>
            </div>
          </div>

          <div className="hoy-scale">
            <div className="hoy-scale__head">
              <label htmlFor="checkin-craving">Craving / deseo de consumo</label>
              <output className="hoy-scale__value" htmlFor="checkin-craving">{form.craving}</output>
            </div>
            <input
              id="checkin-craving"
              type="range"
              min={0}
              max={10}
              value={form.craving}
              onChange={(e) => setForm({ ...form, craving: Number(e.target.value) })}
              aria-valuemin={0}
              aria-valuemax={10}
              aria-valuenow={form.craving}
              aria-label="Escala de craving o deseo de consumo de 0 a 10"
            />
            <div className="range-labels" aria-hidden="true">
              <span>0 (Ninguno)</span>
              <span>10 (Máximo)</span>
            </div>
          </div>

          <div className="hoy-scale hoy-scale--sleep">
            <label htmlFor="checkin-sleep">Horas de sueño anoche</label>
            <input
              id="checkin-sleep"
              className="hoy-scale__number"
              type="number"
              step="0.5"
              min={0}
              max={24}
              value={form.sleep_hours}
              onChange={(e) => setForm({ ...form, sleep_hours: Number(e.target.value) })}
            />
          </div>

          <div className="hoy-scale">
            <div className="hoy-scale__head">
              <label htmlFor="checkin-efficacy">Confianza para manejar hoy</label>
              <output className="hoy-scale__value" htmlFor="checkin-efficacy">{form.self_efficacy}</output>
            </div>
            <input
              id="checkin-efficacy"
              type="range"
              min={0}
              max={10}
              value={form.self_efficacy}
              onChange={(e) => setForm({ ...form, self_efficacy: Number(e.target.value) })}
              aria-valuemin={0}
              aria-valuemax={10}
              aria-valuenow={form.self_efficacy}
              aria-label="Escala de autoeficacia de 0 a 10"
            />
            <div className="range-labels" aria-hidden="true">
              <span>0 (Ninguna)</span>
              <span>10 (Total)</span>
            </div>
          </div>

          <div className="hoy-scale hoy-scale--notes">
            <label htmlFor="checkin-notes">Notas (opcional)</label>
            <textarea
              id="checkin-notes"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="¿Hay algo que quieras dejar registrado?"
            />
          </div>

          <button type="submit" disabled={submitting}>
            {submitting ? "Guardando…" : "Guardar check-in"}
          </button>
        </form>

        {message && (
          <p className="info" aria-live="polite" role="status">
            {message}
          </p>
        )}
      </section>

      <section className="card hoy-panel" aria-labelledby="trend-heading">
        <div className="trends-hero">
          <div>
            <h2 id="trend-heading">Tu trayectoria</h2>
            <p className="subtitle">
              Últimos 30 días de registros. El gráfico muestra observaciones; no calcula el cambio ni rellena los huecos
              con ceros. La comparación detallada con tu línea de base está más abajo.
            </p>
          </div>
          {latestPoint && (
            <div className="trends-baseline" aria-label="Último registro disponible">
              <p className="trends-baseline__title">Último registro</p>
              <p className="trends-baseline__value">{formatDay(latestPoint.date)}</p>
            </div>
          )}
        </div>

        {timeline && timeline.points.length > 0 ? (
          <>
            <PatientTrendSummary
              point={latestPoint}
              moodLabel="Ánimo"
              cravingLabel="Craving"
              ariaLabel="Resumen del último registro"
            />

            <div className="chart-shell" aria-label="Tendencia de ánimo, craving y autoeficacia" role="region">
              <PatientTrajectoryChart
                points={timeline.points}
                height={300}
                margin={{ top: 8, right: 8, bottom: 4, left: -16 }}
                dotRadius={2.5}
                sleepDotRadius={2}
                formatSleepTicks
              />
            </div>

            <p className="chart-reading-note">
              <strong>Cómo leerlo:</strong> busca relaciones entre variables a lo largo del tiempo. Un cambio aislado
              no explica por sí solo por qué te encuentras como te encuentras.
            </p>
          </>
        ) : (
          <p>Todavía no hay registros en esta ventana.</p>
        )}
      </section>

      <section className="card hoy-panel longitudinal-change" aria-label="Cambio respecto a tu línea de base">
        <h2 id="baseline-change-heading">Respecto a lo habitual en ti</h2>
        <p className="longitudinal-change__distinction">
          Esta lectura sale de tu línea de base y de las señales de cambio. No es un nivel de alerta ni una valoración
          de riesgo. Si necesitas ayuda, la línea 024, el 112 y tu plan de seguridad siguen disponibles.
        </p>

        {stateError && (
          <p className="error" role="alert">
            {stateError}
          </p>
        )}

        {!patientState && !stateError && <p>Leyendo tu línea de base…</p>}

        {framing && (
          <>
            <div className="trend-summary" aria-label="Calidad de la línea de base">
              <div className="trend-summary__item">
                <span className="trend-summary__label">Referencia</span>
                <span className="trend-summary__value">{framing.baselineStatus}</span>
              </div>
              <div className="trend-summary__item">
                <span className="trend-summary__label">Calidad</span>
                <span className="trend-summary__value">{framing.referenceQuality}</span>
              </div>
              <div className="trend-summary__item">
                <span className="trend-summary__label">Cobertura</span>
                <span className="trend-summary__value">{framing.coverage}</span>
              </div>
            </div>

            <p className="longitudinal-change__headline">{framing.headline}</p>
            <p>{framing.explanation}</p>

            {framing.featureLines.length > 0 && (
              <ul className="longitudinal-change__list">
                {framing.featureLines.map((line) => (
                  <li className="longitudinal-change__item" key={line.signalId}>
                    <h3>{line.label}</h3>
                    <p className="longitudinal-change__band">{line.bandLabel}</p>
                    <p>{line.detail}</p>
                  </li>
                ))}
              </ul>
            )}

            {framing.pendingNotice && <p>{framing.pendingNotice}</p>}
            {framing.missingNotice && <p>{framing.missingNotice}</p>}
            {framing.limits.map((limit) => (
              <p className="chart-reading-note" key={limit}>
                {limit}
              </p>
            ))}
          </>
        )}
      </section>
    </main>
  );
}
