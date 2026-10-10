/**
 * Charts for the professional panel.
 *
 * Every chart here answers one clinical question and carries its own
 * caption saying how to read it. That caption is not decoration: the
 * previous panel showed a bare `structural_score` number that readers
 * consistently interpreted as "risk", when it actually measures similarity
 * to the patient's own baseline.
 */
import { ReactNode } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  CheckInPoint,
  LevelPoint,
  LinguisticPoint,
  MetricEvent,
  PsychosocialPoint,
  StructuralPoint,
  formatDay,
} from "../api";

/* Series colours, re-stepped for the dark card surface and validated
 * rather than chosen by eye.
 *
 * The previous steps were validated against a WHITE card. The surface is
 * now #1a2332, so they were re-stepped and re-run — a dark palette is
 * selected for its surface, never an automatic flip of the light one.
 *
 * The four categorical slots below are assigned in fixed order and shared
 * by both groups that ever appear together in one chart (the four check-in
 * variables, and the four Agent 2 signals); the groups never co-occur, so
 * one theme serves both. Against #1a2332, on the adjacent pairlist that
 * line charts are read on:
 *
 *   #3987e5 #d95926 #199e70 #c98500
 *   worst adjacent CVD ΔE 8.4 (protan) · normal-vision 19.8 · all >= 3:1
 *
 * Four is the ceiling here, not a preference: past three slots no hue set
 * clears all-pairs CVD inside the dark lightness band, so a fifth series
 * must fold to "Other" or be faceted rather than take a generated hue.
 *
 * `level` and `score` are STATUS colours (critical / good) and stay the
 * stylesheet's semantic red and green, kept apart from the categorical
 * slots so a status tone never impersonates a series.
 */
const COLORS = {
  level: "#e36a6a",
  score: "#55bd91",
  mood: "#3987e5",
  craving: "#d95926",
  sleep: "#199e70",
  efficacy: "#c98500",
  rumination: "#3987e5",
  valence: "#d95926",
  urgency: "#199e70",
  ambivalence: "#c98500",
  psychosocial: "#c98500",
  neutral: "#9aa8bc",
};
const STRUCTURAL_STABLE_MIN = 1 / (1 + 1.2);
const STRUCTURAL_TRANSITION_MIN = 1 / (1 + 1.95);

export function ChartCard({
  title,
  question,
  howToRead,
  empty,
  children,
  footer,
}: {
  title: string;
  question: string;
  howToRead: string;
  empty?: boolean;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className="chart-card">
      <header className="chart-card-head">
        <h3>{title}</h3>
        <p className="chart-question">{question}</p>
      </header>
      {empty ? (
        <p className="chart-empty">Todavía no hay datos suficientes para dibujar esta gráfica.</p>
      ) : (
        <div className="chart-body">{children}</div>
      )}
      <p className="chart-legend-note">
        <strong>Cómo se lee:</strong> {howToRead}
      </p>
      {footer}
    </section>
  );
}

