/**
 * One reading of "change versus the personal baseline" for every screen.
 *
 * Hoy, Tendencias, the professional dossier and the roster all render THIS
 * reading, built from the same `longitudinal` payload (`GET /api/v1/state` or
 * the professional summary/dossier). Before, each screen derived its own
 * labels from different fields (baseline row vs change rows), so one page
 * could say "Sirve como referencia" above "no hay datos para comparar".
 *
 * Rules kept here:
 * - every "available" status shows the values behind it (recent mean,
 *   reference mean, difference, direction, counts, dates);
 * - missing data is named with its reason and is never a zero, never
 *   "normal", never "sin riesgo";
 * - this is a change reading, never a RiskAssessment / alert level.
 */
import type {
  ComparisonSummaryOut,
  FeatureDisplayOut,
  LongitudinalChangeOut,
  LongitudinalStateOut,
  PendingFeatureOut,
} from "../api";

export type Audience = "patient" | "professional";
export type ComparisonStatus = ComparisonSummaryOut["status"];

export const FEATURE_ORDER = ["mood", "craving", "sleep_hours", "self_efficacy"] as const;
const COMPARED_FEATURES: readonly string[] = FEATURE_ORDER;
const CALCULATED_BANDS = ["stable", "transition", "unstable"];
const MIN_REFERENCE_N = 5;

const LABELS: Record<string, string> = {
  mood: "Ánimo",
  craving: "Craving (deseo de consumo)",
  sleep_hours: "Sueño",
  self_efficacy: "Autoeficacia (confianza)",
  structural_composite: "Conjunto de registros",
};

const BAND_LABELS: Record<Audience, Record<string, string>> = {
  patient: {
    stable: "Cerca de lo habitual en ti",
    transition: "Algo distinto de lo habitual en ti",
    unstable: "Bastante distinto de lo habitual en ti",
  },
  professional: {
    stable: "Cerca de su referencia personal",
    transition: "Algo distinto de su referencia personal",
    unstable: "Bastante distinto de su referencia personal",
  },
};

/** Neutral description of the direction, in the feature's own terms. */
const DIRECTION_WORDS: Record<string, { higher: string; lower: string }> = {
  mood: { higher: "ánimo más alto", lower: "ánimo más bajo" },
  craving: { higher: "más deseo de consumo", lower: "menos deseo de consumo" },
  sleep_hours: { higher: "más horas de sueño", lower: "menos horas de sueño" },
  self_efficacy: { higher: "más confianza para manejar el día", lower: "menos confianza para manejar el día" },
};

export const CHANGE_IS_NOT_RISK = "La ausencia de una señal de cambio no demuestra ausencia de riesgo.";

export function featureLabel(feature: string): string {
  return LABELS[feature] ?? feature.replace(/_/g, " ");
}

export function bandLabel(band: string, audience: Audience): string {
  return BAND_LABELS[audience][band] ?? "Sin comparación calculada";
}

export function isCalculated(signal: LongitudinalChangeOut): boolean {
  return CALCULATED_BANDS.includes(signal.band) && typeof signal.change === "number" && Number.isFinite(signal.change);
}

const NUMBER = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1, minimumFractionDigits: 0 });
const SIGNED = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1, minimumFractionDigits: 1, signDisplay: "exceptZero" });

export function formatNumber(value: number | null | undefined): string | null {
  return typeof value === "number" && Number.isFinite(value) ? NUMBER.format(value) : null;
}

function formatSigned(value: number | null | undefined): string | null {
  return typeof value === "number" && Number.isFinite(value) ? SIGNED.format(value) : null;
}

function withUnit(value: string, unit?: string | null): string {
  return unit === "h" ? `${value} h` : `${value}/10`;
}

function unitWord(unit?: string | null): string {
  return unit === "h" ? "h" : "puntos";
}

export function formatDate(value?: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" });
}

function windowText(window?: { start?: string | null; end?: string | null } | null): string | null {
  const start = formatDate(window?.start);
  const end = formatDate(window?.end);
  if (start && end) return `${start} – ${end}`;
  return end ?? start;
}

function joinSpanish(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0;
}

