import { CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import BreathingPacer from "../components/BreathingPacer";
import { api } from "../api";

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

function wavePath(level: number, offset: number, detail = 1) {
  const baseline = 128 - level * 6.5;
  const amplitude = 5 + level * 3.15;
  const wavelength = Math.max(38, 98 - level * 4) / detail;
  const crestSkew = Math.min(0.72, 0.34 + level * 0.035);
  let path = `M ${-wavelength + offset} ${baseline}`;

  for (let x = -wavelength + offset; x < 384 + wavelength; x += wavelength) {
    path += ` C ${x + wavelength * 0.15} ${baseline - amplitude * crestSkew}, ${x + wavelength * 0.42} ${
      baseline - amplitude
    }, ${x + wavelength * 0.58} ${baseline - amplitude * 0.68}`;
    path += ` C ${x + wavelength * 0.76} ${baseline - amplitude * 0.18}, ${x + wavelength * 0.84} ${
      baseline + amplitude
    }, ${x + wavelength} ${baseline}`;
  }

  return `${path} L 384 160 L 0 160 Z`;
}

function peakForStart(start: number): number {
  if (start >= 8) return start;
  return Math.min(10, start + Math.max(2, Math.ceil((10 - start) * 0.35)));
}

/** Smooth urge curve: rise from start → peak, hold, then fall to 0. */
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

function ridePhaseLabel(progress: number, level: number): string {
  if (progress < RISE_FRAC) {
    return "La ola está subiendo. Obsérvala sin pelear ni perseguirla.";
  }
  if (progress < RISE_FRAC + CREST_FRAC) {
    return "Este es el pico. Se siente intenso, y también pasa.";
  }
  if (level <= 2) {
    return "La ola casi ha bajado. Quédate un momento con lo que queda.";
  }
  return "La ola está bajando. Sigue observando el movimiento.";
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

  const waveFront = useMemo(() => wavePath(urgeLevel, 0), [urgeLevel]);
  const waveBack = useMemo(() => wavePath(Math.max(1, urgeLevel - 2), 32, 0.85), [urgeLevel]);
  const waveMid = useMemo(() => wavePath(Math.max(1, urgeLevel - 1), 62, 1.25), [urgeLevel]);
  const waveFoam = useMemo(() => wavePath(Math.min(10, urgeLevel + 1), 12, 1.6), [urgeLevel]);
  const waveState = urgeLevel >= 8 ? "storm" : urgeLevel >= 4 ? "rising" : "calm";
  const waveStyle = {
    "--wave-duration": `${Math.max(5, 12 - urgeLevel * 0.6)}s`,
    "--wave-back-duration": `${Math.max(8, 16 - urgeLevel * 0.5)}s`,
    "--wave-crest-duration": `${Math.max(3.5, 9 - urgeLevel * 0.42)}s`,
  } as CSSProperties;

  const isAuto = rideStatus === "riding" || rideStatus === "paused";
  const displayLevel = Math.round(urgeLevel);

  function startRide() {
    const start = Math.min(10, Math.max(0, urgeLevel));
    startLevelRef.current = start;
    peakRef.current = peakForStart(start);
    elapsedRef.current = 0;
    lastTickRef.current = null;
    setRideProgress(0);
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
    if (rideStatus === "done") setRideStatus("idle");
  }

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

        {isAuto || rideStatus === "done" ? (
          <p className="meta" aria-live="polite">
            {rideStatus === "paused"
              ? "Pausa. La ola se queda donde está hasta que sigas."
              : rideStatus === "done"
                ? "La ola ha bajado. Puedes volver a observar o ajustar la intensidad a mano."
                : ridePhaseLabel(rideProgress, urgeLevel)}
          </p>
        ) : (
          <p className="info">
            Ajusta la intensidad inicial y pulsa «Observar la ola» para recorrer subir, pico y bajada sin mover el
            control.
          </p>
        )}

        {isAuto ? (
          <div
            className="wave-ride-progress"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(rideProgress * 100)}
            aria-label="Progreso de la observación de la ola"
            style={{
              marginTop: "8px",
              height: "6px",
              borderRadius: "999px",
              background: "rgba(47, 79, 158, 0.15)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${Math.round(rideProgress * 100)}%`,
                height: "100%",
                background: "#6c98f4",
                transition: "width 0.1s linear",
              }}
            />
          </div>
        ) : null}

        <div className={`wave-visual wave-visual--${waveState}`} style={waveStyle} aria-hidden="true">
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
        <p>
          {urgeLevel <= 3 && "La ola esta perdiendo fuerza. Sigue observando sin perseguirla ni pelear con ella."}
          {urgeLevel > 3 && urgeLevel <= 7 && "Estas dentro de la ola. Respira, nota el movimiento y date tiempo."}
          {urgeLevel > 7 && "Este es el pico. Se siente muy intenso, pero el pico tambien se mueve y termina bajando."}
        </p>
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
