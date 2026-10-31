import { FormEvent, useState } from "react";
import { ApiError, LongitudinalStateOut, api, formatDateTime } from "../api";

/** Mirrors `BaselineFreezeIn.reason` (min 3, max 1000) on the backend. */
export const FREEZE_NOTE_MIN = 3;
export const FREEZE_NOTE_MAX = 1000;

const SUPERVISED_FREEZE_KIND = "supervised_freeze";

const ROLE_LABELS: Record<string, string> = {
  therapist: "terapeuta asignado",
  supervisor: "supervisor",
  admin_clinical: "administración clínica",
};

export interface SupervisedFreezeRecord {
  frozen_at?: string | null;
  frozen_by_role?: string | null;
  note?: string | null;
}

type Baseline = LongitudinalStateOut["baseline"] | null | undefined;

/** The `supervised_freeze` entry on a frozen reference, if this row is one. */
export function supervisedFreezeRecord(baseline: Baseline): SupervisedFreezeRecord | null {
  if (!baseline || baseline.status !== "frozen") return null;
  for (const entry of baseline.baseline?.exclusions ?? []) {
    if (entry && typeof entry === "object" && (entry as { kind?: unknown }).kind === SUPERVISED_FREEZE_KIND) {
      return entry as SupervisedFreezeRecord;
    }
  }
  // Status says frozen even if the exclusion entry is missing: still frozen.
  return {};
}

/** Same readiness rule as Tendencias: a usable row that is not insufficient_data. */
export function referenceReady(baseline: Baseline): boolean {
  const row = baseline?.baseline;
  if (!baseline || !row || baseline.status === "insufficient_data" || row.stability === "insufficient_data") return false;
  return baseline.status === "active" || baseline.status === "provisional" || baseline.status === "frozen";
}

/** Human error text for the freeze/release endpoints. Never shows raw payloads. */
export function freezeErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "No tienes permiso para esta acción: solo el terapeuta asignado con consentimiento de compartición vigente puede conservar o liberar la referencia.";
    }
    if (error.status === 422) {
      return `La nota es obligatoria y debe tener entre ${FREEZE_NOTE_MIN} y ${FREEZE_NOTE_MAX} caracteres.`;
    }
    if (error.status === 409) {
      return `${error.message}. Recarga la ficha para ver el estado actual.`;
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "No se pudo completar la solicitud.";
}

/**
 * Supervised freeze / release of the canonical personal reference (vNext 8.2).
 *
 * This only changes which reference the canonical ChangeSignal comparison
 * uses. It never changes the alert level, the risk engine or its thresholds.
 */
export default function BaselineFreezeControl({
  patientId,
  baseline,
  canAct,
  onChanged,
}: {
  patientId: string;
  baseline: Baseline;
  /** True only for a therapist; the backend still checks assignment + consent. */
  canAct: boolean;
  onChanged?: () => void | Promise<void>;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmRelease, setConfirmRelease] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const freeze = supervisedFreezeRecord(baseline);
  const frozen = freeze !== null;
  const ready = referenceReady(baseline);
  const trimmed = note.trim();
  const noteValid = trimmed.length >= FREEZE_NOTE_MIN && trimmed.length <= FREEZE_NOTE_MAX;

  async function submitFreeze(e: FormEvent) {
    e.preventDefault();
    if (!noteValid || busy) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.post(`/api/v1/professional/patients/${patientId}/baseline/freeze`, { reason: trimmed });
      setNote("");
      setMessage("Referencia conservada. Los nuevos registros se comparan con ella y no se incorporan a la referencia.");
      await onChanged?.();
    } catch (err) {
      setError(freezeErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitRelease() {
    if (busy) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.post(`/api/v1/professional/patients/${patientId}/baseline/release`);
      setConfirmRelease(false);
      setMessage("Referencia liberada. Se ha recalculado con las ventanas habituales.");
      await onChanged?.();
    } catch (err) {
      setError(freezeErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card baseline-freeze" aria-labelledby="baseline-freeze-heading">
      <h2 id="baseline-freeze-heading">Conservar la referencia personal</h2>
      <p className="subtitle">
        Mientras está conservada, los nuevos registros se comparan con esta referencia y no se incorporan a ella. Solo
        cambia la referencia del cambio longitudinal: no modifica el nivel de alerta, el motor de riesgo ni sus umbrales.
      </p>

      <p className="baseline-freeze__state" data-testid="baseline-freeze-state">
        <strong>Estado:</strong>{" "}
        {frozen ? "Conservada, sin recalcular" : ready ? "Se recalcula con cada registro" : "Sin referencia suficiente"}
      </p>

      {frozen && (
        <dl className="baseline-freeze__record">
          <dt>Conservada desde</dt>
          <dd>{formatDateTime(freeze?.frozen_at)}</dd>
          <dt>Por</dt>
          <dd>{freeze?.frozen_by_role ? ROLE_LABELS[freeze.frozen_by_role] ?? freeze.frozen_by_role : "—"}</dd>
          <dt>Nota registrada</dt>
          <dd>{freeze?.note?.trim() ? freeze.note : "—"}</dd>
        </dl>
      )}

      {!canAct && (
        <p className="meta">
          Solo el terapeuta asignado con consentimiento de compartición vigente puede conservar o liberar la referencia.
        </p>
      )}

      {canAct && !frozen && !ready && (
        <p className="meta">No hay una referencia personal con datos suficientes para conservarla.</p>
      )}

      {canAct && !frozen && ready && (
        <form onSubmit={submitFreeze} className="baseline-freeze__form">
          <label htmlFor="baseline-freeze-note">Nota (obligatoria): motivo para conservar la referencia</label>
          <textarea
            id="baseline-freeze-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={FREEZE_NOTE_MAX}
            rows={3}
            required
            aria-describedby="baseline-freeze-note-help"
            disabled={busy}
          />
          <p id="baseline-freeze-note-help" className="meta">
            Entre {FREEZE_NOTE_MIN} y {FREEZE_NOTE_MAX} caracteres. La nota queda guardada con la referencia conservada; el
            registro de auditoría no incluye su texto. Todavía no hay una guía clínica revisada sobre cuándo conservarla.
          </p>
          <button type="submit" disabled={busy || !noteValid}>
            {busy ? "Conservando…" : "Conservar referencia"}
          </button>
        </form>
      )}

      {canAct && frozen && !confirmRelease && (
        <button type="button" disabled={busy} onClick={() => setConfirmRelease(true)}>
          Liberar referencia
        </button>
      )}

      {canAct && frozen && confirmRelease && (
        <div role="group" aria-label="Confirmar liberación de la referencia" className="baseline-freeze__confirm">
          <p>
            Al liberarla, la referencia se recalcula con las ventanas habituales y el periodo conservado puede pasar a
            formar parte de ella. La referencia conservada no se borra: queda en el historial.
          </p>
          <button type="button" disabled={busy} onClick={submitRelease}>
            {busy ? "Liberando…" : "Confirmar liberación"}
          </button>{" "}
          <button type="button" className="secondary" disabled={busy} onClick={() => setConfirmRelease(false)}>
            Cancelar
          </button>
        </div>
      )}

      {message && (
        <p className="info" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
