import { FormEvent, useEffect, useState } from "react";
import { api, formatDateTime } from "../api";

type Formulation = {
  id: string;
  l0: string;
  l1: string;
  l2: string;
  acute_episode: boolean;
  created_at: string | null;
};
type Discourse = {
  id: string;
  channel: string;
  quote: string;
  manner: { topic_drop?: boolean; length_band?: string; haste?: boolean } | null;
  spoken_at: string | null;
};
type Reading = {
  id: string;
  kind: string;
  uncertainty: string;
  hypothesis: string;
  status: string;
  created_at: string | null;
};
type Notice = {
  id: string;
  reason: string;
  status: string;
  created_at: string | null;
};
type Annotation = {
  id: string;
  body: string;
  target_type: string;
  target_id: string;
  created_at: string | null;
};
type PatientModel = {
  version_no: number;
  patient_summary: string;
  facets: Array<Record<string, unknown>>;
  patterns: Array<Record<string, unknown>>;
  trajectories: Array<Record<string, unknown>>;
  protective_factors: Array<Record<string, unknown>>;
  contradictions: Array<Record<string, unknown>>;
  open_questions: Array<Record<string, unknown>>;
  limitations: string[];
  coverage: Record<string, unknown>;
  source_watermark: string | null;
  created_at: string | null;
};

type MemoryView = {
  linguistic_analysis_consent?: boolean;
  patient_model?: PatientModel | null;
  formulation: Formulation | null;
  formulation_history?: Array<{ id: string; l0: string; acute_episode: boolean; created_at: string | null }>;
  discourse?: Discourse[];
  readings?: Reading[];
  notices?: Notice[];
  annotations?: Annotation[];
};

const REASONS: Record<string, string> = {
  medication_talk_without_act: "Habla de la medicación. Eso no confirma la toma.",
  manner_shift: "La manera de hablar cambió respecto de la suya anterior.",
  contradiction: "Hay dichos que no coinciden entre conversaciones.",
  avoidance: "Deja el tema a mitad en más de un tramo.",
  acute_new_topic: "Aparece un tema agudo que no estaba en la memoria reciente.",
};

