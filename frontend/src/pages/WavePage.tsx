import { CSSProperties, useEffect, useMemo, useState } from "react";
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

export default function WavePage() {
  const [urgeLevel, setUrgeLevel] = useState(5);
  const [alternatives, setAlternatives] = useState<string[]>([]);

  useEffect(() => {
    api
      .get<ResourcesResponse>("/api/v1/safety-plan/resources")
      .then((r) => setAlternatives(r.safe_grounding_alternatives))
      .catch(() => undefined);
  }, []);

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

  return (
    <div className="page">
      <h1>Metafora de la Ola</h1>
      <p className="subtitle">
        La urgencia puede sentirse enorme cuando sube. Esta practica entrena observarla mientras se mueve, alcanza un
        pico y vuelve a bajar.
      </p>

      <section className="card">
        <label>
          Intensidad de la urgencia ahora (0-10): {urgeLevel}
          <input type="range" min={0} max={10} value={urgeLevel} onChange={(e) => setUrgeLevel(Number(e.target.value))} />
        </label>
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
