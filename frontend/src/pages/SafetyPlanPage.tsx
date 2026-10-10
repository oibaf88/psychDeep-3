import { useEffect, useState } from "react";
import CrisisButton from "../components/CrisisButton";
import PsychDeepLoader from "../components/PsychDeepLoader";
import { api, SafetyPlanOut } from "../api";

interface Resource {
  name: string;
  description: string;
  contact: string;
  scope?: "nacional" | "local" | string;
  region?: string;
}

interface ResourcesResponse {
  resources: Resource[];
  local_region?: string | null;
}

/** Always shown, even if the resources request fails. */
const NATIONAL_FALLBACK: Resource[] = [
  { name: "Línea 024", description: "Atención a la conducta suicida (24h, España)", contact: "024", scope: "nacional" },
  { name: "112", description: "Emergencias", contact: "112", scope: "nacional" },
];

const FIELDS: { key: keyof SafetyPlanOut; label: string; placeholder: string }[] = [
  { key: "warning_signs", label: "Señales de alerta", placeholder: "Pensamientos, sensaciones o situaciones que indican que algo empieza a ir mal" },
  { key: "coping_strategies", label: "Estrategias de afrontamiento", placeholder: "Cosas que puedo hacer yo solo/a: la Ola, respiración, salir a caminar..." },
  { key: "social_supports", label: "Apoyos sociales", placeholder: "Personas con las que puedo hablar" },
  { key: "professional_contacts", label: "Contactos profesionales", placeholder: "Mi terapeuta, mi centro de referencia..." },
  { key: "safe_environment", label: "Hacer mi entorno más seguro", placeholder: "Qué puedo retirar o alejar de mi alcance" },
  { key: "reasons_to_live", label: "Razones para vivir", placeholder: "Lo que más me importa" },
];

function ResourceList({ items }: { items: Resource[] }) {
  return (
    <ul>
      {items.map((r) => (
        <li key={r.name}>
          <strong>{r.name}</strong>: {r.description} —{" "}
          {/^https?:\/\//.test(r.contact) ? (
            <a href={r.contact} target="_blank" rel="noreferrer">
              {r.contact}
            </a>
          ) : (
            <a href={`tel:${r.contact}`}>{r.contact}</a>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function SafetyPlanPage() {
  const [plan, setPlan] = useState<SafetyPlanOut | null>(null);
  const [resources, setResources] = useState<ResourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .get<SafetyPlanOut>("/api/v1/safety-plan")
      .then(setPlan)
      .catch(() => setLoadError("No se pudo cargar tu plan. Los recursos de ayuda de abajo siguen disponibles."))
      .finally(() => setLoading(false));
    api
      .get<ResourcesResponse>("/api/v1/safety-plan/resources")
      .then(setResources)
      .catch(() => setResources(null));
  }, []);

  async function save() {
    if (!plan) return;
    setSaving(true);
    setSaved(false);
    setSaveError(null);
    try {
      const { id, updated_at, ...payload } = plan;
      const updated = await api.put<SafetyPlanOut>("/api/v1/safety-plan", payload);
      setPlan(updated);
      setSaved(true);
    } catch {
      setSaveError("No se pudo guardar el plan. Tus cambios siguen en pantalla; inténtalo de nuevo.");
    } finally {
      setSaving(false);
    }
  }

  const all = resources?.resources ?? [];
  const national = all.filter((r) => r.scope !== "local");
  const local = all.filter((r) => r.scope === "local");
  const localRegion = resources?.local_region ?? local[0]?.region ?? null;

  return (
    <div className="page">
      <h1>Mi plan de seguridad</h1>
      <CrisisButton />

      {loading && <PsychDeepLoader size="sm" label="Cargando tu plan…" />}
      {loadError && (
        <p className="error" role="alert">
          {loadError}
        </p>
      )}

      {plan && (
        <section className="card">
          {FIELDS.map((f) => (
            <label key={f.key}>
              {f.label}
              <textarea
                rows={2}
                value={(plan[f.key] as string) || ""}
                placeholder={f.placeholder}
                onChange={(e) => setPlan({ ...plan, [f.key]: e.target.value })}
              />
            </label>
          ))}
          <button onClick={save} disabled={saving}>
            {saving ? "Guardando..." : "Guardar plan"}
          </button>
          {saved && <p className="info" role="status">Guardado.</p>}
          {saveError && (
            <p className="error" role="alert">
              {saveError}
            </p>
          )}
        </section>
      )}

      <section className="card" aria-labelledby="resources-national">
        <h2 id="resources-national">Ayuda inmediata (España, siempre disponible)</h2>
        <ResourceList items={national.length ? national : NATIONAL_FALLBACK} />
        {local.length > 0 && (
          <>
            <h3>Recursos locales{localRegion ? ` · ${localRegion}` : ""}</h3>
            <p className="meta">Recursos configurados para esta zona. Si vives en otro lugar, pregunta a tu profesional por los de tu zona.</p>
            <ResourceList items={local} />
          </>
        )}
      </section>
    </div>
  );
}