export default function ClinicalMemoryPanel({
  patientId,
  canAnnotate,
}: {
  patientId: string;
  canAnnotate: boolean;
}) {
  const [view, setView] = useState<MemoryView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [targetId, setTargetId] = useState("");
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const data = await api.get<MemoryView>(`/api/v1/professional/patients/${patientId}/memory`);
      setView({
        ...data,
        discourse: Array.isArray(data.discourse) ? data.discourse : [],
        readings: Array.isArray(data.readings) ? data.readings : [],
        notices: Array.isArray(data.notices) ? data.notices : [],
        annotations: Array.isArray(data.annotations) ? data.annotations : [],
        formulation_history: Array.isArray(data.formulation_history) ? data.formulation_history : [],
      });
      setTargetId((current) => current || data.discourse?.[0]?.id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo leer la memoria clínica.");
    }
  }

  useEffect(() => {
    let cancelled = false;
    setView(null);
    setError(null);
    api
      .get<MemoryView>(`/api/v1/professional/patients/${patientId}/memory`)
      .then((data) => {
        if (cancelled) return;
        setView({
          ...data,
          discourse: Array.isArray(data.discourse) ? data.discourse : [],
          readings: Array.isArray(data.readings) ? data.readings : [],
          notices: Array.isArray(data.notices) ? data.notices : [],
          annotations: Array.isArray(data.annotations) ? data.annotations : [],
          formulation_history: Array.isArray(data.formulation_history) ? data.formulation_history : [],
        });
        setTargetId(data.discourse?.[0]?.id || "");
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "No se pudo leer la memoria clínica.");
      });
    return () => {
      cancelled = true;
    };
  }, [patientId]);

  async function acknowledge(noticeId: string) {
    setBusy(true);
    setInfo(null);
    try {
      await api.post(`/api/v1/professional/patients/${patientId}/memory/notices/${noticeId}/acknowledge`);
      setInfo("Aviso marcado como visto. El registro sigue en la memoria.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo marcar el aviso.");
    } finally {
      setBusy(false);
    }
  }

  async function annotate(event: FormEvent) {
    event.preventDefault();
    if (!targetId || !note.trim()) return;
    setBusy(true);
    setInfo(null);
    try {
      await api.post(`/api/v1/professional/patients/${patientId}/memory/annotations`, {
        body: note.trim(),
        target_type: "discourse",
        target_id: targetId,
      });
      setNote("");
      setInfo("Nota añadida. No sustituye lo que se dijo.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la nota.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !view) return <p className="error">{error}</p>;
  if (!view) return <p className="meta">Cargando memoria clínica…</p>;

  const discourse = view.discourse ?? [];
  const readings = view.readings ?? [];
  const notices = view.notices ?? [];
  const annotations = view.annotations ?? [];
  const history = view.formulation_history ?? [];

  return (
    <div>
      {error && <p className="error">{error}</p>}
      {info && <p className="info">{info}</p>}
      <section className="card">
        <h2>Comprensión longitudinal de la persona</h2>
        {!view.linguistic_analysis_consent ? (
          <p className="meta">No se muestra una síntesis longitudinal porque el consentimiento de análisis no figura activo.</p>
        ) : view.patient_model?.patient_summary ? (
          <>
            <p>{view.patient_model.patient_summary}</p>
            <p className="meta">
              Versión {view.patient_model.version_no}
              {view.patient_model.created_at ? ` · sintetizada ${formatDateTime(view.patient_model.created_at)}` : ""}
              {view.patient_model.source_watermark ? ` · fuentes hasta ${formatDateTime(view.patient_model.source_watermark)}` : ""}
            </p>
            {view.patient_model.facets.length > 0 && <>
              <h3>Facetas y circunstancias</h3>
              <ul>{view.patient_model.facets.slice(0, 12).map((item, index) => <li key={String(item.id ?? item.statement ?? index)}>{String(item.statement ?? item.summary ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {view.patient_model.patterns.length > 0 && <>
              <h3>Patrones recurrentes</h3>
              <ul>{view.patient_model.patterns.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.statement ?? index)}>{String(item.statement ?? item.description ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {view.patient_model.trajectories.length > 0 && <>
              <h3>Evolución temporal</h3>
              <ul>{view.patient_model.trajectories.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.topic ?? index)}>{String(item.statement ?? item.description ?? item.topic ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {view.patient_model.protective_factors.length > 0 && <>
              <h3>Fortalezas y factores protectores</h3>
              <ul>{view.patient_model.protective_factors.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.statement ?? index)}>{String(item.statement ?? item.description ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {view.patient_model.contradictions.length > 0 && <>
              <h3>Contradicciones que requieren revisión</h3>
              <ul>{view.patient_model.contradictions.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.statement ?? index)}>{String(item.statement ?? item.description ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {view.patient_model.open_questions.length > 0 && <>
              <h3>Preguntas abiertas</h3>
              <ul>{view.patient_model.open_questions.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.question ?? index)}>{String(item.question ?? item.statement ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {view.patient_model.limitations.length > 0 && <p className="meta">Limitaciones: {view.patient_model.limitations.join(" · ")}</p>}
          </>
        ) : (
          <p className="meta">Aún no hay una síntesis longitudinal disponible. La formulación del último tramo se muestra por separado y no representa por sí sola a toda la persona.</p>
        )}
      </section>

      <section className="card">
        <h2>Formulación del último tramo</h2>
        {view.formulation ? (
          <>
            <p>{view.formulation.l0}</p>
            <p>{view.formulation.l1}</p>
            <p className="meta">{view.formulation.l2}</p>
            {view.formulation.acute_episode && <p className="meta">Este tramo está marcado como episodio agudo, no como rasgo.</p>}
            {view.formulation.created_at && <p className="meta">Actualizada: {formatDateTime(view.formulation.created_at)}</p>}
          </>
        ) : <p className="meta">No hay una formulación del último tramo disponible.</p>}
      </section>

      {history.length > 0 && <section className="card">
        <h2>Versiones anteriores</h2>
        <ul>{history.map((item) => <li key={item.id}>
          <p>{item.l0}</p>
          <span className="meta">{item.acute_episode ? "Episodio agudo" : "Síntesis del tramo"}{item.created_at ? ` · ${formatDateTime(item.created_at)}` : ""}</span>
        </li>)}</ul>
      </section>}

      <section className="card">
        <h2>Avisos para mirar</h2>
        <p className="subtitle">No son alertas de riesgo. Piden que una persona lea las citas.</p>
        {notices.length === 0 ? <p className="meta">No hay avisos.</p> : <ul>{notices.map((notice) => <li key={notice.id}>
          <strong>{REASONS[notice.reason] || notice.reason}</strong>
          <span className="meta"> · {notice.status === "open" ? "abierto" : "visto"}{notice.created_at ? ` · ${formatDateTime(notice.created_at)}` : ""}</span>
          {canAnnotate && notice.status === "open" && <div><button type="button" disabled={busy} onClick={() => acknowledge(notice.id)}>Marcar como visto</button></div>}
        </li>)}</ul>}
      </section>

      <section className="card">
        <h2>Hechos de habla</h2>
        <p className="subtitle">Lo que se dijo. No confirma que lo dicho haya ocurrido.</p>
        {discourse.length === 0 ? <p className="meta">Sin hechos de habla.</p> : <ul>{discourse.map((fact) => <li key={fact.id}>
          <span className="meta">{fact.channel === "diary" ? "Diario" : "Chat"}{fact.spoken_at ? ` · ${formatDateTime(fact.spoken_at)}` : ""}</span>
          <p>{fact.quote}</p>
        </li>)}</ul>}
      </section>

      <section className="card">
        <h2>Lecturas</h2>
        <p className="subtitle">Hipótesis sobre por qué habla de eso y cómo. No son diagnósticos.</p>
        {readings.length === 0 ? <p className="meta">Sin lecturas.</p> : <ul>{readings.map((reading) => <li key={reading.id}>
          <span className="meta">{reading.kind} · incertidumbre {reading.uncertainty} · {reading.status}</span>
          <p>{reading.hypothesis}</p>
        </li>)}</ul>}
      </section>

      <section className="card">
        <h2>Notas del profesional</h2>
        {annotations.length === 0 ? <p className="meta">Sin notas.</p> : <ul>{annotations.map((item) => <li key={item.id}>
          <p>{item.body}</p><span className="meta">{item.created_at ? formatDateTime(item.created_at) : ""}</span>
        </li>)}</ul>}
        {canAnnotate && discourse.length > 0 && <form onSubmit={annotate}>
          <label htmlFor="memory-target">Cita que comentas</label>
          <select id="memory-target" value={targetId} onChange={(event) => setTargetId(event.target.value)}>
            {discourse.map((fact) => <option key={fact.id} value={fact.id}>{fact.quote.slice(0, 80)}</option>)}
          </select>
          <label htmlFor="memory-note">Nota</label>
          <textarea id="memory-note" value={note} onChange={(event) => setNote(event.target.value)} rows={3} maxLength={4000} />
          <button type="submit" disabled={busy || !note.trim()}>Añadir nota</button>
        </form>}
      </section>
    </div>
  );
}
