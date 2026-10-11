import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatDateTime } from "../api";
import PsychDeepLoader from "../components/PsychDeepLoader";

interface DiaryEntry {
  id: string;
  content: string;
  created_at: string;
}

interface ConsentRow {
  consent_type: string;
  granted: boolean;
  revoked_at?: string | null;
}

/** Linguistic analysis status, read from the patient's own consents. */
type AnalysisConsent = "granted" | "not_granted" | "unknown";

export function diaryAnalysisCopy(consent: AnalysisConsent): string {
  if (consent === "granted") {
    return "Has autorizado el análisis lingüístico: el texto de tu diario se analiza con el modelo aprobado para ayudarte, nunca para juzgarte. Puedes revocarlo cuando quieras en Consentimientos.";
  }
  if (consent === "not_granted") {
    return "El análisis lingüístico no está autorizado: tu texto se guarda y solo se revisa con reglas de seguridad deterministas (por ejemplo, señales de crisis). No se envía a ningún modelo. Puedes autorizarlo en Consentimientos.";
  }
  return "No se pudo comprobar si has autorizado el análisis lingüístico. Puedes revisarlo en Consentimientos.";
}

export default function DiaryPage() {
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [consent, setConsent] = useState<AnalysisConsent>("unknown");
  const navigate = useNavigate();

  async function load() {
    setEntries(await api.get<DiaryEntry[]>("/api/v1/diary"));
  }

  useEffect(() => {
    load()
      .catch(() => setError("No se pudieron cargar tus entradas. Inténtalo de nuevo en un momento."))
      .finally(() => setLoading(false));
    api
      .get<ConsentRow[]>("/api/v1/consents")
      .then((rows) => {
        const current = rows.find((row) => row.consent_type === "linguistic_analysis" && !row.revoked_at);
        setConsent(current?.granted ? "granted" : "not_granted");
      })
      .catch(() => setConsent("unknown"));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ entry: DiaryEntry; ui_mode: string }>("/api/v1/diary", { content });
      setContent("");
      await load();
      if (res.ui_mode === "crisis") {
        navigate("/chat"); // route through the chat, which will render the crisis screen
      }
    } catch {
      setError("No se pudo guardar la entrada. Tu texto sigue en el cuadro; inténtalo de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  const analysing = consent === "granted";

  return (
    <div className="page">
      <h1>Tu diario</h1>
      <p className="subtitle">Un espacio privado para escribir cómo estás.</p>
      <p className="meta" data-testid="diary-analysis-consent">
        {diaryAnalysisCopy(consent)} <Link to="/consents">Consentimientos</Link>
      </p>
      <form onSubmit={onSubmit} className="diary-form">
        <label htmlFor="diary-content" className="sr-only">
          Nueva entrada del diario
        </label>
        <textarea
          id="diary-content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={5}
          placeholder="¿Cómo ha ido tu día?"
        />
        <button type="submit" disabled={busy || !content.trim()}>
          {busy ? (analysing ? "Esperando análisis…" : "Guardando…") : "Guardar entrada"}
        </button>
        {busy && <PsychDeepLoader size="sm" label={analysing ? "Analizando tu entrada…" : "Guardando tu entrada…"} />}
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <section className="entries" aria-label="Entradas anteriores">
        {loading && <PsychDeepLoader size="sm" label="Cargando tus entradas…" />}
        {!loading && !error && entries.length === 0 && <p className="meta">Todavía no has escrito ninguna entrada.</p>}
        {entries.map((e) => (
          <article key={e.id} className="card">
            <time dateTime={e.created_at}>{formatDateTime(e.created_at)}</time>
            <p>{e.content}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
