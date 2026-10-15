import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import PsychDeepLoader from "./PsychDeepLoader";

/**
 * What the system has accumulated about a patient, and what it plans to
 * bring up next.
 *
 * The point of showing it is that a clinician can disagree with it. A
 * portrait is a model's summary of a person in treatment; one nobody can
 * correct is one nobody should trust. The open threads are an agenda the
 * conversational agent actually follows, so editing them changes what the
 * patient gets asked next — which is exactly why it belongs to the
 * therapist and not to the model alone.
 */

export interface OpenThread {
  topic: string;
  note?: string | null;
  opened_at?: string | null;
  source?: string | null;
}

export interface PatientProfile {
  portrait: string | null;
  previous_portrait: string | null;
  portrait_version: number;
  portrait_updated_at: string | null;
  portrait_edited_by_clinician: boolean;
  open_threads: OpenThread[];
  linguistic_baseline: Record<string, { mean: number; std: number; n: number }> | null;
  linguistic_baseline_n: number;
  baseline_is_usable: boolean;
  minimum_signals_for_baseline: number;
  longitudinal_summary: string | null;
  longitudinal_model_version: number | null;
  longitudinal_created_at: string | null;
  longitudinal_source_watermark: string | null;
  longitudinal_coverage: Record<string, unknown>;
  longitudinal_facets: { domain?: string; statement: string; uncertainty?: string; status?: string }[];
  longitudinal_patterns: { domain?: string; pattern: string; uncertainty?: string }[];
  longitudinal_trajectories: { domain?: string; direction?: string; description: string }[];
  longitudinal_protective_factors: { factor: string; availability?: string }[];
  longitudinal_contradictions: { topic?: string; description: string; uncertainty?: string }[];
  longitudinal_open_questions: { question: string; rationale?: string }[];
  longitudinal_limitations: string[];
  longitudinal_consent_active: boolean;
}

const AXIS_LABELS: Record<string, string> = {
  rumination_score: "Rumiación",
  negative_valence: "Valencia negativa",
  urgency_level: "Urgencia",
  ambivalence: "Ambivalencia",
};

