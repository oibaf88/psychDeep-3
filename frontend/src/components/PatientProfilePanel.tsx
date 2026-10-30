import { useCallback, useEffect, useRef, useState } from "react";

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
  longitudinal_facets: Array<Record<string, unknown>>;
  longitudinal_patterns: Array<Record<string, unknown>>;
  longitudinal_trajectories: Array<Record<string, unknown>>;
  longitudinal_protective_factors: Array<Record<string, unknown>>;
  longitudinal_contradictions: Array<Record<string, unknown>>;
  longitudinal_open_questions: Array<Record<string, unknown>>;
  longitudinal_limitations: string[];
  longitudinal_consent_active: boolean;
  clinical_document_analysis_consent: boolean;
}

interface PatientClinicalDocument {
  id: string;
  original_filename: string;
  media_type: string;
  file_size_bytes: number;
  text_truncated: boolean;
  extraction_status: "text_extracted" | "failed";
  analysis_status: "queued" | "analysing" | "analysed" | "failed" | "consent_revoked";
  error_category: string | null;
  patient_model_version_id: string | null;
  uploaded_at: string;
  analyzed_at: string | null;
}

function documentStatusLabel(document: PatientClinicalDocument): string {
  if (document.extraction_status === "failed") return "No se pudo extraer texto";
  switch (document.analysis_status) {
    case "queued": return "En cola";
    case "analysing": return "Analizando";
    case "analysed": return "Incluido en la memoria";
    case "consent_revoked": return "Análisis detenido por consentimiento revocado";
    case "failed": return "Análisis pendiente de revisión";
    default: return document.analysis_status;
  }
}

function normalizeProfile(data: PatientProfile): PatientProfile {
  const raw = data as PatientProfile & Record<string, unknown>;
  const listOfRecords = (value: unknown): Array<Record<string, unknown>> =>
    Array.isArray(value) ? value.filter(
      (item): item is Record<string, unknown> =>
        item !== null && typeof item === "object" && !Array.isArray(item),
    ) : [];
  return {
    ...raw,
    portrait: typeof raw.portrait === "string" ? raw.portrait : null,
    previous_portrait: typeof raw.previous_portrait === "string" ? raw.previous_portrait : null,
    portrait_version: typeof raw.portrait_version === "number" ? raw.portrait_version : 0,
    portrait_edited_by_clinician: raw.portrait_edited_by_clinician === true,
    open_threads: Array.isArray(raw.open_threads) ? raw.open_threads.filter(
      (item): item is OpenThread => Boolean(item && typeof item.topic === "string"),
    ) : [],
    linguistic_baseline: raw.linguistic_baseline && typeof raw.linguistic_baseline === "object" && !Array.isArray(raw.linguistic_baseline)
      ? raw.linguistic_baseline : null,
    linguistic_baseline_n: typeof raw.linguistic_baseline_n === "number" ? raw.linguistic_baseline_n : 0,
    baseline_is_usable: raw.baseline_is_usable === true,
    minimum_signals_for_baseline: typeof raw.minimum_signals_for_baseline === "number" ? raw.minimum_signals_for_baseline : 0,
    longitudinal_summary: typeof raw.longitudinal_summary === "string" ? raw.longitudinal_summary : null,
    longitudinal_model_version: typeof raw.longitudinal_model_version === "number" ? raw.longitudinal_model_version : null,
    longitudinal_created_at: typeof raw.longitudinal_created_at === "string" ? raw.longitudinal_created_at : null,
    longitudinal_source_watermark: typeof raw.longitudinal_source_watermark === "string" ? raw.longitudinal_source_watermark : null,
    longitudinal_coverage: raw.longitudinal_coverage && typeof raw.longitudinal_coverage === "object" && !Array.isArray(raw.longitudinal_coverage)
      ? raw.longitudinal_coverage as Record<string, unknown> : {},
    longitudinal_facets: listOfRecords(raw.longitudinal_facets),
    longitudinal_patterns: listOfRecords(raw.longitudinal_patterns),
    longitudinal_trajectories: listOfRecords(raw.longitudinal_trajectories),
    longitudinal_protective_factors: listOfRecords(raw.longitudinal_protective_factors),
    longitudinal_contradictions: listOfRecords(raw.longitudinal_contradictions),
    longitudinal_open_questions: listOfRecords(raw.longitudinal_open_questions),
    longitudinal_limitations: Array.isArray(raw.longitudinal_limitations)
      ? raw.longitudinal_limitations.filter((item): item is string => typeof item === "string") : [],
    longitudinal_consent_active: raw.longitudinal_consent_active === true,
    clinical_document_analysis_consent: raw.clinical_document_analysis_consent === true,
  };
}