/** Same rules as the backend summary, for payloads that predate it. */
export function deriveSummary(state: LongitudinalStateOut | null | undefined): ComparisonSummaryOut {
  if (state?.summary) return state.summary;
  const rows = (state?.changes ?? []).filter((row) => COMPARED_FEATURES.includes(row.feature));
  const calculated = rows.filter(isCalculated).map((row) => row.feature);
  const pending: PendingFeatureOut[] = rows
    .filter((row) => !isCalculated(row))
    .map((row) => {
      const baselineN = count(row.uncertainty?.baseline_n);
      const recentN = count(row.uncertainty?.recent_n);
      const shortRef = baselineN < MIN_REFERENCE_N;
      const noRecent = recentN === 0;
      return {
        feature: row.feature,
        reason: shortRef && noRecent ? "both" : shortRef ? "reference" : "recent",
        baseline_n: baselineN,
        recent_n: recentN,
        minimum_reference_n: MIN_REFERENCE_N,
      };
    });
  const hasCanonicalBaseline =
    !!state?.baseline?.baseline && (state.baseline.baseline.algorithm_version ?? "canonical-").startsWith("canonical-");
  let status: ComparisonStatus;
  if (!hasCanonicalBaseline || rows.length === 0) status = "not_computed";
  else if (calculated.length && !pending.length) status = "calculated";
  else if (calculated.length) status = "partial";
  else if (pending.every((item) => item.reason === "recent")) status = "no_recent_data";
  else status = "insufficient_reference";
  const ends = rows.map((row) => row.window?.end).filter((v): v is string => !!v).sort();
  const starts = rows.map((row) => row.window?.start).filter((v): v is string => !!v).sort();
  return {
    status,
    calculated_features: calculated,
    pending_features: pending,
    computed_at: ends[ends.length - 1] ?? null,
    recent_window: { start: starts[0] ?? null, end: ends[ends.length - 1] ?? null },
    reference_window: state?.baseline?.baseline?.window ?? undefined,
    algorithm_version: state?.baseline?.baseline?.algorithm_version ?? null,
    is_stale: false,
    minimum_reference_n: MIN_REFERENCE_N,
  };
}

export interface ComparisonRow {
  feature: string;
  label: string;
  calculated: boolean;
  bandLabel: string;
  /** "3,5/10 de media en el periodo reciente frente a 6,4/10 en tu referencia". */
  valueLine: string | null;
  /** "Más deseo de consumo que lo habitual (+4,1 puntos)". */
  directionLine: string | null;
  countsLine: string | null;
  /** Professional only: signed z on the declared scale. */
  zLine: string | null;
  missingLine: string | null;
  traceLine: string | null;
  contradictionLine: string | null;
  recentValue: number | null;
  referenceValue: number | null;
  difference: number | null;
  direction: FeatureDisplayOut["direction"];
  unit: string | null;
  zText: string | null;
  recentN: number;
  referenceN: number;
}

export interface ComparisonReading {
  status: ComparisonStatus;
  statusLabel: string;
  headline: string;
  explanation: string;
  facts: { label: string; value: string }[];
  rows: ComparisonRow[];
  pendingNotice: string | null;
  staleNotice: string | null;
  windowsLine: string | null;
  versionLine: string | null;
  limit: string;
}

const STATUS_LABELS: Record<ComparisonStatus, string> = {
  calculated: "Comparación calculada",
  partial: "Comparación parcial",
  no_recent_data: "Faltan registros recientes",
  insufficient_reference: "Referencia aún insuficiente",
  not_computed: "Comparación sin calcular",
};

function you(audience: Audience, patient: string, professional: string): string {
  return audience === "patient" ? patient : professional;
}

function pendingText(item: PendingFeatureOut, audience: Audience): string {
  const label = featureLabel(item.feature);
  const min = item.minimum_reference_n ?? MIN_REFERENCE_N;
  if (item.reason === "recent") {
    return `${label}: no hay registros en los últimos 7 días (la referencia tiene ${item.baseline_n}).`;
  }
  const ref = `${you(audience, "tu referencia", "su referencia")} tiene ${item.baseline_n} de los ${min} registros mínimos`;
  return item.reason === "both"
    ? `${label}: ${ref} y no hay registros recientes.`
    : `${label}: ${ref} (${item.recent_n} registros recientes).`;
}

