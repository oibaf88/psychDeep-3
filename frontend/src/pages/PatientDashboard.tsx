import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, AssignmentOut, CheckInIn, LongitudinalStateOut, PatientTimelineOut, formatDay } from "../api";
import { PatientTrajectoryChart } from "../components/ClinicalCharts";
import { PatientTrendSummary } from "../components/PatientTrendSummary";
import ComparisonDetails, { ComparisonFacts } from "../components/ComparisonDetails";
import { readComparison } from "./longitudinalModel";
import { suggestedActionFromReading } from "./hoySuggestedAction";
import {
  clearPendingUsefulness,
  readPendingUsefulness,
  recordHoyActionFeedback,
  stashPendingUsefulness,
  usefulnessFromChoice,
  type PendingUsefulness,
} from "./hoyActionFeedback";

interface PatientStateResponse {
  longitudinal?: LongitudinalStateOut | null;
  missing?: string[];
  limits?: string[];
}

const emptyForm: CheckInIn = { mood: 5, craving: 3, sleep_hours: 7, self_efficacy: 5, notes: "" };

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
  const [pendingUsefulness, setPendingUsefulness] = useState<PendingUsefulness | null>(null);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

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
    setPendingUsefulness(readPendingUsefulness());
  }, []);

  async function onAcceptSuggestedAction() {
    if (feedbackBusy) return;
    setFeedbackBusy(true);
    setFeedbackMessage(null);
    try {
      await recordHoyActionFeedback({
        actionId: suggestedAction.actionId,
        state: "accepted",
        driver: suggestedAction.driver,
      });
      stashPendingUsefulness({
        actionId: suggestedAction.actionId,
        driver: suggestedAction.driver,
        title: suggestedAction.title,
      });
      navigate(suggestedAction.route);
    } finally {
      setFeedbackBusy(false);
    }
  }

  async function onPostponeSuggestedAction() {
    if (feedbackBusy) return;
    setFeedbackBusy(true);
    setFeedbackMessage(null);
    try {
      await recordHoyActionFeedback({
        actionId: suggestedAction.actionId,
        state: "postponed",
        driver: suggestedAction.driver,
      });
      setShowSuggestedAction(false);
    } finally {
      setFeedbackBusy(false);
    }
  }

  async function onUsefulnessChoice(choice: "helped" | "somewhat" | "not_really") {
    if (!pendingUsefulness || feedbackBusy) return;
    setFeedbackBusy(true);
    try {
      await recordHoyActionFeedback({
        actionId: pendingUsefulness.actionId,
        state: "completed",
        driver: pendingUsefulness.driver,
        usefulness: usefulnessFromChoice(choice),
      });
      clearPendingUsefulness();
      setPendingUsefulness(null);
      setFeedbackMessage("Gracias. Queda registrado si te resultó útil, sin borrar la sugerencia.");
    } finally {
      setFeedbackBusy(false);
    }
  }

  function onSkipUsefulness() {
    clearPendingUsefulness();
    setPendingUsefulness(null);
  }

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
  // One reading for the whole page: the hero and the detailed section below
  // can no longer disagree, because both render this same object.
  const reading = patientState ? readComparison(patientState.longitudinal, "patient") : null;
  const heroHeadline = reading?.headline ?? (stateError ? "No disponible" : "Leyendo tu referencia");
  const heroMeta = stateError ? "Comparación no disponible" : "Leyendo tu línea de base";
  const heroExplanation = reading
    ? reading.explanation
    : stateError
      ? "No se pudo cargar la comparación. Esa falta no significa que no haya cambio ni que no haya riesgo."
      : "Leyendo cómo está tu registro reciente respecto a lo habitual en ti.";

  const suggestedAction = useMemo(
    () => suggestedActionFromReading(reading, form),
    [reading, form.craving, form.self_efficacy],
  );

  return (
    <main className="page hoy" aria-label="Panel del paciente">
      <section className="hoy-lead" role="region" aria-label="Resumen del cambio respecto a tu línea de base">
        <p className="hoy-kicker">Hoy</p>
        <h1>{heroHeadline}</h1>
        <p className="hoy-lead__explain">{heroExplanation}</p>
        {reading?.staleNotice && <p className="hoy-missing">{reading.staleNotice}</p>}
        {reading ? (
          <ComparisonFacts reading={reading} className="hoy-facts" />
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

      {pendingUsefulness && (
        <section className="hoy-next" aria-label="Utilidad de la opción anterior">
          <article className="hoy-next__card hoy-next__card--feedback">
            <div>
              <p className="hoy-kicker">Después de la opción</p>
              <h2 className="hoy-next__title">¿Te resultó útil «{pendingUsefulness.title}»?</h2>
              <p className="hoy-next__body">
                Tu respuesta se guarda como feedback de la intervención. No cambia tu comparación ni un nivel de
                alerta, y no borra la sugerencia que viste.
              </p>
            </div>
            <div className="hoy-next__controls">
              <button type="button" disabled={feedbackBusy} onClick={() => onUsefulnessChoice("helped")}>
                Sí, ayudó
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={feedbackBusy}
                onClick={() => onUsefulnessChoice("somewhat")}
              >
                Un poco
              </button>
              <button
                type="button"
                className="btn-quiet"
                disabled={feedbackBusy}
                onClick={() => onUsefulnessChoice("not_really")}
              >
                No especialmente
              </button>
              <button
                type="button"
                className="btn-quiet"
                disabled={feedbackBusy}
                onClick={onSkipUsefulness}
                aria-label="Omitir valoración de utilidad"
              >
                Omitir
              </button>
            </div>
          </article>
        </section>
      )}

      {feedbackMessage && (
        <p className="info hoy-feedback-status" aria-live="polite" role="status">
          {feedbackMessage}
        </p>
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
              <button type="button" disabled={feedbackBusy} onClick={onAcceptSuggestedAction}>
                {suggestedAction.button}
              </button>
              <button
                type="button"
                className="btn-quiet"
                disabled={feedbackBusy}
                onClick={onPostponeSuggestedAction}
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

        {reading && (
          <>
            <p className="longitudinal-change__headline">{reading.headline}</p>
            <p>{reading.explanation}</p>
            <ComparisonDetails reading={reading} audience="patient" />
          </>
        )}
      </section>
    </main>
  );
}
