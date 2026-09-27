import { CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import BreathingPacer from "../components/BreathingPacer";
import { api } from "../api";
import "../wave-swell.css";

interface ResourcesResponse {
  safe_grounding_alternatives: string[];
}

const STOP_STEPS = [
  { letter: "S", text: "Stop: detente, no reacciones automaticamente." },
  { letter: "T", text: "Toma distancia: alejate mentalmente de la situacion." },
  { letter: "O", text: "Observa: que sientes, que piensas y que esta pasando alrededor." },
  { letter: "P", text: "Procede con conciencia: elige tu siguiente paso." },
];

/** Total ride length in ms: rise → brief crest → long fall (urge surfing). */
const RIDE_DURATION_MS = 90_000;
const RISE_FRAC = 0.28;
const CREST_FRAC = 0.12;

type RideStatus = "idle" | "riding" | "paused" | "done";
type RidePhase = "idle" | "rising" | "crest" | "falling" | "done";

/**
 * One soft swell: water fills from the bottom and a single crest sits on top.
 * Higher `level` → higher water + taller crest. `crestX` slides the crest
 * left→center→right so the ride reads as one wave passing, not a scrolling sine.
 */
function swellPath(level: number, crestX: number, softness = 1) {
  const clamped = Math.min(10, Math.max(0, level));
  const surface = 152 - clamped * 9.8;
  const amp = (6 + clamped * 5.2) * softness;
  const halfWidth = 70 + clamped * 4;
  const left = crestX - halfWidth;
  const right = crestX + halfWidth;
  const crestY = surface - amp;
  const shoulder = surface - amp * 0.28;

  return [
    `M 0 160`,
    `L 0 ${surface}`,
    `L ${Math.max(0, left - 20)} ${surface}`,
    `C ${left} ${surface}, ${left + halfWidth * 0.28} ${shoulder}, ${crestX - halfWidth * 0.18} ${crestY + amp * 0.12}`,
    `C ${crestX - halfWidth * 0.06} ${crestY}, ${crestX + halfWidth * 0.06} ${crestY}, ${crestX + halfWidth * 0.18} ${crestY + amp * 0.12}`,
    `C ${right - halfWidth * 0.28} ${shoulder}, ${right} ${surface}, ${Math.min(320, right + 20)} ${surface}`,
    `L 320 ${surface}`,
    `L 320 160`,
    `Z`,
  ].join(" ");
}

function foamPath(level: number, crestX: number) {
  const clamped = Math.min(10, Math.max(0, level));
  const surface = 152 - clamped * 9.8;
  const amp = 6 + clamped * 5.2;
  const halfWidth = 70 + clamped * 4;
  const crestY = surface - amp;
  const left = crestX - halfWidth * 0.55;
  const right = crestX + halfWidth * 0.55;
  return [
    `M ${left} ${surface - amp * 0.15}`,
    `C ${crestX - halfWidth * 0.2} ${crestY + 2}, ${crestX - 8} ${crestY}, ${crestX} ${crestY}`,
    `C ${crestX + 8} ${crestY}, ${crestX + halfWidth * 0.2} ${crestY + 2}, ${right} ${surface - amp * 0.15}`,
  ].join(" ");
}

function peakForStart(start: number): number {
  if (start >= 8) return start;
  return Math.min(10, start + Math.max(2, Math.ceil((10 - start) * 0.35)));
}

function intensityAt(progress: number, start: number, peak: number): number {
  const p = Math.min(1, Math.max(0, progress));
  if (p < RISE_FRAC) {
    const t = p / RISE_FRAC;
    const eased = t * t * (3 - 2 * t);
    return start + (peak - start) * eased;
  }
  if (p < RISE_FRAC + CREST_FRAC) {
    return peak;
  }
  const t = (p - RISE_FRAC - CREST_FRAC) / (1 - RISE_FRAC - CREST_FRAC);
  const eased = t * t * (3 - 2 * t);
  return peak * (1 - eased);
}

function crestXAt(progress: number): number {
  const p = Math.min(1, Math.max(0, progress));
  if (p < RISE_FRAC) {
    const t = p / RISE_FRAC;
    return 48 + (160 - 48) * (t * t * (3 - 2 * t));
  }
  if (p < RISE_FRAC + CREST_FRAC) {
    return 160;
  }
  const t = (p - RISE_FRAC - CREST_FRAC) / (1 - RISE_FRAC - CREST_FRAC);
  return 160 + (272 - 160) * (t * t * (3 - 2 * t));
}

function phaseFromProgress(progress: number, start: number, peak: number): RidePhase {
  if (progress <= 0) return "idle";
  if (progress >= 1) return "done";
  // Already at peak: skip "rising" copy even during the rise time window.
  if (start >= peak - 0.05) {
    if (progress < RISE_FRAC + CREST_FRAC) return "crest";
    return "falling";
  }
  if (progress < RISE_FRAC) return "rising";
  if (progress < RISE_FRAC + CREST_FRAC) return "crest";
  return "falling";
}

function coachingForPhase(phase: RidePhase, paused: boolean): string {
  if (paused) return "Pausa. La ola se queda donde está hasta que sigas.";
  switch (phase) {
    case "rising":
      return "La ola está subiendo. Obsérvala sin pelear ni perseguirla.";
    case "crest":
      return "Este es el pico. Se siente intenso, y también pasa.";
    case "falling":
      return "La ola está bajando. Sigue observando el movimiento.";
    case "done":
      return "La ola ha bajado. Puedes volver a observar o ajustar la intensidad a mano.";
    default:
      return "Ajusta la intensidad inicial y pulsa «Observar la ola» para verla subir, hacer pico y bajar.";
  }
}

export default function WavePage() {
  const [urgeLevel, setUrgeLevel] = useState(5);
  const [alternatives, setAlternatives] = useState<string[]>([]);
  const [rideStatus, setRideStatus] = useState<RideStatus>("idle");
  const [rideProgress, setRideProgress] = useState(0);

  const startLevelRef = useRef(5);
  const peakRef = useRef(7);
  const elapsedRef = useRef(0);
  const lastTickRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    api
      .get<ResourcesResponse>("/api/v1/safety-plan/resources")
      .then((r) => setAlternatives(r.safe_grounding_alternatives))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (rideStatus !== "riding") {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      lastTickRef.current = null;
      return undefined;
    }

    const tick = (now: number) => {
      if (lastTickRef.current === null) {
        lastTickRef.current = now;
      }
      const delta = now - lastTickRef.current;
      lastTickRef.current = now;
      elapsedRef.current = Math.min(RIDE_DURATION_MS, elapsedRef.current + delta);
      const progress = elapsedRef.current / RIDE_DURATION_MS;
      const next = intensityAt(progress, startLevelRef.current, peakRef.current);
      setUrgeLevel(Math.round(next * 10) / 10);
      setRideProgress(progress);

      if (progress >= 1) {
        setUrgeLevel(0);
        setRideProgress(1);
        setRideStatus("done");
        rafRef.current = null;
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [rideStatus]);

  const isAuto = rideStatus === "riding" || rideStatus === "paused";
  const displayLevel = Math.round(urgeLevel);
  const ridePhase: RidePhase =
    rideStatus === "done"
      ? "done"
      : isAuto
        ? phaseFromProgress(rideProgress, startLevelRef.current, peakRef.current)
        : "idle";

  const crestX = isAuto || rideStatus === "done" ? crestXAt(rideProgress) : 160;
  const waveFront = useMemo(() => swellPath(urgeLevel, crestX, 1), [urgeLevel, crestX]);
  const waveBack = useMemo(
    () => swellPath(Math.max(0, urgeLevel - 1.5), crestX - 28, 0.72),
    [urgeLevel, crestX],
  );
  const waveMid = useMemo(
    () => swellPath(Math.max(0, urgeLevel - 0.6), crestX + 18, 0.88),
    [urgeLevel, crestX],
  );
  const waveFoam = useMemo(() => foamPath(urgeLevel, crestX), [urgeLevel, crestX]);

  const waveState =
    ridePhase === "crest" || urgeLevel >= 8 ? "storm" : ridePhase === "rising" || urgeLevel >= 4 ? "rising" : "calm";
  const waveStyle = {
    "--wave-fill": `${Math.min(100, Math.max(8, urgeLevel * 9.2))}%`,
  } as CSSProperties;

  function startRide() {
    const start = Math.min(10, Math.max(0, urgeLevel));
    const peak = peakForStart(start);
    startLevelRef.current = start;
    peakRef.current = peak;
    // If already at the peak, skip the empty "rise" and begin at the crest window.
    const startProgress = start >= peak - 0.05 ? RISE_FRAC : 0;
    elapsedRef.current = RIDE_DURATION_MS * startProgress;
    lastTickRef.current = null;
    setRideProgress(startProgress);
    setUrgeLevel(start);
    setRideStatus("riding");
  }

  function pauseRide() {
    setRideStatus("paused");
  }

  function resumeRide() {
    lastTickRef.current = null;
    setRideStatus("riding");
  }

  function stopRide() {
    setRideStatus("idle");
    setRideProgress(0);
    elapsedRef.current = 0;
    lastTickRef.current = null;
  }

  function onSliderChange(value: number) {
    if (isAuto) return;
    setUrgeLevel(value);
    if (rideStatus === "done") {
      setRideStatus("idle");
      setRideProgress(0);
    }
  }

  const coaching = coachingForPhase(ridePhase, rideStatus === "paused");

  return (
    <div className="page">
      <h1>Metafora de la Ola</h1>
      <p className="subtitle">
        La urgencia puede sentirse enorme cuando sube. Esta practica entrena observarla mientras se mueve, alcanza un
        pico y vuelve a bajar.
      </p>

      <section className="card">
        <label>
          Intensidad de la urgencia ahora (0-10): {displayLevel}
          <input
            type="range"
            min={0}
            max={10}
            step={1}
            value={displayLevel}
            disabled={isAuto}
            onChange={(e) => onSliderChange(Number(e.target.value))}
            aria-valuemin={0}
            aria-valuemax={10}
            aria-valuenow={displayLevel}
            aria-label="Intensidad de la urgencia de 0 a 10"
          />
        </label>

        <div className="wave-ride-controls" style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "12px" }}>
          {rideStatus === "idle" || rideStatus === "done" ? (
            <button type="button" onClick={startRide}>
              Observar la ola (~90 s)
            </button>
          ) : null}
          {rideStatus === "riding" ? (
            <button type="button" className="btn-secondary" onClick={pauseRide}>
              Pausar
            </button>
          ) : null}
          {rideStatus === "paused" ? (
            <button type="button" onClick={resumeRide}>
              Seguir observando
            </button>
          ) : null}
          {isAuto ? (
            <button type="button" className="btn-secondary" onClick={stopRide}>
              Detener
            </button>
          ) : null}
        </div>

        <p className="meta" aria-live="polite">
          {coaching}
        </p>

        {isAuto ? (
          <div
            className="wave-ride-progress"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(rideProgress * 100)}
            aria-label="Progreso de la observación de la ola"
          >
            <div className="wave-ride-progress__bar" style={{ width: `${Math.round(rideProgress * 100)}%` }} />
          </div>
        ) : null}

        <div
          className={`wave-visual wave-visual--swell wave-visual--${waveState}${isAuto || rideStatus === "done" ? " wave-visual--riding" : ""}`}
          style={waveStyle}
          aria-hidden="true"
          data-phase={ridePhase}
        >
          <svg className="wave-svg" viewBox="0 0 320 160" preserveAspectRatio="none">
            <defs>
              <linearGradient id="waveFrontGradient" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#7fd8c2" />
                <stop offset="46%" stopColor="#6c98f4" />
                <stop offset="100%" stopColor="#2f4f9e" />
              </linearGradient>
              <linearGradient id="waveBackGradient" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0%" stopColor="#b9cdfa" stopOpacity="0.7" />
                <stop offset="100%" stopColor="#6c98f4" stopOpacity="0.55" />
              </linearGradient>
              <linearGradient id="waveMidGradient" x1="0" x2="0.7" y1="0" y2="1">
                <stop offset="0%" stopColor="#9bded8" stopOpacity="0.78" />
                <stop offset="100%" stopColor="#4578c9" stopOpacity="0.72" />
              </linearGradient>
            </defs>
            <path className="wave-back" d={waveBack} />
            <path className="wave-mid" d={waveMid} />
            <path className="wave-front" d={waveFront} />
            <path className="wave-foam" d={waveFoam} />
          </svg>
        </div>
      </section>

      <section className="card">
        <h2>Respiracion guiada</h2>
        <BreathingPacer />
      </section>

      <section className="card">
        <h2>DBT - STOP</h2>
        <ul>
          {STOP_STEPS.map((s) => (
            <li key={s.letter}>
              <strong>{s.letter}</strong> - {s.text}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Anclaje sensorial seguro</h2>
        <p className="info">
          Evita tecnicas de frio intenso o dolor fisico. Prueba una alternativa sensorial suave y reversible:
        </p>
        <ul>
          {alternatives.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
