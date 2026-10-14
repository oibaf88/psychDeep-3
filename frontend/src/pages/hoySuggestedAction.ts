/**
 * Hoy's default suggested action from the canonical ChangeSignal comparison
 * (ComparisonReading) plus an optional acute override from the in-progress form.
 *
 * ChangeSignal ≠ RiskAssessment: this never reads alert levels.
 * No new clinical thresholds — only existing bands/directions and the same
 * form cut-offs already used on Hoy (craving ≥ 7, self_efficacy ≤ 3).
 *
 * Each action carries a stable actionId so accept / postpone / usefulness
 * feedback can be recorded on InterventionEvent without inventing clinical meaning.
 */
import type { CheckInIn } from "../api";
import type { ComparisonReading } from "./longitudinalModel";

export type HoyActionId =
  | "hoy.suggest.regular_wave"
  | "hoy.suggest.trends_explain"
  | "hoy.suggest.register_observe";

export type HoyActionDriver =
  | "acute_craving"
  | "acute_self_efficacy"
  | "longitudinal_adverse"
  | "calculated_explain"
  | "insufficient_observe";

export type SuggestedAction = {
  actionId: HoyActionId;
  driver: HoyActionDriver;
  title: string;
  body: string;
  button: string;
  route: string;
};

const ADVERSE_BANDS = new Set(["transition", "unstable"]);

function rowShowsAdverseForRegular(row: ComparisonReading["rows"][number]): boolean {
  if (!row.calculated) return false;
  const band = row.band ?? "";
  const adverseBand = ADVERSE_BANDS.has(band);

  if (row.feature === "craving") {
    if (row.direction === "higher") return true;
    if (
      adverseBand &&
      typeof row.recentValue === "number" &&
      typeof row.referenceValue === "number" &&
      row.recentValue > row.referenceValue
    ) {
      return true;
    }
    return false;
  }

  if (row.feature === "mood" || row.feature === "self_efficacy") {
    return row.direction === "lower" && adverseBand;
  }

  return false;
}

/** True when a calculated feature row shows adverse change suitable for Regular. */
export function readingShowsAdverseForRegular(reading: ComparisonReading | null | undefined): boolean {
  if (!reading) return false;
  return reading.rows.some(rowShowsAdverseForRegular);
}

/**
 * Primary driver = longitudinal reading. Secondary acute override = form moved
 * away from defaults (craving ≥ 7 or self_efficacy ≤ 3). At form defaults,
 * longitudinal wins.
 */
export function suggestedActionFromReading(
  reading: ComparisonReading | null | undefined,
  form: Pick<CheckInIn, "craving" | "self_efficacy">,
): SuggestedAction {
  if (form.craving >= 7) {
    return {
      actionId: "hoy.suggest.regular_wave",
      driver: "acute_craving",
      title: "Regular una ola",
      body: "Tienes una urgencia alta en este momento. Puedes probar la práctica de la ola sin necesidad de resolver nada más ahora.",
      button: "Ir a Regular",
      route: "/wave",
    };
  }

  if (form.self_efficacy <= 3) {
    return {
      actionId: "hoy.suggest.regular_wave",
      driver: "acute_self_efficacy",
      title: "Bajar el ritmo",
      body: "Cuando la confianza está baja, una práctica breve puede ayudarte a recuperar espacio antes de decidir el siguiente paso.",
      button: "Ir a Regular",
      route: "/wave",
    };
  }

  if (readingShowsAdverseForRegular(reading)) {
    return {
      actionId: "hoy.suggest.regular_wave",
      driver: "longitudinal_adverse",
      title: "Regular una ola",
      body: "Tu comparación reciente muestra un cambio respecto a lo habitual en ti. Puedes probar la práctica de la ola como un siguiente paso breve, sin necesidad de resolver nada más ahora.",
      button: "Ir a Regular",
      route: "/wave",
    };
  }

  if (reading && (reading.status === "calculated" || reading.status === "partial")) {
    return {
      actionId: "hoy.suggest.trends_explain",
      driver: "calculated_explain",
      title: "Mirar la explicación del cambio",
      body: "Hay una comparación con tu referencia. En Tendencias puedes ver qué se está moviendo y con qué valores, sin interpretarlo como un nivel de alerta.",
      button: "Ver Tendencias",
      route: "/trends",
    };
  }

  return {
    actionId: "hoy.suggest.register_observe",
    driver: "insufficient_observe",
    title: "Registrar y observar",
    body: "Aún no hay una comparación suficiente con tu referencia. Puedes registrar y observar tu trayectoria en Tendencias. Eso no significa que todo vaya bien ni que no haya riesgo.",
    button: "Ver Tendencias",
    route: "/trends",
  };
}
