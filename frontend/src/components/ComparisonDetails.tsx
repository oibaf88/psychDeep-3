import type { ComparisonReading } from "../pages/longitudinalModel";
import { formatNumber } from "../pages/longitudinalModel";

function value(v: number | null, unit: string | null): string {
  const text = formatNumber(v);
  if (text == null) return "—";
  return unit === "h" ? `${text} h` : text;
}

const DIRECTION_SHORT: Record<string, string> = { higher: "Más alto", lower: "Más bajo", similar: "Parecido" };

/** Facts row shared by Hoy, Tendencias and the professional panel. */
export function ComparisonFacts({ reading, className = "trend-summary" }: { reading: ComparisonReading; className?: string }) {
  return (
    <dl className={className} aria-label="Estado de la comparación con la referencia personal">
      {reading.facts.map((fact) => (
        <div className="trend-summary__item" key={fact.label}>
          <dt className="trend-summary__label">{fact.label}</dt>
          <dd className="trend-summary__value">{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Per-area comparison with the values behind every status. */
export default function ComparisonDetails({
  reading,
  audience,
}: {
  reading: ComparisonReading;
  audience: "patient" | "professional";
}) {
  return (
    <div className="comparison-details" data-status={reading.status}>
      {reading.staleNotice && (
        <p className="hoy-missing" role="note">
          {reading.staleNotice}
        </p>
      )}
      {audience === "professional" && reading.rows.length > 0 ? (
        <div className="table-wrap">
          <table className="table explain-table">
            <caption className="meta" style={{ textAlign: "left" }}>
              Medias en la escala declarada (el craving no se invierte aquí). Diferencia = reciente − referencia. z
              positivo = media reciente más alta. Nada de esta tabla es un nivel de alerta.
            </caption>
            <thead>
              <tr>
                <th scope="col">Área</th>
                <th scope="col">Referencia</th>
                <th scope="col">Últimos 7 días</th>
                <th scope="col">Diferencia</th>
                <th scope="col">Dirección</th>
                <th scope="col">z</th>
                <th scope="col">Registros (rec. / ref.)</th>
                <th scope="col">Lectura</th>
              </tr>
            </thead>
            <tbody>
              {reading.rows.map((row) => (
                <tr key={row.feature}>
                  <th scope="row">
                    {row.label}
                    {row.traceLine && <div className="meta">{row.traceLine}</div>}
                  </th>
                  <td>{value(row.referenceValue, row.unit)}</td>
                  <td>{value(row.recentValue, row.unit)}</td>
                  <td>{row.calculated ? `${(row.difference ?? 0) > 0 ? "+" : ""}${value(row.difference, row.unit)}` : "—"}</td>
                  <td>{row.calculated && row.direction ? DIRECTION_SHORT[row.direction] : "—"}</td>
                  <td>{row.zText ?? "—"}</td>
                  <td>
                    {row.recentN} / {row.referenceN}
                    {row.calculated && row.recentN > 0 && row.recentN < 3 && <div className="meta">pocos registros recientes</div>}
                  </td>
                  <td>
                    <span className="change-band">{row.bandLabel}</span>
                    {row.missingLine && <div className="meta">{row.missingLine}</div>}
                    {row.contradictionLine && <div className="meta">{row.contradictionLine}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        reading.rows.length > 0 && (
          <ul className="longitudinal-change__list">
            {reading.rows.map((row) => (
              <li className="longitudinal-change__item" key={row.feature}>
                <h3>{row.label}</h3>
                <p className="longitudinal-change__band">{row.bandLabel}</p>
                {row.directionLine && <p>{row.directionLine}</p>}
                {row.valueLine && <p>{row.valueLine}</p>}
                {row.countsLine && <p className="meta">{row.countsLine}</p>}
                {row.missingLine && <p className="meta">{row.missingLine}</p>}
                {row.contradictionLine && <p className="meta">{row.contradictionLine}</p>}
              </li>
            ))}
          </ul>
        )
      )}
      {reading.pendingNotice && <p>{reading.pendingNotice}</p>}
      {reading.windowsLine && <p className="meta">{reading.windowsLine}</p>}
      {reading.versionLine && <p className="meta">{reading.versionLine}</p>}
      <p className="chart-reading-note">{reading.limit}</p>
    </div>
  );
}
