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
  manner: { topic_drop?: boolean; length_band?: string; haste?: boolean };
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
  created_at: string | null;
};

type PatientModel = {
  version_no: number;
  patient_summary: string;
  patterns: Array<Record<string, unknown>>;
  trajectories: Array<Record<string, unknown>>;
  protective_factors: Array<Record<string, unknown>>;
  contradictions: Array<Record<string, unknown>>;
  limitations: string[];
  coverage: Record<string, unknown>;
  source_watermark: string | null;
  created_at: string | null;
};

type ClinicalDocument = {
  id: string;
  original_filename: string;
  document_type: string;
  extraction_status: string;
  analysis_status: string;
  error_category: string | null;
  created_at: string | null;
};

type MemoryView = {
  linguistic_analysis_consent: boolean;
  patient_model: PatientModel | null;
  clinical_documents: ClinicalDocument[];
  formulation: Formulation | null;
  discourse: Discourse[];
  readings: Reading[];
  notices: Notice[];
  annotations: Annotation[];
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
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("clinical_report");
  const [documentDate, setDocumentDate] = useState("");

  async function load() {
    setError(null);
    try {
      const data = await api.get<MemoryView>(`/api/v1/professional/patients/${patientId}/memory`);
      setView(data);
      setTargetId((current) => current || data.discourse[0]?.id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo leer la memoria clínica.");
    }
  }

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .get<MemoryView>(`/api/v1/professional/patients/${patientId}/memory`)
      .then((data) => {
        if (cancelled) return;
        setView(data);
        setTargetId((current) => current || data.discourse[0]?.id || "");
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "No se pudo leer la memoria clínica.");
      });
    return () => {
      cancelled = true;
    };
  }, [patientId]);

  async function rebuildLongitudinalMemory() {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const result = await api.post<{ status: string; already_queued?: boolean }>(`/api/v1/professional/patients/${patientId}/memory/rebuild`);
      setInfo(result.already_queued ? "Ya hay una actualización de la memoria en cola." : "Actualización longitudinal puesta en cola; la síntesis aparecerá cuando termine el trabajador de memoria.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo programar la actualización longitudinal.");
    } finally {
      setBusy(false);
    }
  }

  async function uploadClinicalDocument(event: FormEvent) {
    event.preventDefault();
    if (!fileToUpload) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const form = new FormData();
      form.append("file", fileToUpload);
      form.append("document_type", documentType);
      if (documentDate) form.append("document_date", documentDate);
      const result = await api.upload<{ extraction_status: string; analysis_status: string; duplicate?: boolean; original_filename: string }>(
        `/api/v1/professional/patients/${patientId}/memory/documents`, form,
      );
      setFileToUpload(null);
      setDocumentDate("");
      setInfo(result.duplicate ? "Ese informe ya estaba registrado." : result.extraction_status === "needs_ocr" ? "Informe guardado, pero necesita OCR porque no se ha extraído texto." : "Informe guardado y análisis longitudinal programado.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo subir el informe clínico.");
    } finally {
      setBusy(false);
    }
  }

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

  return (
    <div>
      {error && <p className="error">{error}</p>}
      {info && <p className="info">{info}</p>}
      <section className="card">
        <h2>Formulación longitudinal de la persona</h2>
        <p className="subtitle">Síntesis general versionada del historial disponible. Es una interpretación provisional, no un diagnóstico ni una evaluación automática de riesgo.</p>
        {view.patient_model ? (
          <>
            <p className="meta">Versión {view.patient_model.version_no}{view.patient_model.created_at ? ` · generada ${formatDateTime(view.patient_model.created_at)}` : ""}{view.patient_model.source_watermark ? ` · fuentes hasta ${formatDateTime(view.patient_model.source_watermark)}` : ""}</p>
            <p className="patient-longitudinal-summary">{view.patient_model.patient_summary || "La versión actual no contiene una síntesis general."}</p>
            {view.patient_model.patterns.length > 0 && <><h3>Patrones provisionales</h3><ul>{view.patient_model.patterns.slice(0, 6).map((item, i) => <li key={i}>{String(item.pattern || "Patrón sin descripción")} <span className="meta">{String(item.uncertainty || "incertidumbre no registrada")}</span></li>)}</ul></>}
            {view.patient_model.trajectories.length > 0 && <><h3>Evolución</h3><ul>{view.patient_model.trajectories.slice(0, 6).map((item, i) => <li key={i}>{String(item.description || "Trayectoria sin descripción")} <span className="meta">{String(item.direction || "dirección no determinada")}</span></li>)}</ul></>}
            {view.patient_model.protective_factors.length > 0 && <><h3>Recursos protectores</h3><ul>{view.patient_model.protective_factors.slice(0, 5).map((item, i) => <li key={i}>{String(item.factor || "Factor sin descripción")} <span className="meta">{String(item.availability || "disponibilidad no confirmada")}</span></li>)}</ul></>}
            {view.patient_model.contradictions.length > 0 && <><h3>Contradicciones pendientes</h3><ul>{view.patient_model.contradictions.slice(0, 5).map((item, i) => <li key={i}>{String(item.topic || "Tema")}: {String(item.description || item.interpretation || "Revisión pendiente")}</li>)}</ul></>}
            {view.patient_model.limitations.length > 0 && <p className="meta">Limitaciones: {view.patient_model.limitations.join(" · ")}</p>}
          </>
        ) : (
          <p className="meta">Todavía no existe una síntesis longitudinal. Consentimiento para análisis: {view.linguistic_analysis_consent ? "activo" : "no consta activo"}. Este permiso es distinto de la autorización profesional de acceso a la ficha.</p>
        )}
        <button type="button" className="btn-secondary" disabled={busy || !canAnnotate || !view.linguistic_analysis_consent} onClick={() => void rebuildLongitudinalMemory()}>
          {busy ? "Procesando…" : "Actualizar comprensión longitudinal"}
        </button>
        <details>
          <summary>Formulación del último tramo (no describe a la persona en su conjunto)</summary>
          {view.formulation ? (
          <>
            <p>{view.formulation.l0}</p>
            <p>{view.formulation.l1}</p>
            <p className="meta">{view.formulation.l2}</p>
            {view.formulation.acute_episode && (
              <p className="meta">Este tramo está marcado como episodio agudo, no como rasgo.</p>
            )}
          </>
        ) : (
          <p className="meta">No hay una formulación del último tramo disponible.</p>
        )}
        </details>
      </section>

      <section className="card">
        <h2>Informes clínicos</h2>
        <p className="subtitle">Los informes se guardan como fuentes atribuidas. La carga no equivale a lectura ni a análisis completado.</p>
        {view.clinical_documents.length === 0 ? <p className="meta">No hay informes adjuntos.</p> : <ul>{view.clinical_documents.map((doc) => <li key={doc.id}><strong>{doc.original_filename}</strong><span className="meta"> · extracción: {doc.extraction_status} · análisis: {doc.analysis_status}{doc.error_category ? ` · ${doc.error_category}` : ""}{doc.created_at ? ` · ${formatDateTime(doc.created_at)}` : ""}</span></li>)}</ul>}
        {canAnnotate && <form onSubmit={uploadClinicalDocument}>
          <label htmlFor="clinical-document-file">Subir informe (PDF, DOCX, TXT o Markdown; hasta 15 MiB)</label>
          <input id="clinical-document-file" type="file" accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown" onChange={(event) => setFileToUpload(event.target.files?.[0] ?? null)} />
          <label htmlFor="clinical-document-type">Tipo de informe</label>
          <select id="clinical-document-type" value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
            <option value="clinical_report">Informe clínico</option><option value="discharge_summary">Informe de alta</option><option value="psychological_report">Informe psicológico</option><option value="psychiatric_report">Informe psiquiátrico</option><option value="medication_report">Informe de medicación</option><option value="other">Otro</option>
          </select>
          <label htmlFor="clinical-document-date">Fecha del informe (opcional)</label>
          <input id="clinical-document-date" type="date" value={documentDate} onChange={(event) => setDocumentDate(event.target.value)} />
          <button type="submit" disabled={busy || !fileToUpload || !view.linguistic_analysis_consent}>{busy ? "Procesando…" : "Subir y analizar informe"}</button>
        </form>}
      </section>

      <section className="card">
        <h2>Avisos para mirar</h2>
        <p className="subtitle">No son alertas de riesgo. Piden que una persona lea las citas.</p>
        {view.notices.length === 0 && <p className="meta">No hay avisos.</p>}
        <ul>
          {view.notices.map((notice) => (
            <li key={notice.id}>
              <strong>{REASONS[notice.reason] || notice.reason}</strong>
              <span className="meta">
                {" "}
                · {notice.status === "open" ? "abierto" : "visto"}
                {notice.created_at ? ` · ${formatDateTime(notice.created_at)}` : ""}
              </span>
              {canAnnotate && notice.status === "open" && (
                <div>
                  <button type="button" disabled={busy} onClick={() => acknowledge(notice.id)}>
                    Marcar como visto
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Hechos de habla</h2>
        <p className="subtitle">Lo que se dijo. No confirma que lo dicho haya ocurrido.</p>
        {view.discourse.length === 0 && <p className="meta">Sin hechos de habla.</p>}
        <ul>
          {view.discourse.map((fact) => (
            <li key={fact.id}>
              <span className="meta">
                {fact.channel === "diary" ? "Diario" : "Chat"}
                {fact.spoken_at ? ` · ${formatDateTime(fact.spoken_at)}` : ""}
              </span>
              <p>{fact.quote}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Lecturas</h2>
        <p className="subtitle">Hipótesis sobre por qué habla de eso y cómo. No son diagnósticos.</p>
        {view.readings.length === 0 && <p className="meta">Sin lecturas.</p>}
        <ul>
          {view.readings.map((reading) => (
            <li key={reading.id}>
              <span className="meta">
                {reading.kind} · incertidumbre {reading.uncertainty} · {reading.status}
              </span>
              <p>{reading.hypothesis}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Notas del profesional</h2>
        {view.annotations.length === 0 && <p className="meta">Sin notas.</p>}
        <ul>
          {view.annotations.map((item) => (
            <li key={item.id}>
              <p>{item.body}</p>
              <span className="meta">{item.created_at ? formatDateTime(item.created_at) : ""}</span>
            </li>
          ))}
        </ul>
        {canAnnotate && view.discourse.length > 0 && (
          <form onSubmit={annotate}>
            <label htmlFor="memory-target">Cita que comentas</label>
            <select
              id="memory-target"
              value={targetId}
              onChange={(event) => setTargetId(event.target.value)}
            >
              {view.discourse.map((fact) => (
                <option key={fact.id} value={fact.id}>
                  {fact.quote.slice(0, 80)}
                </option>
              ))}
            </select>
            <label htmlFor="memory-note">Nota</label>
            <textarea
              id="memory-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              maxLength={4000}
            />
            <button type="submit" disabled={busy || !note.trim()}>
              Añadir nota
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
