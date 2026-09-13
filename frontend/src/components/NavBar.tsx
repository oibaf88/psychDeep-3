import { Link } from "react-router-dom";
import { ROLE_LABELS, UserRole } from "../api";
import { useAuth } from "../auth/AuthContext";
import PsychDeepMark from "./PsychDeepMark";

export default function NavBar() {
  const { user, logout } = useAuth();

  if (!user) {
    return (
      <nav className="navbar">
        <div className="navbar-brand">
          <PsychDeepMark variant="compact" className="navbar-mark" />
          <span>PsychDeep</span>
        </div>
        <div className="navbar-links">
          <Link to="/login">Entrar</Link>
          <Link to="/settings">Estado</Link>
        </div>
      </nav>
    );
  }

  const role = user.role as UserRole;
  const isPatient = role === "patient";
  const isTherapist = role === "therapist";
  const isSupervisor = role === "supervisor";
  const isAdmin = role === "admin_clinical";

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <PsychDeepMark variant="compact" className="navbar-mark" />
        <span>PsychDeep</span>
      </div>
      <div className="navbar-links">
        {isPatient && (
          <>
            <Link to="/">Hoy</Link>
            <Link to="/trends">Tendencias</Link>
            <Link to="/wave">Regular</Link>
            <Link to="/diary">Diario</Link>
            <Link to="/safety-plan">Plan</Link>
            <Link to="/sharing">Compartir</Link>
            <Link to="/notifications">Avisos</Link>
          </>
        )}
        {isTherapist && (
          <>
            <Link to="/professional">Pacientes</Link>
            <Link to="/professional/alerts">Alertas</Link>
            <Link to="/professional/copilot">Copiloto</Link>
            <Link to="/professional/assignments">Asignaciones</Link>
            <Link to="/professional/manual">Manual</Link>
            <Link to="/notifications">Avisos</Link>
          </>
        )}
        {isSupervisor && (
          <>
            <Link to="/professional">Pacientes</Link>
            <Link to="/professional/alerts">Alertas</Link>
            <Link to="/professional/copilot">Copiloto</Link>
            <Link to="/professional/assignments">Asignaciones</Link>
            <Link to="/professional/audit">Auditoría</Link>
            <Link to="/professional/manual">Manual</Link>
            <Link to="/notifications">Avisos</Link>
          </>
        )}
        {isAdmin && (
          <>
            <Link to="/professional">Roster</Link>
            <Link to="/professional/users">Usuarios</Link>
            <Link to="/professional/assignments">Asignaciones</Link>
            <Link to="/professional/audit">Auditoría</Link>
            <Link to="/professional/manual">Manual</Link>
            <Link to="/notifications">Avisos</Link>
          </>
        )}
        <Link to="/account">Mi cuenta</Link>
        <Link to="/settings">Estado</Link>
      </div>
      <div className="navbar-user">
        <span>{user.display_name} · {ROLE_LABELS[role] || role}</span>
        <button onClick={logout}>Salir</button>
      </div>
    </nav>
  );
}
