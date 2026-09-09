import { useEffect, useState } from "react";
import PsychDeepMark from "./PsychDeepMark";

type BreathPhase = "inhale" | "hold" | "exhale";

const PHASES: Array<{ id: BreathPhase; label: string; durationMs: number }> = [
  { id: "inhale", label: "Inhala suave", durationMs: 4000 },
  { id: "hold", label: "Sosten un momento", durationMs: 2000 },
  { id: "exhale", label: "Exhala lento", durationMs: 6000 },
];

const TOTAL_SECONDS = PHASES.reduce((sum, phase) => sum + phase.durationMs, 0) / 1000;

export default function BreathingPacer() {
  const [running, setRunning] = useState(false);
  const [immersive, setImmersive] = useState(false);
  const [phaseIndex, setPhaseIndex] = useState(0);
  const phase = PHASES[phaseIndex];

  useEffect(() => {
    if (!running) return undefined;

    const timer = window.setTimeout(() => {
      setPhaseIndex((current) => (current + 1) % PHASES.length);
    }, phase.durationMs);

    return () => window.clearTimeout(timer);
  }, [running, phase.durationMs]);

  useEffect(() => {
    if (!immersive) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") stop();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [immersive]);

  function stop() {
    setRunning(false);
    setPhaseIndex(0);
    setImmersive(false);
  }

  function toggle() {
    if (running) {
      stop();
      return;
    }

    setPhaseIndex(0);
    setRunning(true);
    setImmersive(true);
  }

  return (
    <div className="breathing-pacer">
      {/* The pacer is the PsychDeep mark itself, breathing. The phase logic
          above stays the only clock: it writes the phase here and the
          stylesheet does the rest — no timers, audio or state in the mark. */}
      <div className="breathing-mark" data-phase={running ? phase.id : "rest"} aria-hidden="true">
        <PsychDeepMark />
      </div>
      <p className="breathing-label">{running && !immersive ? phase.label : "Pulsa iniciar para comenzar"}</p>
      <p className="breathing-ratio">4 s inspirar - 2 s sostener - 6 s exhalar - {TOTAL_SECONDS}s por ciclo</p>
      <button onClick={toggle}>{running ? "Detener" : "Iniciar respiracion guiada"}</button>
      <p className="disclaimer">
        Esto es una guia visual de ritmo respiratorio, no un dispositivo medico ni biofeedback real: no mide tu cuerpo.
      </p>
      {immersive && (
        <div
          className="breathing-immersive-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Respiración guiada inmersiva"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) stop();
          }}
        >
          <div className="breathing-immersive-stage" onMouseDown={(event) => event.stopPropagation()}>
            <p className="breathing-immersive-kicker">Respira con la ola</p>
            <div className="breathing-halo breathing-halo-one" aria-hidden="true" />
            <div className="breathing-halo breathing-halo-two" aria-hidden="true" />
            <div className="breathing-halo breathing-halo-three" aria-hidden="true" />
            <div className="breathing-mark breathing-mark--immersive" data-phase={phase.id} aria-hidden="true">
              <PsychDeepMark />
            </div>
            <p className="breathing-immersive-label" aria-live="polite">{phase.label}</p>
            <p className="breathing-immersive-ratio">4 · 2 · 6</p>
            <button type="button" className="btn-secondary breathing-immersive-close" onClick={stop}>
              Volver
            </button>
            <p className="breathing-immersive-hint">Pulsa fuera del círculo o Esc para salir.</p>
          </div>
        </div>
      )}
    </div>
  );
}
