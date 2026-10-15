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
  facets: { domain?: string; statement: string; perspective?: string; status?: string; uncertainty?: string; time_scope?: string; source_refs?: string[] }[];
  patterns: { domain?: string; pattern: string; temporal_description?: string; uncertainty?: string; source_refs?: string[] }[];
  trajectories: { domain?: string; direction?: string; description: string; uncertainty?: string; source_refs?: string[] }[];
  protective_factors: { factor: string; availability?: string; uncertainty?: string; source_refs?: string[] }[];
  contradictions: { topic?: string; description: string; interpretation?: string; uncertainty?: string; source_refs?: string[] }[];
  open_questions: { question: string; rationale?: string; priority?: number }[];
  theme_gaps: { description: string }[];
  limitations: string[];
  coverage: Record<string, unknown>;
  source_watermark: string | null;
  created_at: string | null;
};

type ClinicalDocument = {
  id: string;
  original_filename: string;
  document_type: string;
  file_size_bytes: number;
  extraction_status: string;
  analysis_status: string;
  error_category: string | null;
  created_at: string | null;
  analyzed_at: string | null;
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
  patient_model: PatientModel | null;
  clinical_documents: ClinicalDocument[];
  linguistic_analysis_consent: boolean;
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
  const [documentFile, setDocumentFile] = useState<File | null>(null);
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
      const result = await api.post<{ status: string; already_queued?: boolean }>(
        `/api/v1/professional/patients/${patientId}/memory/rebuild`,
      );
      setInfo(result.already_queued ? "La reconstrucción de memoria ya está en cola." : "Reconstrucción programada. La formulación aparecerá al terminar el proceso en segundo plano.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo programar la reconstrucción longitudinal.");
    } finally {
      setBusy(false);
    }
  }

  async function uploadClinicalDocument(event: FormEvent) {
    event.preventDefault();
    if (!documentFile) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const form = new FormData();
      form.append("file", documentFile);
      form.append("document_type", documentType);
      if (documentDate) form.append("document_date", documentDate);
      const result = await api.upload<{ original_filename: string; extraction_status: string; analysis_status: string; duplicate?: boolean }>(
        `/api/v1/professional/patients/${patientId}/memory/documents`,
        form,
      );
      setInfo(result.duplicate ? "El mismo informe ya estaba guardado." : result.extraction_status === "needs_ocr"
        ? "Informe guardado, pero no contiene texto extraíble; necesita OCR antes del análisis."
        : "Informe guardado y enviado a la cola de análisis longitudinal.");
      setDocumentFile(null);
      setDocumentDate("");
      const fileInput = document.getElementById("clinical-memory-report") as HTMLInputElement | null;
      if (fileInput) fileInput.value = "";
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
        <h2>Formulación longitudinal</h2>
        <p className="subtitle">Síntesis de la persona y su evolución a través de las fuentes disponibles; no es una respuesta a la última intervención ni un diagnóstico.</p>
        {view.patient_model ? (
          <>
            <p>{view.patient_model.patient_summary || "La última versión no contiene un resumen textual."}</p>
            <p className="meta">Versión {view.patient_model.version_no}{view.patient_model.created_at ? ` · generada ${formatDateTime(view.patient_model.created_at)}` : ""}{view.patient_model.source_watermark ? ` · evidencia hasta ${formatDateTime(view.patient_model.source_watermark)}` : ""}</p>
            {view.patient_model.facets.length > 0 && (
              <>
                <h3>Facetas documentadas</h3>
                <ul>{view.patient_model.facets.slice(0, 8).map((facet, i) => <li key={`${facet.domain || "facet"}-${i}`}><strong>{facet.domain || "Contexto"}:</strong> {facet.statement} <span className="meta">({facet.uncertainty || "incertidumbre no indicada"}; {facet.status || "estado no indicado"})</span></li>)}</ul>
              </>
            )}
            {view.patient_model.patterns.length > 0 && (
              <>
                <h3>Patrones longitudinales provisionales</h3>
                <ul>{view.patient_model.patterns.slice(0, 5).map((item, i) => <li key={`${item.domain || "pattern"}-${i}`}>{item.pattern}<span className="meta"> · {item.uncertainty || "incertidumbre no indicada"}</span></li>)}</ul>
              </>
            )}
            {view.patient_model.trajectories.length > 0 && (
              <>
                <h3>Trayectorias</h3>
                <ul>{view.patient_model.trajectories.slice(0, 5).map((item, i) => <li key={`${item.domain || "trajectory"}-${i}`}><strong>{item.direction || "Evolución no clasificada"}:</strong> {item.description}</li>)}</ul>
              </>
            )}
            {view.patient_model.protective_factors.length > 0 && (
              <>
                <h3>Fortalezas y apoyos registrados</h3>
                <ul>{view.patient_model.protective_factors.slice(0, 5).map((item, i) => <li key={i}>{item.factor}<span className="meta"> · {item.availability || "disponibilidad no confirmada"}</span></li>)}</ul>
              </>
            )}
            {view.patient_model.contradictions.length > 0 && (
              <>
                <h3>Contradicciones pendientes de aclarar</h3>
                <ul>{view.patient_model.contradictions.slice(0, 5).map((item, i) => <li key={i}><strong>{item.topic || "Tema"}:</strong> {item.description}<span className="meta"> · {item.uncertainty || "incertidumbre no indicada"}</span></li>)}</ul>
              </>
            )}
            {view.patient_model.open_questions.length > 0 && (
              <>
                <h3>Preguntas abiertas</h3>
                <ul>{view.patient_model.open_questions.slice(0, 5).map((item, i) => <li key={i}>{item.question}</li>)}</ul>
              </>
            )}
            {view.patient_model.limitations.length > 0 && <p className="meta">Límites de la síntesis: {view.patient_model.limitations.join(" · ")}</p>}
            <p className="meta">Las lagunas del registro indican falta de datos, no ausencia de problemas ni mejoría. Las hipótesis deben cotejarse con las fuentes citadas.</p>
          </>
        ) : (
          <>
            <p className="meta">{view.linguistic_analysis_consent
              ? "No hay una versión longitudinal activa. Esto no implica que falten permisos: puede que la síntesis nunca se haya ejecutado o que el trabajador de memoria no haya terminado."
              : "El consentimiento de análisis lingüístico no figura como activo para este paciente; la síntesis longitudinal no se inicia mientras siga así."}</p>
            {canAnnotate && view.linguistic_analysis_consent && <button type="button" className="btn-secondary" disabled={busy} onClick={() => void rebuildLongitudinalMemory()}>{busy ? "Programando…" : "Construir / actualizar formulación longitudinal"}</button>}
          </>
        )}
      </section>

      <section className="card">
        <h2>Informes clínicos</h2>
        <p className="subtitle">Los informes se guardan como fuentes diferenciadas, se atribuyen al profesional que los aporta y pasan por la misma memoria longitudinal. Los PDF escaneados quedan identificados como pendientes de OCR.</p>
        {canAnnotate && view.linguistic_analysis_consent && (
          <form onSubmit={uploadClinicalDocument}>
            <label htmlFor="clinical-memory-report">Informe (PDF, DOCX, TXT o Markdown; máximo 15 MiB)</label>
            <input id="clinical-memory-report" type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setDocumentFile(event.target.files?.[0] || null)} />
            <label htmlFor="clinical-memory-document-type">Tipo de informe</label>
            <select id="clinical-memory-document-type" value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
              <option value="clinical_report">Informe clínico</option>
              <option value="discharge_summary">Informe de alta</option>
              <option value="psychological_report">Informe psicológico</option>
              <option value="psychiatric_report">Informe psiquiátrico</option>
              <option value="medication_report">Informe de medicación</option>
              <option value="other">Otro</option>
            </select>
            <label htmlFor="clinical-memory-document-date">Fecha del informe (opcional)</label>
            <input id="clinical-memory-document-date" type="date" value={documentDate} onChange={(event) => setDocumentDate(event.target.value)} />
            <button type="submit" disabled={busy || !documentFile}>{busy ? "Procesando…" : "Subir y analizar informe"}</button>
          </form>
        )}
        {view.clinical_documents.length === 0 ? <p className="meta">Todavía no se han añadido informes clínicos.</p> : (
          <ul>{view.clinical_documents.map((document) => (
            <li key={document.id}>
              <strong>{document.original_filename}</strong>
              <span className="meta"> · extracción: {document.extraction_status} · análisis: {document.analysis_status}{document.created_at ? ` · cargado ${formatDateTime(document.created_at)}` : ""}</span>
              {document.extraction_status === "needs_ocr" && <p className="meta">No se pudo extraer texto de este PDF. El original permanece guardado; necesita OCR para incorporarse a la síntesis.</p>}
              {document.error_category && document.analysis_status === "failed" && <p className="error">No se pudo programar o completar el análisis ({document.error_category}).</p>}
            </li>
          ))}</ul>
        )}
      </section>

      <section className="card">
        <h2>Lectura del último tramo</h2>
        <p className="subtitle">Esta formulación breve describe una interacción concreta. No sustituye la síntesis longitudinal que aparece arriba.</p>
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