function rowFor(signal: LongitudinalChangeOut, pending: PendingFeatureOut | undefined, audience: Audience): ComparisonRow {
  const calculated = isCalculated(signal);
  const display = signal.evidence?.display ?? null;
  const unit = display?.unit ?? (signal.feature === "sleep_hours" ? "h" : "0-10");
  const recent = formatNumber(display?.recent_value);
  const reference = formatNumber(display?.reference_value);
  const recentN = count(signal.evidence?.recent?.n ?? signal.uncertainty?.recent_n);
  const referenceN = count(signal.evidence?.reference?.n ?? signal.uncertainty?.baseline_n);

  let valueLine: string | null = null;
  if (recent && reference) {
    valueLine = `${withUnit(recent, unit)} de media en el periodo reciente frente a ${withUnit(reference, unit)} en ${you(audience, "tu", "su")} referencia.`;
  } else if (recent) {
    valueLine = `${withUnit(recent, unit)} de media en el periodo reciente; sin referencia suficiente para comparar.`;
  }

  let directionLine: string | null = null;
  const words = DIRECTION_WORDS[signal.feature];
  if (calculated && display?.direction && words) {
    const diff = formatSigned(display.difference);
    const diffText = diff ? ` (${diff} ${unitWord(unit)})` : "";
    directionLine =
      display.direction === "similar"
        ? `Parecido a lo habitual${diffText}.`
        : `${words[display.direction].charAt(0).toUpperCase()}${words[display.direction].slice(1)} que lo habitual${diffText}.`;
  }

  const countsLine = calculated
    ? `${recentN} registro${recentN === 1 ? "" : "s"} reciente${recentN === 1 ? "" : "s"} · ${referenceN} en la referencia${recentN > 0 && recentN < 3 ? " · pocos registros recientes: lectura poco firme" : ""}`
    : null;

  let zLine: string | null = null;
  if (audience === "professional" && calculated && typeof display?.z === "number") {
    zLine = `z = ${formatSigned(display.z)} en la escala declarada (positivo = media reciente más alta). No es un nivel de alerta.`;
  }

  let traceLine: string | null = null;
  if (audience === "professional" && signal.evidence) {
    const reproduced = signal.evidence.reproduced_from_rows;
    const rep = reproduced === true ? "reproducible desde las filas citadas" : reproduced === false ? "NO coincide con las filas citadas: revisar" : "sin comprobación de reproducibilidad";
    traceLine = `${signal.algorithm_version ?? "versión desconocida"} · ${rep}`;
  }

  return {
    feature: signal.feature,
    label: featureLabel(signal.feature),
    calculated,
    bandLabel: calculated ? bandLabel(signal.band, audience) : "Sin comparación calculada",
    valueLine,
    directionLine,
    countsLine,
    zLine,
    missingLine: calculated ? null : pending ? pendingText(pending, audience) : "Sin comparación calculada. No se interpreta como cero.",
    traceLine,
    contradictionLine:
      Array.isArray(signal.contradictions) && signal.contradictions.length > 0
        ? "Hay contexto contradictorio registrado. La señal se conserva y no se convierte en un nivel de alerta."
        : null,
    recentValue: display?.recent_value ?? null,
    referenceValue: display?.reference_value ?? null,
    difference: display?.difference ?? null,
    direction: display?.direction ?? null,
    unit,
    zText: calculated && typeof display?.z === "number" ? formatSigned(display.z) : null,
    recentN,
    referenceN,
  };
}

