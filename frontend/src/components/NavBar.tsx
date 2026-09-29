import { NavLink } from "react-router-dom";
import { ROLE_LABELS, UserRole } from "../api";
import { useAuth } from "../auth/AuthContext";
import PsychDeepLogo from "./PsychDeepLogo";

function MenuLink({ to, children, end = false }: { to: string; children: React.ReactNode; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => (isActive ? "active" : undefined)}
    >
      {children}
    </NavLink>
  );
}

export default function NavBar() {
  const { user, logout } = useAuth();

  if (!user) {
    return (
      <nav className="navbar" aria-label="Navegación principal">
        <div className="navbar-brand">
          <PsychDeepLogo className="navbar-mark" />
          <span>PsychDeep</span>
        </div>
        <div className="navbar-links">
          <MenuLink to="/login">Entrar</MenuLink>
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
    <nav className="navbar" aria-label="Navegación principal">
      <div className="navbar-brand">
        <PsychDeepLogo className="navbar-mark" />
        <span>PsychDeep</span>
      </div>

      <div className="navbar-links">
        {isPatient && (
          <>
            <MenuLink to="/" end>Hoy</MenuLink>
            <MenuLink to="/trends">Tendencias</MenuLink>
            <MenuLink to="/wave">Regular</MenuLink>
            <MenuLink to="/diary">Diario</MenuLink>
            <MenuLink to="/safety-plan">Plan</MenuLink>
            <MenuLink to="/sharing">Compartir</MenuLink>
            <MenuLink to="/chat">Chat</MenuLink>
            <MenuLink to="/notifications">Avisos</MenuLink>
          </>
        )}

        {isTherapist && (
          <>
            <MenuLink to="/professional">Pacientes</MenuLink>
            <MenuLink to="/professional/alerts">Alertas</MenuLink>
            <MenuLink to="/professional/copilot">Copiloto</MenuLink>
            <MenuLink to="/professional/assignments">Asignaciones</MenuLink>
            <MenuLink to="/professional/manual">Manual</MenuLink>
            <MenuLink to="/notifications">Avisos</MenuLink>
          </>
        )}

        {isSupervisor && (
          <>
            <MenuLink to="/professional">Pacientes</MenuLink>
            <MenuLink to="/professional/alerts">Alertas</MenuLink>
            <MenuLink to="/professional/copilot">Copiloto</MenuLink>
            <MenuLink to="/professional/assignments">Asignaciones</MenuLink>
            <MenuLink to="/professional/audit">Auditoría</MenuLink>
            <MenuLink to="/professional/manual">Manual</MenuLink>
            <MenuLink to="/notifications">Avisos</MenuLink>
          </>
        )}

        {isAdmin && (
          <>
            <MenuLink to="/professional">Roster</MenuLink>
            <MenuLink to="/professional/users">Usuarios</MenuLink>
            <MenuLink to="/professional/assignments">Asignaciones</MenuLink>
            <MenuLink to="/professional/audit">Auditoría</MenuLink>
            <MenuLink to="/professional/manual">Manual</MenuLink>
            <MenuLink to="/notifications">Avisos</MenuLink>
          </>
        )}

        <MenuLink to="/account">Mi cuenta</MenuLink>
        <MenuLink to="/settings">Mis modelos</MenuLink>
      </div>

      <div className="navbar-user">
        <span>{user.display_name} · {ROLE_LABELS[role] || role}</span>
        <button onClick={logout}>Salir</button>
      </div>
    </nav>
  );
}
