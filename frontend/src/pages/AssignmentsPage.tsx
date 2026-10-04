import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, AssignmentOut, ASSIGNMENT_STATUS_LABELS, UserRole } from "../api";
import { useAuth } from "../auth/AuthContext";
import { partitionAssignments } from "./assignmentGroups";

export default function AssignmentsPage() {
  const { user } = useAuth();
  const role = (user?.role || "patient") as UserRole;
  const [params] = useSearchParams();
  const patientId = params.get("patient");
  const patientName = params.get("nombre");
  const [rows, setRows] = useState<AssignmentOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const isPatient = role === "patient";
  const isClinicalAdmin = role === "admin_clinical";
  const isSupervisor = role === "supervisor";
  const showsGroups = isClinicalAdmin || isSupervisor;

  async function load() {
    setError(null);
    try {
      const query = new URLSearchParams();
      if (patientId && !isPatient) query.set("patient_id", patientId);
      const suffix = query.toString();
      const data = await api.get<AssignmentOut[]>(`/api/v1/assignments/mine${suffix ? `?${suffix}` : ""}`);
      setRows(data);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, [patientId, isPatient]);

  async function act(id: string, action: "accept" | "reject" | "pause" | "resume" | "end") {
    setBusy(id + action);
    setError(null);
    try {
      await api.post(`/api/v1/assignments/${id}/${action}`);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const focusedName =
    rows.find((row) => row.patient_display_name)?.patient_display_name || patientName || "este paciente";
  const { pending, done } = partitionAssignments(rows);

  return (
    <main className="page" aria-label="Vinculaciones">
      <h1>
        {isPatient
          ? "Vinculación con profesionales"
          : patientId
            ? `Asignaciones de ${focusedName}`
            : "Asignaciones paciente–profesional"}
      </h1>
      <p className="subtitle">
        {isPatient
          ? "Debes aceptar explícitamente cada solicitud. Al aceptar, activas el consentimiento de compartir con ese profesional."
          : showsGroups
            ? "Pendientes son solicitudes que el paciente aún no acepta. Hechas son las activas, pausadas, finalizadas o rechazadas."
            : "Solicitudes y vínculos con tus pacientes."}
      </p>
      {patientId && !isPatient && (
        <p>
          <Link to="/professional">Volver a pacientes</Link>
        </p>
      )}

      {error && <p className="error" role="alert">{error}</p>}

      {showsGroups ? (
        <>
          {rows.length === 0 && (
            <p className="info">
              {patientId
                ? "Este paciente no tiene asignaciones clínicas pendientes ni hechas."
                : "No hay asignaciones pendientes ni hechas."}
            </p>
          )}
          <AssignmentGroup
            id="asignaciones-pendientes"
            title="Pendientes"
            rows={pending}
            empty="Ninguna pendiente."
            isPatient={isPatient}
            busy={busy}
            act={act}
          />
          <AssignmentGroup
            id="asignaciones-hechas"
            title="Hechas"
            rows={done}
            empty="Ninguna hecha."
            isPatient={isPatient}
            busy={busy}
            act={act}
          />
        </>
      ) : (
        <>
          {rows.length === 0 && <p className="info">No hay asignaciones todavía.</p>}
          <div className="stack">
            {rows.map((assignment) => (
              <AssignmentCard key={assignment.id} assignment={assignment} isPatient={isPatient} busy={busy} act={act} />
            ))}
          </div>
        </>
      )}
    </main>
  );
}

function AssignmentGroup({
  id,
  title,
  rows,
  empty,
  isPatient,
  busy,
  act,
}: {
  id: string;
  title: string;
  rows: AssignmentOut[];
  empty: string;
  isPatient: boolean;
  busy: string | null;
  act: (id: string, action: "accept" | "reject" | "pause" | "resume" | "end") => void;
}) {
  return (
    <section aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {rows.length === 0 ? (
        <p className="info">{empty}</p>
      ) : (
        <div className="stack">
          {rows.map((assignment) => (
            <AssignmentCard key={assignment.id} assignment={assignment} isPatient={isPatient} busy={busy} act={act} />
          ))}
        </div>
      )}
    </section>
  );
}

function AssignmentCard({
  assignment,
  isPatient,
  busy,
  act,
}: {
  assignment: AssignmentOut;
  isPatient: boolean;
  busy: string | null;
  act: (id: string, action: "accept" | "reject" | "pause" | "resume" | "end") => void;
}) {
  const counterpart = isPatient
    ? assignment.professional_display_name || assignment.professional_email
    : assignment.patient_display_name || assignment.patient_email;
  return (
    <article className="card">
      <h3>
        {isPatient
          ? assignment.professional_display_name || assignment.professional_email || "Profesional"
          : assignment.patient_display_name || assignment.patient_email || "Paciente"}
      </h3>
      <p className="meta">
        Estado: <strong>{ASSIGNMENT_STATUS_LABELS[assignment.status] || assignment.status}</strong>
        {" · "}
        Solicitada: {new Date(assignment.requested_at).toLocaleString()}
      </p>
      <p className="meta">
        Profesional: {assignment.professional_display_name} ({assignment.professional_email})
      </p>

      <div className="alert-actions">
        {isPatient && assignment.status === "pending" && (
          <>
            <button disabled={!!busy} onClick={() => act(assignment.id, "accept")} aria-label={`Aceptar asignación con ${counterpart}`}>
              Aceptar
            </button>
            <button className="btn-secondary" disabled={!!busy} onClick={() => act(assignment.id, "reject")} aria-label={`Rechazar asignación con ${counterpart}`}>
              Rechazar
            </button>
          </>
        )}
        {assignment.status === "active" && (
          <>
            <button className="btn-secondary" disabled={!!busy} onClick={() => act(assignment.id, "pause")} aria-label={`Pausar asignación con ${counterpart}`}>
              Pausar
            </button>
            <button className="btn-danger" disabled={!!busy} onClick={() => act(assignment.id, "end")} aria-label={`Finalizar asignación con ${counterpart}`}>
              Finalizar
            </button>
          </>
        )}
        {assignment.status === "paused" && (
          <>
            <button disabled={!!busy} onClick={() => act(assignment.id, "resume")} aria-label={`Reanudar asignación con ${counterpart}`}>
              Reanudar
            </button>
            <button className="btn-danger" disabled={!!busy} onClick={() => act(assignment.id, "end")} aria-label={`Finalizar asignación con ${counterpart}`}>
              Finalizar
            </button>
          </>
        )}
      </div>
    </article>
  );
}
