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

const WAVE_WIDTH = 320;
const WAVE_HEIGHT = 180;
const WAVE_SAMPLES = 56;

interface WaveLayer {
  amplitude: number;
  cycles: number;
  phaseOffset: number;
  speed: number;
  verticalOffset: number;
}

/**
 * Several layered fields. The emotional cue is vertical drama:
 * at a fixed intensity the surface heaves hard (peak ↔ trough), and
 * raising intensity makes that heave taller, sharper and faster —
 * anguish at the crest, settling calm in the trough.
 */
const WAVE_LAYERS: WaveLayer[] = [
  { amplitude: 0.58, cycles: 1.55, phaseOffset: 1.35, speed: 0.72, verticalOffset: 8 },
  { amplitude: 0.84, cycles: 2.05, phaseOffset: -0.55, speed: 1.05, verticalOffset: 3 },
  { amplitude: 1.0, cycles: 2.45, phaseOffset: 0.08, speed: 1.32, verticalOffset: 0 },
];

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function waveSurface(level: number, phase: number, layer: WaveLayer): Array<{ x: number; y: number }> {
  const normalized = clamp01(level / 10);
  // Keep mid intensities expressive; don't wait until 9–10 to feel motion.
  const severity = Math.pow(normalized, 1.15);

  // Body of water sits lower when calm; rises when urge is high.
  const baseWaterline = 158 - severity * 48;
  // Dominant emotional signal: whole surface heaves peak ↔ trough.
  // Level ~1 ≈ gentle bob; level 10 ≈ nearly the full canvas.
  const swellRange = 7 + severity * 72;
  const heaveSpeed = 0.85 + severity * 1.55;
  const swell =
    (0.5 - 0.5 * Math.cos(phase * heaveSpeed + layer.phaseOffset * 0.22)) * swellRange;

  // Traveling crests on top of the heave — also scale hard with intensity.
  const amplitude = (5 + severity * 52) * layer.amplitude;
  const travelPhase = phase * layer.speed * (0.85 + severity * 0.9);
  const sharpness = 0.18 + severity * 0.72;

  return Array.from({ length: WAVE_SAMPLES + 1 }, (_, index) => {
    const x = (index / WAVE_SAMPLES) * WAVE_WIDTH;
    const position = index / WAVE_SAMPLES;
    const angle = position * Math.PI * 2 * layer.cycles + travelPhase + layer.phaseOffset;
    const raw = Math.sin(angle);
    // Stretch peaks / soften troughs at high urge → jagged anxiety crests.
    const shaped = raw >= 0 ? Math.pow(raw, 1 - severity * 0.35) * (1 + severity * 0.45) : raw * (0.7 - severity * 0.12);
    const harmonic = sharpness * Math.sin(angle * 2.05 - travelPhase * 0.75);
    const chop = severity * 0.16 * Math.sin(angle * 3.4 + travelPhase * 1.1);
    const y =
      baseWaterline -
      swell +
      layer.verticalOffset +
      (shaped + harmonic + chop) * amplitude * 0.5;
    return { x, y: Math.max(6, Math.min(WAVE_HEIGHT - 2, y)) };
  });
}