export function formatLongitudinalItem(
  item: Record<string, unknown>,
  preferredFields: string[],
): string {
  for (const field of preferredFields) {
    const value = item[field];
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number" || typeof value === "boolean") return String(value);
  }
  try {
    return JSON.stringify(item) ?? "Detalle no disponible";
  } catch {
    return "Detalle no disponible";
  }
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
  const [documents, setDocuments] = useState<PatientClinicalDocument[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<File | null>(null);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [documentsMessage, setDocumentsMessage] = useState<string | null>(null);
  const [documentBusy, setDocumentBusy] = useState(false);
  const [memoryBusy, setMemoryBusy] = useState(false);
  const previouslyPending = useRef(false);
  const documentInput = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api
      .get<PatientProfile>(`/api/v1/professional/patients/${patientId}/profile`)
      .then((data) => {
        const normalized = normalizeProfile(data);
        setProfile(normalized);
        setPortraitDraft(normalized.portrait || "");
        setError(null);
      })
      .catch((e) => setError((e as Error).message));
  }, [patientId]);

  const loadDocuments = useCallback(() => {
    api
      .get<PatientClinicalDocument[]>(`/api/v1/professional/patients/${patientId}/documents`)
      .then((rows) => {
        setDocuments(Array.isArray(rows) ? rows : []);
        setDocumentsError(null);
      })
      .catch((e) => setDocumentsError((e as Error).message));
  }, [patientId]);

  useEffect(() => {
    load();
    loadDocuments();
  }, [load, loadDocuments]);

  const hasPendingAnalysis = documents.some((doc) => doc.analysis_status === "queued" || doc.analysis_status === "analysing");

  useEffect(() => {
    if (!hasPendingAnalysis) return;
    const timer = window.setInterval(loadDocuments, 8000);
    return () => window.clearInterval(timer);
  }, [hasPendingAnalysis, loadDocuments]);

  useEffect(() => {
    if (previouslyPending.current && !hasPendingAnalysis) load();
    previouslyPending.current = hasPendingAnalysis;
  }, [hasPendingAnalysis, load]);

  async function save(body: Record<string, unknown>, message: string) {
    setBusy(true);
    setSaved(null);
    try {
      const next = await api.put<PatientProfile>(
        `/api/v1/professional/patients/${patientId}/profile`,
        body,
      );
      const normalized = normalizeProfile(next);
      setProfile(normalized);
      setPortraitDraft(normalized.portrait || "");
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

  async function uploadDocument() {
    if (!selectedDocument) return;
    setDocumentBusy(true);
    setDocumentsError(null);
    setDocumentsMessage(null);
    try {
      const body = new FormData();
      body.append("file", selectedDocument);
      const uploaded = await api.upload<PatientClinicalDocument>(
        `/api/v1/professional/patients/${patientId}/documents`,
        body,
      );
      setDocuments((current) => [uploaded, ...current.filter((item) => item.id !== uploaded.id)]);
      setDocumentsMessage(uploaded.extraction_status === "failed"
        ? "El archivo quedó guardado, pero no se encontró texto extraíble. Los PDF escaneados requieren OCR antes de subirlos."
        : "Documento guardado. El análisis longitudinal se ha añadido a la cola.");
      setSelectedDocument(null);
      if (documentInput.current) documentInput.current.value = "";
      loadDocuments();
    } catch (e) {
      setDocumentsError((e as Error).message);
    } finally {
      setDocumentBusy(false);
    }
  }

  async function rebuildMemory() {
    setMemoryBusy(true);
    setDocumentsError(null);
    setDocumentsMessage(null);
    try {
      const result = await api.post<{ status: string; message: string }>(
        `/api/v1/professional/patients/${patientId}/memory/rebuild`,
      );
      setDocumentsMessage(result.message);
      loadDocuments();
    } catch (e) {
      setDocumentsError((e as Error).message);
    } finally {
      setMemoryBusy(false);
    }
  }

  async function downloadDocument(item: PatientClinicalDocument) {
    setDocumentsError(null);
    try {
      const blob = await api.download(
        `/api/v1/professional/patients/${patientId}/documents/${item.id}/download`,
      );
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = item.original_filename;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (e) {
      setDocumentsError((e as Error).message);
    }
  }

  if (error) return <p className="error">No se pudo cargar el perfil: {error}</p>;
  if (!profile) return <PsychDeepLoader size="sm" label="Cargando perfil…" />;

  const hasPortrait = Boolean(profile.portrait);

  return (
    <div className="profile-panel">
      <h3>Retrato editable del profesional</h3>
      {profile.portrait_edited_by_clinician ? (
        <p className="meta">
          Corregido por un profesional. El analizador puede añadir, pero se le indica que no
          contradiga lo que has escrito.
        </p>
      ) : (
        <p className="meta">
          Lo ha acumulado el sistema a partir de lo que el paciente ha ido contando. Es un resumen
          de un modelo: si algo no encaja, corrígelo.
        </p>
      )}

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

      <section className="card" aria-labelledby="longitudinal-patient-model">
        <h3 id="longitudinal-patient-model">Comprensión longitudinal de la persona</h3>
        {!profile.longitudinal_consent_active ? (
          <p className="meta">El modelo longitudinal no se muestra porque el consentimiento de análisis no figura activo.</p>
        ) : profile.longitudinal_summary ? (
          <>
            <p>{profile.longitudinal_summary}</p>
            <p className="meta">
              Versión {profile.longitudinal_model_version ?? "—"}
              {profile.longitudinal_created_at ? ` · sintetizada ${new Date(profile.longitudinal_created_at).toLocaleString()}` : ""}
              {profile.longitudinal_source_watermark ? ` · fuentes hasta ${new Date(profile.longitudinal_source_watermark).toLocaleDateString()}` : ""}
            </p>
            {Object.keys(profile.longitudinal_coverage || {}).length > 0 && (
              <details><summary>Cobertura del registro</summary><pre>{JSON.stringify(profile.longitudinal_coverage, null, 2)}</pre></details>
            )}
            {profile.longitudinal_facets.length > 0 && <>
              <h4>Facetas y circunstancias</h4>
              <ul>{profile.longitudinal_facets.slice(0, 12).map((item, index) => <li key={String(item.id ?? item.statement ?? index)}>{String(item.statement ?? item.summary ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {profile.longitudinal_patterns.length > 0 && <>
              <h4>Patrones recurrentes</h4>
              <ul>{profile.longitudinal_patterns.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.statement ?? index)}>{String(item.statement ?? item.description ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {profile.longitudinal_trajectories.length > 0 && <>
              <h4>Evolución temporal</h4>
              <ul>{profile.longitudinal_trajectories.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.topic ?? index)}>{String(item.statement ?? item.description ?? item.topic ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {profile.longitudinal_protective_factors.length > 0 && <>
              <h4>Fortalezas y factores protectores</h4>
              <ul>{profile.longitudinal_protective_factors.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.statement ?? index)}>{String(item.statement ?? item.description ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {profile.longitudinal_contradictions.length > 0 && <>
              <h4>Contradicciones que requieren revisión</h4>
              <ul>{profile.longitudinal_contradictions.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.statement ?? index)}>{String(item.statement ?? item.description ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {profile.longitudinal_open_questions.length > 0 && <>
              <h4>Preguntas abiertas</h4>
              <ul>{profile.longitudinal_open_questions.slice(0, 8).map((item, index) => <li key={String(item.id ?? item.question ?? index)}>{String(item.question ?? item.statement ?? JSON.stringify(item))}</li>)}</ul>
            </>}
            {profile.longitudinal_limitations.length > 0 && <p className="meta">Limitaciones: {profile.longitudinal_limitations.join(" · ")}</p>}
          </>
        ) : (
          <p className="meta">Aún no hay una síntesis longitudinal disponible con los consentimientos vigentes. El retrato editable de arriba no se sustituye por comentarios recientes.</p>
        )}
      </section>

      <section className="card" aria-labelledby="clinical-documents-heading">
        <h3 id="clinical-documents-heading">Informes y documentos clínicos</h3>
        <p className="meta">
          El documento original se guarda en el expediente privado. Con ambos consentimientos activos,
          el texto extraído se incorpora como fuente atribuida al profesional en la síntesis longitudinal y en la
          memoria contextual. Los patrones psicológicos son hipótesis revisables, no diagnósticos.
        </p>
        <p className="meta">Admite PDF con texto, DOCX y TXT de hasta 8 MiB. Los PDF escaneados no tienen OCR automático.</p>
        {canEdit && profile.longitudinal_consent_active && profile.clinical_document_analysis_consent && (
          <div className="alert-actions">
            <label htmlFor="patient-clinical-document">Añadir informe clínico</label>
            <input
              id="patient-clinical-document"
              ref={documentInput}
              type="file"
              accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
              disabled={documentBusy}
              onChange={(event) => setSelectedDocument(event.target.files?.[0] ?? null)}
            />
            <button type="button" className="btn-secondary" disabled={documentBusy || !selectedDocument} onClick={() => void uploadDocument()}>
              {documentBusy ? "Guardando…" : "Subir y analizar"}
            </button>
          </div>
        )}
        {canEdit && (!profile.longitudinal_consent_active || !profile.clinical_document_analysis_consent) && (
          <p className="meta">Para subir y analizar informes, la persona debe autorizar “Análisis lingüístico” y “Análisis de informes clínicos” en Consentimientos.</p>
        )}
        {!canEdit && <p className="meta">Solo el terapeuta asignado puede añadir documentos o solicitar un nuevo análisis.</p>}
        {canEdit && profile.longitudinal_consent_active && (
          <div className="alert-actions">
            <button type="button" className="btn-secondary" disabled={memoryBusy || hasPendingAnalysis} onClick={() => void rebuildMemory()}>
              {memoryBusy ? "Añadiendo…" : hasPendingAnalysis ? "Análisis en curso…" : profile.clinical_document_analysis_consent ? "Analizar historial y documentos" : "Analizar historial disponible"}
            </button>
            <button type="button" className="btn-secondary" onClick={() => { load(); loadDocuments(); }}>
              Actualizar estado
            </button>
          </div>
        )}
        {documentsError && <p className="error" role="alert">{documentsError}</p>}
        {documentsMessage && <p className="info" role="status">{documentsMessage}</p>}
        {documents.length === 0 ? (
          <p className="meta">Todavía no hay documentos clínicos asociados.</p>
        ) : (
          <ul className="plain-list">
            {documents.map((item) => (
              <li key={item.id}>
                <strong>{item.original_filename}</strong>
                <span className="meta"> · {documentStatusLabel(item)} · {new Date(item.uploaded_at).toLocaleString()}</span>
                {item.patient_model_version_id && <span className="meta"> · versión {item.patient_model_version_id.slice(0, 8)}</span>}
                {item.text_truncated && <span className="meta"> · texto limitado por tamaño</span>}
                {item.error_category === "no_extractable_text" && <span className="meta"> · puede ser un escaneo que requiera OCR</span>}
                <button type="button" className="btn-secondary" aria-label={`Descargar original: ${item.original_filename}`} onClick={() => void downloadDocument(item)}>
                  Descargar original
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

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
                <button type="button" className="btn-secondary" aria-label={`Cerrar tema: ${t.topic}`} onClick={() => removeThread(t.topic)}>
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
            aria-label="Nuevo tema a explorar"
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
