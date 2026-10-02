import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatDay, PatientTimelineOut } from "../api";

type TimelinePoint = PatientTimelineOut["points"][number];
type ChartMargin = { top: number; right: number; bottom: number; left: number };

const SERIES = [
  { dataKey: "mood", name: "Ánimo", yAxisId: "left", stroke: "#7ea8f7", strokeWidth: 2.5 },
  { dataKey: "craving", name: "Craving", yAxisId: "left", stroke: "#df9a73", strokeWidth: 2.5 },
  { dataKey: "self_efficacy", name: "Autoeficacia", yAxisId: "left", stroke: "#76cdbd", strokeWidth: 2.5 },
  { dataKey: "sleep_hours", name: "Sueño (h)", yAxisId: "sleep", stroke: "#e9c982", strokeWidth: 2 },
] as const;

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

export default function PatientTimelineChart({
  points,
  height,
  margin,
  primaryDotRadius,
  sleepTicksWithUnit = false,
  ariaLabel,
}: {
  points: TimelinePoint[];
  height: number;
  margin: ChartMargin;
  primaryDotRadius: number;
  sleepTicksWithUnit?: boolean;
  ariaLabel: string;
}) {
  return (
    <div className="chart-shell" aria-label={ariaLabel} role="region">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={points} margin={margin}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={formatDay} minTickGap={24} />
          <YAxis yAxisId="left" domain={[0, 10]} tick={{ fontSize: 11 }} />
          <YAxis
            yAxisId="sleep"
            orientation="right"
            domain={[0, 24]}
            tick={{ fontSize: 11 }}
            tickFormatter={sleepTicksWithUnit ? (value: number) => value + " h" : undefined}
          />
          <Tooltip labelFormatter={formatDay} />
          <Legend />
          {SERIES.map((series) => (
            <Line
              key={series.dataKey}
              yAxisId={series.yAxisId}
              type="monotone"
              dataKey={series.dataKey}
              name={series.name}
              stroke={series.stroke}
              strokeWidth={series.strokeWidth}
              connectNulls={false}
              dot={{ r: series.dataKey === "sleep_hours" ? 2 : primaryDotRadius }}
              {...(series.dataKey === "sleep_hours" ? { strokeDasharray: "5 3" } : {})}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
