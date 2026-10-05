import { PatientTimelineOut } from "../api";

type TimelinePoint = PatientTimelineOut["points"][number];

export function PatientTrendSummary({
  point,
  moodLabel,
  cravingLabel,
  ariaLabel,
}: {
  point: TimelinePoint | null;
  moodLabel: string;
  cravingLabel: string;
  ariaLabel?: string;
}) {
  return (
    <div className="trend-summary" aria-label={ariaLabel}>
      <div className="trend-summary__item">
        <span className="trend-summary__label">{moodLabel}</span>
        <span className="trend-summary__value">{point?.mood ?? "—"}/10</span>
      </div>
      <div className="trend-summary__item">
        <span className="trend-summary__label">{cravingLabel}</span>
        <span className="trend-summary__value">{point?.craving ?? "—"}/10</span>
      </div>
      <div className="trend-summary__item">
        <span className="trend-summary__label">Sueño</span>
        <span className="trend-summary__value">
          {point?.sleep_hours == null ? "—" : point.sleep_hours + " h"}
        </span>
      </div>
    </div>
  );
}
