import { FormEvent, useEffect, useState } from "react";
import { api, ROLE_LABELS, type UserRole } from "../api";
import { useAuth } from "../auth/AuthContext";

type ProvisionableRole = Exclude<UserRole, "patient">;

interface AdminUserOut {
  id: string;
  email: string;
  display_name: string;
  first_name?: string | null;
  last_name?: string | null;
  phone?: string | null;
  role: UserRole;
  locale: string;
  is_active: boolean;
  created_at: string;
  local_llm_approved?: boolean;
}

interface AdminUserPermissionsOut {
  user: AdminUserOut;
  permissions: string[];
  can_revoke: boolean;
  can_restore: boolean;
  local_llm_access: "manager" | "approved" | "pending";
  local_llm_usable: boolean;
  can_set_local_llm: boolean;
}

const LOCAL_LLM_LABEL: Record<AdminUserPermissionsOut["local_llm_access"], string> = {
  manager: "Autorizado por rol de administrador clínico",
  approved: "Autorizado por el administrador clínico",
  pending: "Pendiente de autorización",
};

const ALL_ROLES: UserRole[] = ["patient", "therapist", "supervisor", "admin_clinical"];
const PROVISIONABLE_ROLES: ProvisionableRole[] = ["therapist", "supervisor", "admin_clinical"];

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AdminUserOut[]>([]);
  const [selected, setSelected] = useState<AdminUserPermissionsOut | null>(null);
  const [draftRole, setDraftRole] = useState<UserRole>("patient");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [provisionRole, setProvisionRole] = useState<ProvisionableRole>("therapist");

  async function load() {
    setError(null);
    try {
      setUsers(await api.get<AdminUserOut[]>("/api/v1/admin/users"));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function selectUser(user: AdminUserOut) {
    setBusy(`select:${user.id}`);
    setError(null);
    setNotice(null);
    try {
      const document = await api.get<AdminUserPermissionsOut>(`/api/v1/admin/users/${user.id}/permissions`);
      setSelected(document);
      setDraftRole(document.user.role);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function provision(event: FormEvent) {
    event.preventDefault();
    setBusy("provision");
    setError(null);
    setNotice(null);
    try {
      const created = await api.post<AdminUserOut>("/api/v1/admin/users", {
        email,
        password,
        display_name: displayName,
        role: provisionRole,
      });
      setUsers((current) => [created, ...current]);
      setDisplayName("");
      setEmail("");
      setPassword("");
      setProvisionRole("therapist");
      setNotice(`Cuenta profesional creada para ${created.email}.`);
      await selectUser(created);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function saveRole() {
    if (!selected || draftRole === selected.user.role) return;
    if (selected.user.id === currentUser?.id) {
      setError("No puedes cambiar tu propio rol administrativo desde esta pantalla.");
      return;
    }
    if (!window.confirm(`Cambiar ${selected.user.email} a ${ROLE_LABELS[draftRole]}? Se cerrarán sus sesiones actuales.`)) return;

    setBusy("role");
    setError(null);
    setNotice(null);
    try {
      const updated = await api.put<AdminUserOut>(`/api/v1/admin/users/${selected.user.id}/role`, { role: draftRole });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      const document = await api.get<AdminUserPermissionsOut>(`/api/v1/admin/users/${updated.id}/permissions`);
      setSelected(document);
      setDraftRole(document.user.role);
      setNotice(`Rol actualizado: ${updated.email} → ${ROLE_LABELS[updated.role]}.`);
    } catch (e) {
      setDraftRole(selected.user.role);
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function changeAccess(action: "revoke" | "restore") {
    if (!selected) return;
    const verb = action === "revoke" ? "revocar" : "restaurar";
    if (!window.confirm(`${verb[0].toUpperCase()}${verb.slice(1)} el acceso de ${selected.user.email}?`)) return;
    setBusy(action);
    setError(null);
    setNotice(null);
    try {
      const document = await api.post<AdminUserPermissionsOut>(`/api/v1/admin/users/${selected.user.id}/${action}`);
      setSelected(document);
      setUsers((current) => current.map((item) => (item.id === document.user.id ? document.user : item)));
      setNotice(action === "revoke" ? "Acceso revocado y sesiones invalidadas." : "Acceso restaurado; la persona debe iniciar sesión de nuevo.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function setLocalLlmAccess(approved: boolean) {
    if (!selected) return;
    const verb = approved ? "autorizar el modelo local para" : "retirar la autorización del modelo local de";
    if (!window.confirm(`¿${verb[0].toUpperCase()}${verb.slice(1)} ${selected.user.email}?`)) return;
    setBusy("local-llm");
    setError(null);
    setNotice(null);
    try {
      const document = await api.put<AdminUserPermissionsOut>(`/api/v1/admin/users/${selected.user.id}/local-llm`, { approved });
      setSelected(document);
      setUsers((current) => current.map((item) => (item.id === document.user.id ? document.user : item)));
      setNotice(approved ? "Modelo local autorizado para esta cuenta." : "Autorización del modelo local retirada.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function printPermissions() {
    if (!selected) return;
    setBusy("print");
    setError(null);
    try {
      const document = await api.post<AdminUserPermissionsOut>(`/api/v1/admin/users/${selected.user.id}/permissions/print`);
      setSelected(document);
      window.print();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const normalizedQuery = query.trim().toLowerCase();
  const visibleUsers = normalizedQuery
    ? users.filter(
        (item) =>
          item.email.toLowerCase().includes(normalizedQuery) ||
          item.display_name.toLowerCase().includes(normalizedQuery) ||
          ROLE_LABELS[item.role].toLowerCase().includes(normalizedQuery),
      )
    : users;
  const selectedIsSelf = selected?.user.id === currentUser?.id;

  return (
    <div className="page">
      <h1>Gestión de usuarios</h1>
      <p className="subtitle">
        Selecciona una cuenta para ver únicamente sus opciones de acceso y su documento de permisos. No se muestra aquí ningún dato clínico.
      </p>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="info" role="status">{notice}</p>}

      <section className="card">
        <h2>Crear cuenta profesional</h2>
        <p className="meta">La contraseña inicial se guarda sólo como hash. Entrégala por un canal seguro y pide cambiarla en el primer acceso.</p>
        <form className="auth-form" onSubmit={provision}>
          <label>
            Nombre mostrado
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required maxLength={255} />
          </label>
          <label>
            Correo
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </label>
          <label>
            Contraseña inicial
            <input type="password" minLength={12} maxLength={256} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
          </label>
          <label>
            Perfil
            <select value={provisionRole} onChange={(e) => setProvisionRole(e.target.value as ProvisionableRole)}>
              {PROVISIONABLE_ROLES.map((role) => <option key={role} value={role}>{ROLE_LABELS[role]}</option>)}
            </select>
          </label>
          <button type="submit" disabled={busy === "provision"}>{busy === "provision" ? "Creando…" : "Crear cuenta profesional"}</button>
        </form>
      </section>

      <section className="admin-users-workspace" aria-label="Cuentas y permisos">
        <div className="card admin-user-list">
          <h2>Usuarios</h2>
          <label>
            Buscar
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nombre, correo o perfil" />
          </label>
          <div className="admin-user-list-items">
            {visibleUsers.map((item) => (
              <button
                type="button"
                key={item.id}
                className={selected?.user.id === item.id ? "admin-user-row is-selected" : "admin-user-row"}
                onClick={() => void selectUser(item)}
                disabled={busy === `select:${item.id}`}
              >
                <span><strong>{item.display_name}</strong><small>{ROLE_LABELS[item.role]}</small></span>
                <span className={item.is_active ? "status-active" : "status-revoked"}>{item.is_active ? "Activa" : "Revocada"}</span>
              </button>
            ))}
            {visibleUsers.length === 0 && <p className="info">No hay usuarios que coincidan con la búsqueda.</p>}
          </div>
        </div>

        <section className="card admin-user-options permissions-print" aria-live="polite">
          {!selected ? (
            <p className="meta">Elige una cuenta de la lista para ver sus opciones.</p>
          ) : (
            <>
              <div className="admin-user-options-heading">
                <div>
                  <p className="eyebrow">Cuenta seleccionada</p>
                  <h2>{selected.user.display_name}</h2>
                  <p>{selected.user.email}</p>
                </div>
                <span className={selected.user.is_active ? "status-active" : "status-revoked"}>{selected.user.is_active ? "Cuenta activa" : "Acceso revocado"}</span>
              </div>
              <p className="meta">Idioma: {selected.user.locale} · creada: {new Date(selected.user.created_at).toLocaleString()}</p>

              <h3>Permisos efectivos</h3>
              <ul className="permission-list">
                {selected.permissions.map((permission) => <li key={permission}>{permission}</li>)}
              </ul>

              <h3>Modelo local (LM Studio)</h3>
              <p className="meta">Estado: {LOCAL_LLM_LABEL[selected.local_llm_access]}</p>
              {selected.can_set_local_llm && (
                <div className="admin-user-actions no-print">
                  {selected.local_llm_access === "pending" ? (
                    <button type="button" disabled={busy !== null} onClick={() => void setLocalLlmAccess(true)}>
                      {busy === "local-llm" ? "Guardando…" : "Autorizar modelo local"}
                    </button>
                  ) : (
                    <button type="button" className="btn-secondary" disabled={busy !== null} onClick={() => void setLocalLlmAccess(false)}>
                      {busy === "local-llm" ? "Guardando…" : "Retirar autorización"}
                    </button>
                  )}
                </div>
              )}
              {selected.user.role === "admin_clinical" && (
                <p className="meta no-print">Esta cuenta usa el modelo local por su rol. No requiere una autorización adicional.</p>
              )}

              <div className="admin-user-actions no-print">
                <label>
                  Perfil de acceso
                  <select value={draftRole} disabled={selectedIsSelf || busy !== null} onChange={(e) => setDraftRole(e.target.value as UserRole)}>
                    {ALL_ROLES.map((role) => <option key={role} value={role}>{ROLE_LABELS[role]}</option>)}
                  </select>
                </label>
                <button type="button" disabled={selectedIsSelf || busy !== null || draftRole === selected.user.role} onClick={() => void saveRole()}>
                  {busy === "role" ? "Guardando…" : "Guardar perfil"}
                </button>
                <button type="button" className="btn-secondary" disabled={busy !== null} onClick={() => void printPermissions()}>
                  {busy === "print" ? "Preparando…" : "Imprimir / guardar PDF"}
                </button>
                {selected.can_revoke && <button type="button" className="btn-danger" disabled={busy !== null} onClick={() => void changeAccess("revoke")}>Revocar acceso</button>}
                {selected.can_restore && <button type="button" disabled={busy !== null} onClick={() => void changeAccess("restore")}>Restaurar acceso</button>}
              </div>
              {selectedIsSelf && <p className="meta no-print">Tu propio acceso y rol están protegidos para evitar un bloqueo administrativo accidental.</p>}
              <p className="print-only meta">Documento generado desde PsychDeep. No contiene datos clínicos ni contraseñas.</p>
            </>
          )}
        </section>
      </section>
    </div>
  );
}