/** Alert level over time. The single most important series for triage. */
export function LevelHistoryChart({
  daily,
  levels,
}: {
  daily: { date: string; max_level: number }[];
  levels: LevelPoint[];
}) {
  const byDate = new Map(levels.map((row) => [row.date, row]));
  const data = daily.map((row) => ({ ...row, detail: byDate.get(row.date) }));
  return (
    <ChartCard
      title="Nivel de alarma en el tiempo"
      question="¿Cuándo y con qué frecuencia ha escalado este paciente?"
      howToRead="Un punto por día con actividad, con el nivel MÁS ALTO alcanzado ese día (0–4). Las mesetas en 3–4 son lo que hay que mirar; los picos aislados suelen ser un único texto. El nivel lo decide siempre el motor determinista, nunca el modelo de lenguaje. Este gráfico es el nivel de alerta, no la señal de cambio: un día sin punto no es nivel cero ni ausencia de riesgo."
      empty={data.length === 0}
    >
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: -18 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <ReferenceArea y1={3} y2={4} fill={COLORS.level} fillOpacity={0.07} />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={formatDay} minTickGap={24} />
          <YAxis domain={[0, 4]} ticks={[0, 1, 2, 3, 4]} tick={{ fontSize: 11 }} />
          <Tooltip
            labelFormatter={formatDay}
            formatter={(value: unknown, _name, item) => {
              const detail = (item?.payload as { detail?: LevelPoint } | undefined)?.detail;
              return [`Nivel ${value}${detail?.reason ? ` — ${detail.reason}` : ""}`, "Máximo del día"];
            }}
          />
          <Area
            type="stepAfter"
            dataKey="max_level"
            name="Nivel máximo del día"
            stroke={COLORS.level}
            fill={COLORS.level}
            fillOpacity={0.18}
            strokeWidth={2}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

const UNLABELED_VERSION = "sin-version";

/** Readable name of a calculation version. Unlabeled rows are said to be unlabeled. */
export function structuralVersionLabel(version: string | null | undefined): string {
  if (!version || version === UNLABELED_VERSION) return "Sin versión registrada";
  if (version === "structural-v2") return "structural-v2 · fórmula actual";
  return `${version} · cálculo histórico`;
}

function versionKey(point: StructuralPoint): string {
  return point.calculation_version || UNLABELED_VERSION;
}

export interface VersionSegment {
  version: string;
  start: string;
  end: string;
  count: number;
}

/**
 * Consecutive runs of the same calculation version, in date order. Used to
 * draw ONE continuous series with a marker where the formula changes,
 * instead of one chart per version.
 */
export function structuralVersionSegments(points: StructuralPoint[]): VersionSegment[] {
  const segments: VersionSegment[] = [];
  for (const point of points) {
    if (typeof point.score !== "number" || !Number.isFinite(point.score)) continue;
    const version = versionKey(point);
    const last = segments[segments.length - 1];
    if (last && last.version === version) {
      last.end = point.date;
      last.count += 1;
    } else {
      segments.push({ version, start: point.date, end: point.date, count: 1 });
    }
  }
  return segments;
}

const VERSION_DOT: Record<string, string> = {
  "structural-v2": COLORS.score,
  "structural-v1": "#e5b75f",
  [UNLABELED_VERSION]: COLORS.neutral,
};

function bandsFor(version: string): { stableMin: number; transitionMin: number } | null {
  if (version === "structural-v2") return { stableMin: STRUCTURAL_STABLE_MIN, transitionMin: STRUCTURAL_TRANSITION_MIN };
  if (version === "structural-v1") return { stableMin: 0.6, transitionMin: 0.35 };
  return null;
}

/** Plain function (not a component): recharts only sees direct children. */
function versionMarkers(segments: VersionSegment[]) {
  return segments.slice(1).map((segment) => (
        <ReferenceLine
          key={`${segment.version}-${segment.start}`}
          x={segment.start}
          stroke="#c7d2e3"
          strokeDasharray="2 3"
          strokeWidth={1.5}
          ifOverflow="extendDomain"
          label={{ value: `Cambio de cálculo → ${structuralVersionLabel(segment.version).split(" · ")[0]}`, position: "insideTopRight", fontSize: 10, fill: "#c7d2e3" }}
        />
  ));
}

/**
 * Structural score as ONE continuous series across calculation versions.
 * Each point keeps its version (dot colour, tooltip, legend under the chart),
 * a vertical marker shows where the formula changed, and each segment gets
 * the band thresholds of its own version. Rows that never recorded a version
 * are shown as "Sin versión registrada", without assuming structural-v1.
 */
export function StructuralScoreChart({ points }: { points: StructuralPoint[] }) {
  const sorted = [...points].sort((a, b) => (a.at ?? a.date).localeCompare(b.at ?? b.date));
  const segments = structuralVersionSegments(sorted);
  const versions = [...new Set(segments.map((segment) => segment.version))];
  const lastDate = sorted.length ? sorted[sorted.length - 1].date : undefined;
  return (
    <ChartCard
      title="Similitud de check-ins del motor de riesgo"
      question="¿Qué similitud guardó el motor de riesgo entre los check-ins recientes y su ventana de 21 días?"
      howToRead="Esta gráfica es la similitud de check-ins que guarda el motor de riesgo, no la señal de cambio canónica ni el nivel de alerta. structural-v2 calcula 1 / (1 + media de |z|): 1 = los check-ins recientes coinciden con la ventana del motor; un valor menor es más distancia. No indica ausencia de riesgo y no rellena un hueco con cero. Bandas de esa entrada: estable ≥ 1/2,2 (≈ 0,455), transición ≥ 1/2,95 (≈ 0,339), inestable por debajo. Las reglas usan un componente de deterioro separado para que las mejoras no compensen señales adversas."
      empty={segments.length === 0}
      footer={
        versions.length > 1 || versions.some((version) => version !== "structural-v2") ? (
          <p className="chart-footnote">
            Una sola serie con todos los cálculos guardados. La línea vertical marca el cambio de fórmula: los valores a
            cada lado no son directamente comparables y cada tramo usa las bandas de su versión. Los puntos sin versión
            registrada se muestran como tales; no se les asigna una fórmula.
          </p>
        ) : undefined
      }
    >
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={sorted} margin={{ top: 16, right: 16, bottom: 4, left: -18 }}>
          <CartesianGrid strokeDasharray="3 3" />
          {segments.flatMap((segment, index) => {
            const bands = bandsFor(segment.version);
            if (!bands) return [];
            const x2 = segments[index + 1]?.start ?? lastDate ?? segment.end;
            const key = `${segment.version}-${segment.start}`;
            return [
              <ReferenceArea key={`s-${key}`} x1={segment.start} x2={x2} y1={bands.stableMin} y2={1} fill="#55bd91" fillOpacity={0.06} />,
              <ReferenceArea key={`t-${key}`} x1={segment.start} x2={x2} y1={bands.transitionMin} y2={bands.stableMin} fill="#e5b75f" fillOpacity={0.08} />,
              <ReferenceArea key={`u-${key}`} x1={segment.start} x2={x2} y1={0} y2={bands.transitionMin} fill="#e36a6a" fillOpacity={0.07} />,
              ...(segment.version === "structural-v2"
                ? [
                    <ReferenceLine key={`ls-${key}`} segment={[{ x: segment.start, y: bands.stableMin }, { x: x2, y: bands.stableMin }]} stroke="#55bd91" strokeDasharray="4 4" />,
                    <ReferenceLine key={`lt-${key}`} segment={[{ x: segment.start, y: bands.transitionMin }, { x: x2, y: bands.transitionMin }]} stroke="#e36a6a" strokeDasharray="4 4" />,
                  ]
                : []),
            ];
          })}
          {versionMarkers(segments)}
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={formatDay} minTickGap={24} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
          <Tooltip
            labelFormatter={formatDay}
            formatter={(value: unknown, _n, item) => {
              const point = item?.payload as StructuralPoint | undefined;
              return [
                `${value}${point?.band ? ` (banda del motor: ${point.band})` : ""} · ${structuralVersionLabel(point?.calculation_version)}`,
                "Similitud del motor",
              ];
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            name="Similitud del motor"
            stroke={COLORS.score}
            strokeWidth={2}
            connectNulls={false}
            dot={(props: { cx?: number; cy?: number; payload?: StructuralPoint; index?: number }) => {
              const { cx, cy, payload, index } = props;
              if (cx == null || cy == null || !payload) return <g key={`dot-${index}`} />;
              return <circle key={`dot-${index}`} cx={cx} cy={cy} r={2.5} fill={VERSION_DOT[versionKey(payload)] ?? COLORS.neutral} stroke="none" />;
            }}
          />
        </LineChart>
      </ResponsiveContainer>
      <ul className="meta chart-version-legend" aria-label="Versiones de cálculo en la serie">
        {segments.map((segment) => (
          <li key={`${segment.version}-${segment.start}`}>
            <span aria-hidden="true" style={{ color: VERSION_DOT[segment.version] ?? COLORS.neutral }}>●</span>{" "}
            <strong>{structuralVersionLabel(segment.version)}</strong>: {formatDay(segment.start)} – {formatDay(segment.end)} ·{" "}
            {segment.count} punto{segment.count === 1 ? "" : "s"}
          </li>
        ))}
      </ul>
    </ChartCard>
  );
}

/** Per-variable z-scores — this is what makes a low score actionable. */
export function ZScoreChart({ points }: { points: StructuralPoint[] }) {
  const sorted = [...points].sort((a, b) => (a.at ?? a.date).localeCompare(b.at ?? b.date));
  const segments = structuralVersionSegments(sorted);
  return (
    <ChartCard
      title="Desviación por variable (z-scores)"
      question="Si se ha desviado, ¿QUÉ se ha desviado y en qué dirección?"
      howToRead="Estos z son la entrada del motor de riesgo, no la señal de cambio canónica. 0 en un eje presente significa que esa variable coincide con la ventana del motor; un eje ausente no se dibuja como cero. Para ánimo, craving invertido y autoeficacia, valores negativos indican desviación adversa y positivos desviación favorable. En sueño, negativo significa menos horas y positivo más: ambas direcciones requieren contexto, sin diagnóstico automático. El denominador mínimo v2 es 1 punto para escalas 0–10 y 0,5 h para sueño. La similitud usa |z|; las reglas usan los componentes adversos sin compensarlos con mejoras."
      empty={points.length === 0}
    >
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={sorted} margin={{ top: 16, right: 16, bottom: 4, left: -18 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <ReferenceLine y={0} stroke="#3a4a63" />
          {versionMarkers(segments)}
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={formatDay} minTickGap={24} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip labelFormatter={formatDay} />
          <Legend />
          <Line type="monotone" dataKey="z_mood" name="Ánimo" stroke={COLORS.mood} connectNulls={false} dot={false} />
          <Line
            type="monotone"
            dataKey="z_craving_inv"
            name="Craving (invertido)"
            stroke={COLORS.craving}
            connectNulls={false}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="z_sleep_hours"
            name="Sueño"
            stroke={COLORS.sleep}
            connectNulls={false}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="z_self_efficacy"
            name="Autoeficacia"
            stroke={COLORS.efficacy}
            connectNulls={false}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

type CheckInChartPoint = Pick<CheckInPoint, "date"> & {
  mood?: number | null;
  craving?: number | null;
  sleep_hours?: number | null;
  self_efficacy?: number | null;
};

export function CheckInChart({ points }: { points: CheckInChartPoint[] }) {
  return (
    <ChartCard
      title="Check-ins declarados"
      question="¿Qué está reportando el paciente día a día?"
      howToRead="Ánimo, craving y autoeficacia en 0–10 (eje izquierdo); sueño en horas, de 0 a 24 (eje derecho, línea discontinua). Un valor ausente nunca se sustituye por cero. Un craving mayor expresa más deseo de consumo; ánimo y autoeficacia mayores expresan mejor estado y más confianza."
      empty={!points.some((point) => [point.mood, point.craving, point.self_efficacy, point.sleep_hours].some((value) => typeof value === "number" && Number.isFinite(value)))}
    >
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 4, left: -18 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={formatDay} minTickGap={24} />
          <YAxis yAxisId="left" domain={[0, 10]} ticks={[0, 2, 4, 6, 8, 10]} tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" domain={[0, 24]} ticks={[0, 6, 12, 18, 24]} tickFormatter={(value: number) => `${value} h`} tick={{ fontSize: 11 }} />
          <Tooltip labelFormatter={formatDay} />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="mood" name="Ánimo" stroke={COLORS.mood} connectNulls={false} />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="craving"
            name="Craving"
            stroke={COLORS.craving}
            connectNulls={false}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="self_efficacy"
            name="Autoeficacia"
            stroke={COLORS.efficacy}
            connectNulls={false}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="sleep_hours"
            name="Sueño (h)"
            stroke={COLORS.sleep}
            strokeDasharray="5 3"
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

/**
 * Agent 2 output over time. Points where the model raised a flag are drawn
 * as an extra scatter series so they are visible at a glance and can be
 * traced back to the sentence that produced them.
 */
export function LinguisticSignalChart({
  points,
  onSelect,
}: {
  points: LinguisticPoint[];
  onSelect?: (point: LinguisticPoint) => void;
}) {
  const data = points.filter((point) => point.is_active !== false).map((point) => ({
    ...point,
    flagged:
      point.ideation_direct || point.ideation_indirect || point.consumption_crisis ? 1 : null,
  }));
  return (
    <ChartCard
      title="Señales lingüísticas del Agente 2"
      question="¿Cómo está escribiendo el paciente en chat y diario?"
      howToRead="Un punto por cada texto analizado (chat o diario), en escala 0–1. Son INFERENCIAS de un modelo de lenguaje, no medidas. Los rombos en la línea superior marcan textos donde el modelo levantó una bandera (ideación o crisis de consumo): pincha en un punto para abrir el texto original en la pestaña Evidencia."
      empty={data.length === 0}
      footer={
        <p className="chart-footnote">
          Las banderas de ideación directa, ideación indirecta y crisis de consumo forman parte de las
          reglas de seguridad. Su interpretación requiere revisar el texto, la antigüedad de la señal y
          la valoración profesional; no son diagnósticos ni puntuaciones de una escala clínica.
          Las inferencias refutadas se excluyen de esta gráfica y de las estadísticas, y siguen en la trazabilidad.
        </p>
      }
    >
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart
          data={data}
          margin={{ top: 8, right: 16, bottom: 4, left: -18 }}
          onClick={(state) => {
            const index = state?.activeTooltipIndex;
            if (onSelect && typeof index === "number" && data[index]) onSelect(data[index]);
          }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={formatDay} minTickGap={24} />
          <YAxis domain={[0, 1.12]} ticks={[0, 0.25, 0.5, 0.75, 1]} tick={{ fontSize: 11 }} />
          <Tooltip
            labelFormatter={formatDay}
            formatter={(value: unknown, name) =>
              name === "Bandera crítica" ? ["sí", name] : [value as number, name]
            }
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="rumination_score"
            name="Rumiación"
            stroke={COLORS.rumination}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="negative_valence"
            name="Valencia negativa"
            stroke={COLORS.valence}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="urgency_level"
            name="Urgencia"
            stroke={COLORS.urgency}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="ambivalence"
            name="Ambivalencia"
            stroke={COLORS.ambivalence}
            strokeDasharray="4 3"
            connectNulls={false}
          />
          <Scatter dataKey="flagged" name="Bandera crítica" fill={COLORS.level} shape="diamond" />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

/**
 * Psychosocial vulnerability over time.
 *
 * Drawn separately from the structural score on purpose: the two run in
 * opposite directions (high score = stable, high index = adverse) and
 * sharing an axis would invite exactly the misreading this redesign exists
 * to prevent.
 */
export function PsychosocialIndexChart({ points }: { points: PsychosocialPoint[] }) {
  return (
    <ChartCard
      title="Vulnerabilidad psicosocial"
      question="¿Se está estrechando el contexto de vida del paciente?"
      howToRead="0.00 = sin adversidad social registrada; 1.00 = adversidad marcada en los dominios de más peso (vivienda, apoyo, pérdidas, economía, vínculo con el tratamiento). Aquí MÁS ALTO ES PEOR — al revés que el score estructural. Los rombos marcan días con un cambio adverso reciente. Sale de lo que el paciente cuenta, así que un tramo plano puede significar «sin cambios» o «no ha hablado del tema»."
      empty={points.length === 0}
      footer={
        <p className="chart-footnote">
          El índice por sí solo nunca genera alerta profesional: para llegar a nivel 3 tiene que converger con
          inestabilidad estructural, sueño empeorando o rumiación alta.
        </p>
      }
    >
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart
          data={points.map((point) => ({ ...point, change: point.has_acute_change ? 1.05 : null }))}
          margin={{ top: 8, right: 16, bottom: 4, left: -18 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <ReferenceArea y1={0.6} y2={1.12} fill="#e36a6a" fillOpacity={0.07} />
          <ReferenceArea y1={0.35} y2={0.6} fill="#e5b75f" fillOpacity={0.08} />
          <ReferenceLine y={0.6} stroke="#e36a6a" strokeDasharray="4 4" />
          <ReferenceLine y={0.35} stroke="#e5b75f" strokeDasharray="4 4" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={formatDay} minTickGap={24} />
          <YAxis domain={[0, 1.12]} ticks={[0, 0.25, 0.5, 0.75, 1]} tick={{ fontSize: 11 }} />
          <Tooltip
            labelFormatter={formatDay}
            formatter={(value: unknown, name) =>
              name === "Cambio reciente" ? ["sí", name] : [value as number, name]
            }
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="index"
            name="Índice psicosocial"
            stroke={COLORS.psychosocial}
            strokeWidth={2}
            connectNulls
            dot={{ r: 2 }}
          />
          <Scatter dataKey="change" name="Cambio reciente" fill={COLORS.level} shape="diamond" />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

type TrajectoryPoint = {
  date: string;
  mood?: number | null;
  craving?: number | null;
  sleep_hours?: number | null;
  self_efficacy?: number | null;
};

const PATIENT_SERIES = [
  { key: "mood", name: "Ánimo", stroke: "#7ea8f7", width: 2.5, axis: "left" },
  { key: "craving", name: "Craving", stroke: "#df9a73", width: 2.5, axis: "left" },
  { key: "self_efficacy", name: "Autoeficacia", stroke: "#76cdbd", width: 2.5, axis: "left" },
  { key: "sleep_hours", name: "Sueño (h)", stroke: "#e9c982", width: 2, axis: "sleep", dash: "5 3" },
] as const;

/** Patient Hoy/Tendencias chart. Colours and axes stay those of the patient screens. */
export function PatientTrajectoryChart({
  points,
  height,
  margin,
  dotRadius,
  sleepDotRadius = dotRadius,
  formatSleepTicks = false,
}: {
  points: TrajectoryPoint[];
  height: number;
  margin: { top: number; right: number; bottom: number; left: number };
  dotRadius: number;
  sleepDotRadius?: number;
  formatSleepTicks?: boolean;
}) {
  return (
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
          {...(formatSleepTicks ? { tickFormatter: (value: number) => value + " h" } : {})}
        />
        <Tooltip labelFormatter={formatDay} />
        <Legend />
        {PATIENT_SERIES.map((series) => (
          <Line
            key={series.key}
            yAxisId={series.axis}
            type="monotone"
            dataKey={series.key}
            name={series.name}
            stroke={series.stroke}
            strokeWidth={series.width}
            {...("dash" in series ? { strokeDasharray: series.dash } : {})}
            connectNulls={false}
            dot={{ r: series.axis === "sleep" ? sleepDotRadius : dotRadius }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Alerts and confirmed facts as a readable timeline, not a chart. */
export function EventTimeline({ events }: { events: MetricEvent[] }) {
  if (events.length === 0) {
    return <p className="meta">Sin alertas ni hechos registrados en la ventana.</p>;
  }
  return (
    <ol className="event-timeline">
      {[...events].reverse().map((event) => (
        <li key={`${event.kind}-${event.id}`} className={`event-${event.kind}`}>
          <span className="event-date">{formatDay(event.at)}</span>
          <span className={`event-tag event-tag-${event.kind}`}>
            {event.kind === "alert" ? `Alerta N${event.level}` : "Hecho"}
          </span>
          <span className="event-label">{event.label}</span>
          <span className="meta"> · {event.status}</span>
        </li>
      ))}
    </ol>
  );
}
