import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  ASSIGNMENT_STATUS_LABELS,
  PatientSummaryOut,
  ROLE_LABELS,
  UserRole,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import { joinAssignmentLabels, partitionAssignments } from "./assignmentGroups";
import { dashboardChangeDetail, dashboardChangeHeadline } from "./professionalChange";
import { riskEngineBandText, riskEngineScoreText } from "../riskEngineReading";

export default function ProfessionalDashboard() {
  const { user } = useAuth();
  const role = (user?.role || "therapist") as UserRole;
  const [patients, setPatients] = useState<PatientSummaryOut[]>([]);
  const [patientEmail, setPatientEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canRequestAccess = role === "therapist" || role === "supervisor";
  const canSeeClinicalColumns = role !== "admin_clinical";
  const isAdmin = role === "admin_clinical";
  const isSupervisor = role === "supervisor";
  const showsAssignmentGroups = isAdmin || isSupervisor;

  async function load() {
    setPatients(await api.get<PatientSummaryOut[]>("/api/v1/professional/patients"));
  }

  useEffect(() => {
    load().catch((e) => setError((e as Error).message));
  }, []);

  async function requestAssignment(e: FormEvent) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    try {
      await api.post("/api/v1/assignments/request", { patient_email: patientEmail });
      setMessage("Solicitud enviada. El paciente debe aceptarla desde Vinculaciones.");
      setPatientEmail("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const title =
    role === "therapist"
      ? "Mis pacientes"
      : role === "supervisor"
        ? "Panel de supervisión — pacientes"
        : "Administración clínica — roster de pacientes";

  return (
    <main className="page" aria-label="Panel Profesional">
      <h1>{title}</h1>
      <p className="subtitle">
        Rol: <strong>{ROLE_LABELS[role]}</strong>
        {role === "therapist" &&
          " · Abre la ficha de cualquier paciente con asignación activa/pausada para ver el historial completo (check-ins, diario, hechos, evaluaciones). No hace falta que haya alerta."}
        {isSupervisor && " · Visibilidad de roster y alertas; puede finalizar asignaciones."}
        {isAdmin &&
          " · Ves las asignaciones clínicas pendientes y hechas de cada paciente. No ves señales, expediente ni alertas (RBAC)."}
      </p>

      {canRequestAccess && (
        <section className="card">
          <h2>Solicitar acceso a un paciente</h2>
          <p className="meta">El paciente debe aceptar la solicitud (consentimiento professional_sharing).</p>
          <form onSubmit={requestAssignment} className="inline-form">
            <input
              type="email"
              value={patientEmail}
              onChange={(e) => setPatientEmail(e.target.value)}
              placeholder="email del paciente"
              required
            />
            <button type="submit">Solicitar</button>
          </form>
          {message && <p className="info" aria-live="polite" role="status">{message}</p>}
        </section>
      )}

      {error && <p className="error" aria-live="assertive" role="alert">{error}</p>}

      <div className="table-wrap">
        <table className="table">
          <caption>Lista de pacientes</caption>
          <thead>
            <tr>
              <th scope="col">Paciente</th>
              <th scope="col">Email</th>
              <th scope="col">Asignación</th>
              {canSeeClinicalColumns && <th scope="col">Nivel operativo</th>}
              {canSeeClinicalColumns && (
                <th
                  scope="col"
                  title="Cambio respecto a su línea de base personal. No es el nivel de alerta ni el score del motor de riesgo."
                >
                  Cambio vs su referencia
                </th>
              )}
              {canSeeClinicalColumns && (
                <th
                  scope="col"
                  title="Entrada del motor de riesgo: similitud de los check-ins de 7 días con la ventana de 21 días que usa ese motor. No es la señal de cambio y no es el nivel de alerta. Si falta, no es cero ni ausencia de riesgo."
                >
                  Similitud del motor ⓘ
                </th>
              )}
              {canSeeClinicalColumns && <th scope="col">Check-ins</th>}
              {canSeeClinicalColumns && <th scope="col">Alertas abiertas</th>}
              <th scope="col"></th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.id}>
                <td>{p.display_name}</td>
                <td>{p.email}</td>
                <td>
                  {showsAssignmentGroups ? (
                    <AssignmentGroups assignments={p.assignments} />
                  ) : (
                    ASSIGNMENT_STATUS_LABELS[p.assignment_status] || p.assignment_status
                  )}
                </td>
                {canSeeClinicalColumns && (
                  <td>
                    {p.pending_alert_level != null ? (
                      <>
                        <strong className={`level-pill level-${p.pending_alert_level}`}>
                          N{p.pending_alert_level}
                        </strong>
                        <div className="meta">
                          Alerta pendiente
                          {p.pending_alert_status === "acknowledged" ? " (reconocida)" : " (abierta)"}
                          {p.latest_alert_level != null && p.latest_alert_level !== p.pending_alert_level
                            ? ` · última eval. auto. N${p.latest_alert_level}`
                            : ""}
                        </div>
                      </>
                    ) : p.latest_alert_level != null ? (
                      <>
                        <strong className={`level-pill level-${p.latest_alert_level}`}>
                          N{p.latest_alert_level}
                        </strong>
                        <div className="meta">Última evaluación automática</div>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                )}
                {canSeeClinicalColumns && (
                  <td>
                    <strong className="change-band">{dashboardChangeHeadline(p.longitudinal)}</strong>
                    <div className="meta">{dashboardChangeDetail(p.longitudinal)}</div>
                  </td>
                )}
                {canSeeClinicalColumns && (
                  <td className="meta">
                    <div>{riskEngineScoreText(p.latest_structural_score)}</div>
                    <div>{riskEngineBandText(p.latest_confidence_band)}</div>
                  </td>
                )}
                {canSeeClinicalColumns && <td>{p.checkin_count ?? "—"}</td>}
                {canSeeClinicalColumns && <td>{p.open_alerts}</td>}
                <td>
                  {role === "admin_clinical" ? (
                    <Link to={assignmentHref(p)}>Ver asignaciones</Link>
                  ) : p.assignment_status === "pending" && role === "therapist" ? (
                    <span className="meta">Esperando aceptación</span>
                  ) : (
                    <>
                      <Link to={`/professional/patients/${p.id}`}>Ver historial</Link>
                      {role === "supervisor" && (
                        <>
                          {" · "}
                          <Link to={assignmentHref(p)}>Asignaciones</Link>
                        </>
                      )}
                    </>
                  )}
                </td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr>
                <td colSpan={canSeeClinicalColumns ? 9 : 4}>
                  {role === "therapist"
                    ? "Aún no tienes pacientes. Solicita acceso por email."
                    : "No hay pacientes en el sistema."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}

function assignmentHref(patient: PatientSummaryOut) {
  const params = new URLSearchParams({ patient: patient.id, nombre: patient.display_name });
  return `/professional/assignments?${params.toString()}`;
}

function AssignmentGroups({ assignments }: { assignments: PatientSummaryOut["assignments"] }) {
  const { pending, done } = partitionAssignments(assignments ?? []);
  return (
    <>
      <div>
        <strong>Pendientes:</strong> {joinAssignmentLabels(pending)}
      </div>
      <div>
        <strong>Hechas:</strong> {joinAssignmentLabels(done)}
      </div>
    </>
  );
}
