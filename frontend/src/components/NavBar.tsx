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

interface MenuEntry {
  to: string;
  label: string;
  end?: boolean;
}

const ROLE_MENUS: Record<UserRole, MenuEntry[]> = {
  patient: [
    { to: "/", label: "Hoy", end: true },
    { to: "/trends", label: "Tendencias" },
    { to: "/wave", label: "Regular" },
    { to: "/diary", label: "Diario" },
    { to: "/safety-plan", label: "Plan" },
    { to: "/sharing", label: "Compartir" },
    { to: "/chat", label: "Chat" },
    { to: "/notifications", label: "Avisos" },
  ],
  therapist: [
    { to: "/professional", label: "Pacientes" },
    { to: "/professional/alerts", label: "Alertas" },
    { to: "/professional/copilot", label: "Copiloto" },
    { to: "/professional/assignments", label: "Asignaciones" },
    { to: "/professional/manual", label: "Manual" },
    { to: "/notifications", label: "Avisos" },
  ],
  supervisor: [
    { to: "/professional", label: "Pacientes" },
    { to: "/professional/alerts", label: "Alertas" },
    { to: "/professional/copilot", label: "Copiloto" },
    { to: "/professional/assignments", label: "Asignaciones" },
    { to: "/professional/audit", label: "Auditoría" },
    { to: "/professional/manual", label: "Manual" },
    { to: "/notifications", label: "Avisos" },
  ],
  admin_clinical: [
    { to: "/professional", label: "Roster" },
    { to: "/professional/users", label: "Usuarios" },
    { to: "/professional/assignments", label: "Asignaciones" },
    { to: "/professional/audit", label: "Auditoría" },
    { to: "/professional/manual", label: "Manual" },
    { to: "/notifications", label: "Avisos" },
  ],
};

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

  return (
    <nav className="navbar" aria-label="Navegación principal">
      <div className="navbar-brand">
        <PsychDeepLogo className="navbar-mark" />
        <span>PsychDeep</span>
      </div>

      <div className="navbar-links">
        {(ROLE_MENUS[role] ?? []).map((entry) => (
          <MenuLink key={entry.to} to={entry.to} end={entry.end}>
            {entry.label}
          </MenuLink>
        ))}

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
