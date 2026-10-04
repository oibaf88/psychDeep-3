import type { LongitudinalStateOut } from "../api";
import { readProfessionalChange } from "../pages/professionalChange";

/** Personal-baseline change for a clinician. This is not the risk/alert card. */
export default function LongitudinalChangePanel({
  longitudinal,
}: {
  longitudinal?: LongitudinalStateOut | null;
}) {
  const reading = readProfessionalChange(longitudinal);
  return (
    <section className="card change-panel" aria-labelledby="baseline-change-heading">
      <h2 id="baseline-change-heading">Cambio respecto a su línea de base</h2>
      <p className="subtitle">{reading.intro}</p>
      <div className="trends-baseline" aria-label="Estado de la referencia personal">
        <p className="trends-baseline__title">Referencia personal</p>
        <p className="trends-baseline__value">{reading.baselineLabel}</p>
        <span className="meta">
          {reading.stabilityLabel} · {reading.coverageLabel}
        </span>
      </div>
      {reading.rows.length === 0 ? (
        <p>
          Todavía no hay una comparación calculada. Faltan datos para contrastar este periodo con su
          referencia personal. Esa falta no se interpreta como cero ni como ausencia de riesgo.
        </p>
      ) : (
        <ul className="change-list">
          {reading.rows.map((row) => (
            <li key={row.feature}>
              <strong>{row.label}</strong>
              <span className="change-band">{row.bandLabel}</span>
              <span className="meta">{row.changeLabel}</span>
              {row.missingNote && <span className="meta">{row.missingNote}</span>}
            </li>
          ))}
        </ul>
      )}
      {reading.missingSentence && <p>{reading.missingSentence}</p>}
      <p className="chart-reading-note">{reading.limit}</p>
    </section>
  );
}