export default function PatientProfilePanel({
  patientId,
  canEdit,
}: {
  patientId: string;
  canEdit: boolean;
}) {
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [portraitDraft, setPortraitDraft] = useState("");
  const [threadDraft, setThreadDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [showPrevious, setShowPrevious] = useState(false);

  const load = useCallback(() => {
    api
      .get<PatientProfile>(`/api/v1/professional/patients/${patientId}/profile`)
      .then((data) => {
        setProfile(data);
        setPortraitDraft(data.portrait || "");
        setError(null);
      })
      .catch((e) => setError((e as Error).message));
  }, [patientId]);

  useEffect(load, [load]);

  async function save(body: Record<string, unknown>, message: string) {
    setBusy(true);
    setSaved(null);
    try {
      const next = await api.put<PatientProfile>(
        `/api/v1/professional/patients/${patientId}/profile`,
        body,
      );
      setProfile(next);
      setPortraitDraft(next.portrait || "");
      setSaved(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function addThread() {
    const topic = threadDraft.trim();
    if (!topic || !profile) return;
    const threads = [...profile.open_threads, { topic }].map((t) => ({
      topic: t.topic,
      note: t.note || null,
    }));
    setThreadDraft("");
    void save({ open_threads: threads }, "Tema añadido.");
  }

  function removeThread(topic: string) {
    if (!profile) return;
    const threads = profile.open_threads
      .filter((t) => t.topic !== topic)
      .map((t) => ({ topic: t.topic, note: t.note || null }));
    void save({ open_threads: threads }, "Tema cerrado.");
  }

  if (error) return <p className="error">No se pudo cargar el perfil: {error}</p>;
  if (!profile) return <PsychDeepLoader size="sm" label="Cargando perfil…" />;

  const hasPortrait = Boolean(profile.portrait);

  return (
    <div className="profile-panel">
      <h3>Quién es esta persona</h3>
      {profile.longitudinal_summary ? (
        <section className="card">
          <h4>Síntesis longitudinal del modelo · versión {profile.longitudinal_model_version ?? "—"}</h4>
          <p>{profile.longitudinal_summary}</p>
          <p className="meta">
            {profile.longitudinal_created_at ? `Actualizada ${new Date(profile.longitudinal_created_at).toLocaleString()}` : ""}
            {profile.longitudinal_source_watermark ? ` · fuentes hasta ${new Date(profile.longitudinal_source_watermark).toLocaleString()}` : ""}
          </p>
          {profile.longitudinal_facets.length > 0 && (
            <>
              <h4>Facetas</h4>
              <ul>{profile.longitudinal_facets.slice(0, 8).map((item, i) => <li key={i}><strong>{item.domain || "Contexto"}:</strong> {item.statement}<span className="meta"> · {item.uncertainty || "incertidumbre no indicada"}</span></li>)}</ul>
            </>
          )}
          {profile.longitudinal_patterns.length > 0 && (
            <>
              <h4>Patrones provisionales</h4>
              <ul>{profile.longitudinal_patterns.slice(0, 5).map((item, i) => <li key={i}>{item.pattern}<span className="meta"> · {item.uncertainty || "incertidumbre no indicada"}</span></li>)}</ul>
            </>
          )}
          {profile.longitudinal_trajectories.length > 0 && (
            <>
              <h4>Trayectorias</h4>
              <ul>{profile.longitudinal_trajectories.slice(0, 5).map((item, i) => <li key={i}><strong>{item.direction || "Evolución no clasificada"}:</strong> {item.description}</li>)}</ul>
            </>
          )}
          {profile.longitudinal_protective_factors.length > 0 && (
            <>
              <h4>Apoyos y fortalezas documentados</h4>
              <ul>{profile.longitudinal_protective_factors.slice(0, 5).map((item, i) => <li key={i}>{item.factor}<span className="meta"> · {item.availability || "disponibilidad no confirmada"}</span></li>)}</ul>
            </>
          )}
          {profile.longitudinal_contradictions.length > 0 && (
            <>
              <h4>Contradicciones pendientes</h4>
              <ul>{profile.longitudinal_contradictions.slice(0, 5).map((item, i) => <li key={i}><strong>{item.topic || "Tema"}:</strong> {item.description}<span className="meta"> · {item.uncertainty || "incertidumbre no indicada"}</span></li>)}</ul>
            </>
          )}
          {profile.longitudinal_open_questions.length > 0 && (
            <>
              <h4>Preguntas abiertas</h4>
              <ul>{profile.longitudinal_open_questions.slice(0, 5).map((item, i) => <li key={i}>{item.question}</li>)}</ul>
            </>
          )}
          {profile.longitudinal_limitations.length > 0 && <p className="meta">Limitaciones: {profile.longitudinal_limitations.join(" · ")}</p>}
          <p className="meta">Las lagunas documentales no son prueba de ausencia ni de mejoría. Las hipótesis deben comprobarse con las fuentes.</p>
        </section>
      ) : (
        <p className="meta">
          {profile.longitudinal_consent_active
            ? "No hay síntesis longitudinal activa. La nota editable de abajo es un campo de compatibilidad y no sustituye la formulación completa."
            : "El consentimiento para análisis longitudinal no figura como activo; el modelo no ofrece una síntesis nueva."}
        </p>
      )}
      <p className="meta">
        {profile.portrait_edited_by_clinician
          ? "El siguiente campo contiene una corrección profesional manual."
          : "El siguiente campo conserva el perfil editable previo por compatibilidad; la síntesis longitudinal de arriba es la lectura general del modelo."}
      </p>

      {canEdit ? (
        <>
          <textarea
            rows={7}
            value={portraitDraft}
            placeholder="Corrección profesional opcional. La síntesis longitudinal se genera por separado."
            onChange={(e) => setPortraitDraft(e.target.value)}
          />
          <div className="alert-actions">
            <button
              type="button"
              className="btn-secondary"
              disabled={busy || portraitDraft === (profile.portrait || "")}
              onClick={() => void save({ portrait: portraitDraft }, "Retrato guardado.")}
            >
              {busy ? "Guardando…" : "Guardar retrato"}
            </button>
            {profile.previous_portrait && (
              <button type="button" className="btn-secondary" onClick={() => setShowPrevious((v) => !v)}>
                {showPrevious ? "Ocultar versión anterior" : "Ver versión anterior"}
              </button>
            )}
          </div>
        </>
      ) : (
        <p>{profile.portrait || "Todavía no hay retrato."}</p>
      )}

      {showPrevious && profile.previous_portrait && (
        <blockquote className="meta">
          <strong>Versión {Math.max(profile.portrait_version - 1, 0)}:</strong>{" "}
          {profile.previous_portrait}
        </blockquote>
      )}

      <h3>Temas abiertos</h3>
      <p className="meta">
        Es la agenda que el asistente sigue con el paciente, no un cuestionario. Lo que pongas aquí
        es lo que intentará retomar; lo que quites, deja de sacarlo.
      </p>
      {profile.open_threads.length === 0 ? (
        <p className="meta">Ninguno ahora mismo.</p>
      ) : (
        <ul className="thread-list">
          {profile.open_threads.map((t) => (
            <li key={t.topic}>
              <strong>{t.topic}</strong>
              {t.note && <span className="meta"> — {t.note}</span>}
              {t.source === "clinician" && <span className="meta"> · añadido por un profesional</span>}
              {canEdit && (
                <button type="button" className="btn-secondary" onClick={() => removeThread(t.topic)}>
                  Cerrar
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <div className="alert-actions">
          <input
            type="text"
            value={threadDraft}
            placeholder="Qué te gustaría que explorase"
            onChange={(e) => setThreadDraft(e.target.value)}
          />
          <button type="button" className="btn-secondary" disabled={busy || !threadDraft.trim()} onClick={addThread}>
            Añadir
          </button>
        </div>
      )}

      <h3>Cómo puntúa habitualmente</h3>
      {profile.baseline_is_usable && profile.linguistic_baseline ? (
        <>
          <p className="meta">
            Sobre {profile.linguistic_baseline_n} textos suyos. El motor compara cada texto nuevo
            con estos valores además de con los umbrales fijos, nunca en lugar de ellos.
          </p>
          <dl className="llm-active-grid">
            {Object.entries(profile.linguistic_baseline).map(([axis, stats]) => (
              <div key={axis}>
                <dt>{AXIS_LABELS[axis] || axis}</dt>
                <dd>
                  {stats.mean.toFixed(2)} <span className="meta">± {stats.std.toFixed(2)}</span>
                </dd>
              </div>
            ))}
          </dl>
        </>
      ) : (
        <p className="meta">
          Todavía no hay suficiente historial ({profile.linguistic_baseline_n} de{" "}
          {profile.minimum_signals_for_baseline} textos). Hasta entonces se evalúa solo con los
          umbrales fijos, igual que antes.
        </p>
      )}
      {saved && <p className="info">{saved}</p>}
      {!hasPortrait && !canEdit && <p className="meta">Solo el terapeuta asignado puede editarlo.</p>}
    </div>
  );
}