/** The reading every screen renders. */
export function readComparison(
  state: LongitudinalStateOut | null | undefined,
  audience: Audience,
): ComparisonReading {
  const summary = deriveSummary(state);
  const changes = state?.changes ?? [];
  const pendingByFeature = new Map(summary.pending_features.map((item) => [item.feature, item]));
  const rows = FEATURE_ORDER.map((feature) => changes.find((row) => row.feature === feature))
    .filter((row): row is LongitudinalChangeOut => !!row)
    .map((row) => rowFor(row, pendingByFeature.get(row.feature), audience));
  const composite = changes.find((row) => row.feature === "structural_composite");
  const compared = summary.calculated_features.length;
  const total = COMPARED_FEATURES.length;
  const min = summary.minimum_reference_n ?? MIN_REFERENCE_N;

  let headline: string;
  let explanation: string;
  switch (summary.status) {
    case "calculated":
      headline = composite && isCalculated(composite) ? bandLabel(composite.band, audience) : `Comparación en las ${total} áreas`;
      explanation = you(
        audience,
        "Tus registros de los últimos 7 días comparados con tu referencia personal (las 3 semanas anteriores). Abajo tienes los valores de cada área.",
        "Registros de los últimos 7 días frente a su referencia personal (las 3 semanas anteriores, sin incluir esos 7 días).",
      );
      break;
    case "partial":
      headline = `Comparación en ${compared} de ${total} áreas`;
      explanation = "Las áreas sin comparación se explican abajo con el motivo. Su ausencia no significa que estén bien.";
      break;
    case "no_recent_data":
      headline = you(audience, "Tu referencia está lista, pero faltan registros recientes", "Referencia lista, sin registros recientes");
      explanation = you(
        audience,
        "No hay check-ins en los últimos 7 días, así que no se puede saber si algo ha cambiado. Un check-in hoy actualiza la comparación.",
        "No hay check-ins en los últimos 7 días: el cambio es desconocido, no nulo.",
      );
      break;
    case "insufficient_reference":
      headline = you(audience, "Aún no hay registros suficientes para tu referencia personal", "Referencia personal aún insuficiente");
      explanation = `Hacen falta al menos ${min} registros por área entre hace 8 y 28 días para construir la referencia. Mientras tanto no se calcula ningún cambio, y eso no significa que todo vaya bien.`;
      break;
    default:
      headline = you(audience, "Todavía no se ha calculado tu comparación", "Comparación aún no calculada");
      explanation = you(
        audience,
        "La comparación con lo habitual en ti se calcula al guardar un check-in. Cuando registres el próximo, aparecerá aquí con sus valores.",
        "No hay una referencia calculada con el método actual. Se calculará con el próximo check-in del paciente.",
      );
  }

  const computed = formatDate(summary.computed_at);
  const facts = [
    { label: "Estado", value: STATUS_LABELS[summary.status] },
    { label: "Áreas comparadas", value: `${compared} de ${total}` },
    { label: "Calculada", value: computed ? `${computed}${summary.is_stale ? " (desactualizada)" : ""}` : "Aún no" },
  ];

  const pending = summary.pending_features;
  const pendingNotice =
    summary.status === "partial" && pending.length
      ? `Falta la comparación en ${joinSpanish(pending.map((item) => featureLabel(item.feature)))}. Esa falta no se guarda como cero ni indica ausencia de riesgo.`
      : null;

  const staleNotice = summary.is_stale
    ? you(
        audience,
        `Esta comparación es del ${computed}. Desde entonces no hay check-ins, así que puede no describir cómo estás ahora.`,
        `Comparación calculada el ${computed}, sin check-ins posteriores: puede no describir el estado actual.`,
      )
    : null;

  const recentWin = windowText(summary.recent_window);
  const refWin = windowText(summary.reference_window);
  const windowsLine =
    recentWin || refWin
      ? `Periodo reciente: ${recentWin ?? "no disponible"} · Referencia: ${refWin ?? "no disponible"}${
          ["canonical-structural-v2", "canonical-structural-v3"].includes(summary.algorithm_version ?? "") ? " (la referencia no incluye el periodo reciente)" : ""
        }`
      : null;

  return {
    status: summary.status,
    statusLabel: STATUS_LABELS[summary.status],
    headline,
    explanation,
    facts,
    rows,
    pendingNotice,
    staleNotice,
    windowsLine,
    versionLine: audience === "professional" && summary.algorithm_version ? `Algoritmo: ${summary.algorithm_version}` : null,
    limit: CHANGE_IS_NOT_RISK,
  };
}

/** Roster / copilot one-liners, from the same reading. */
export function rosterHeadline(state: LongitudinalStateOut | null | undefined): string {
  if (!state) return "Sin lectura longitudinal";
  return readComparison(state, "professional").headline;
}

export function rosterDetail(state: LongitudinalStateOut | null | undefined): string {
  if (!state) return "Esta fila no incluye la trayectoria canónica.";
  const reading = readComparison(state, "professional");
  const areas = reading.facts[1].value;
  const when = reading.facts[2].value;
  return `${areas} áreas · ${when} · no es una alerta`;
}