function fillWavePath(points: Array<{ x: number; y: number }>): string {
  const surface = points.map(({ x, y }) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L ");
  return `M 0 ${WAVE_HEIGHT} L ${surface} L ${WAVE_WIDTH} ${WAVE_HEIGHT} Z`;
}

function surfacePath(points: Array<{ x: number; y: number }>): string {
  return `M ${points.map(({ x, y }) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L ")}`;
}

function wavePath(level: number, phase: number, layer: WaveLayer): string {
  return fillWavePath(waveSurface(level, phase, layer));
}

function foamPath(level: number, phase: number): string {
  return surfacePath(waveSurface(level, phase, WAVE_LAYERS[2]));
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

function phaseFromProgress(progress: number, start: number, peak: number): RidePhase {
  if (progress <= 0) return "idle";
  if (progress >= 1) return "done";
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
      return "Ajusta la intensidad y mira cómo el pico y el fondo cambian. Luego pulsa «Observar la ola».";
  }
}

export default function WavePage() {
  const [urgeLevel, setUrgeLevel] = useState(5);
  const [alternatives, setAlternatives] = useState<string[]>([]);
  const [rideStatus, setRideStatus] = useState<RideStatus>("idle");
  const [rideProgress, setRideProgress] = useState(0);
  const [visualPhase, setVisualPhase] = useState(0);

  const startLevelRef = useRef(5);
  const peakRef = useRef(7);
  const elapsedRef = useRef(0);
  const urgeLevelRef = useRef(5);
  const lastTickRef = useRef<number | null>(null);
  const visualPhaseRef = useRef(0);
  const visualFrameAccumulatorRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    api
      .get<ResourcesResponse>("/api/v1/safety-plan/resources")
      .then((r) => setAlternatives(r.safe_grounding_alternatives))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let mounted = true;
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

    const tick = (now: number) => {
      if (!mounted) return;
      if (lastTickRef.current === null) lastTickRef.current = now;

      const delta = Math.min(80, now - lastTickRef.current);
      lastTickRef.current = now;

      if (rideStatus === "riding") {
        elapsedRef.current = Math.min(RIDE_DURATION_MS, elapsedRef.current + delta);
        const progress = elapsedRef.current / RIDE_DURATION_MS;
        const next = intensityAt(progress, startLevelRef.current, peakRef.current);
        const displayNext = Math.round(next * 10) / 10;
        urgeLevelRef.current = displayNext;
        setUrgeLevel(displayNext);
        setRideProgress(progress);

        if (progress >= 1) {
          urgeLevelRef.current = 0;
          setUrgeLevel(0);
          setRideProgress(1);
          setRideStatus("done");
        }
      }

      if (rideStatus !== "paused" && !reducedMotion) {
        const motionLevel =
          rideStatus === "riding"
            ? intensityAt(elapsedRef.current / RIDE_DURATION_MS, startLevelRef.current, peakRef.current)
            : urgeLevelRef.current;
        const severity = Math.pow(clamp01(motionLevel / 10), 1.15);
        // Low intensity: slow calm pulse. High: frantic advance.
        const speed = 0.00085 + severity * 0.0085;
        visualPhaseRef.current += delta * speed;

        visualFrameAccumulatorRef.current += delta;
        if (visualFrameAccumulatorRef.current >= 28) {
          visualFrameAccumulatorRef.current = 0;
          setVisualPhase(visualPhaseRef.current);
        }
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      mounted = false;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      lastTickRef.current = null;
      visualFrameAccumulatorRef.current = 0;
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

  const waveBack = useMemo(
    () => wavePath(Math.max(0, urgeLevel - 1.3), visualPhase, WAVE_LAYERS[0]),
    [urgeLevel, visualPhase],
  );

  const waveMid = useMemo(
    () => wavePath(Math.max(0, urgeLevel - 0.5), visualPhase, WAVE_LAYERS[1]),
    [urgeLevel, visualPhase],
  );

  const waveFront = useMemo(
    () => wavePath(urgeLevel, visualPhase, WAVE_LAYERS[2]),
    [urgeLevel, visualPhase],
  );

  const waveFoam = useMemo(() => foamPath(urgeLevel, visualPhase), [urgeLevel, visualPhase]);

  const waveState =
    ridePhase === "crest" || urgeLevel >= 8
      ? "storm"
      : ridePhase === "rising" || urgeLevel >= 4
        ? "rising"
        : "calm";
  const waveStyle = {
    "--wave-fill": `${Math.min(100, Math.max(8, urgeLevel * 9.2))}%`,
    "--wave-intensity": String(urgeLevel / 10),
  } as CSSProperties;

  function startRide() {
    const start = Math.min(10, Math.max(0, urgeLevel));
    const peak = peakForStart(start);
    startLevelRef.current = start;
    peakRef.current = peak;
    const startProgress = start >= peak - 0.05 ? RISE_FRAC : 0;
    elapsedRef.current = RIDE_DURATION_MS * startProgress;
    lastTickRef.current = null;
    setRideProgress(startProgress);
    urgeLevelRef.current = start;
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
    urgeLevelRef.current = value;
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
          <svg className="wave-svg" viewBox={`0 0 ${WAVE_WIDTH} ${WAVE_HEIGHT}`} preserveAspectRatio="none">
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
