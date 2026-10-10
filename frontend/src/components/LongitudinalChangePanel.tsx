import type { LongitudinalStateOut } from "../api";
import { readComparison } from "../pages/longitudinalModel";
import ComparisonDetails, { ComparisonFacts } from "./ComparisonDetails";

/** Personal-baseline change for a clinician. This is not the risk/alert card. */
export default function LongitudinalChangePanel({
  longitudinal,
}: {
  longitudinal?: LongitudinalStateOut | null;
}) {
  const reading = readComparison(longitudinal, "professional");
  return (
    <section className="card change-panel" aria-labelledby="baseline-change-heading">
      <h2 id="baseline-change-heading">Cambio respecto a su línea de base</h2>
      <p className="subtitle">
        Comparación con su referencia personal (pipeline canónico). Es independiente del nivel de alerta y del motor
        de riesgo, que usa su propia ventana (ver «Score estructural, explicado»).
      </p>
      <p className="trends-baseline__value">{reading.headline}</p>
      <p>{reading.explanation}</p>
      <ComparisonFacts reading={reading} />
      <ComparisonDetails reading={reading} audience="professional" />
    </section>
  );
}
