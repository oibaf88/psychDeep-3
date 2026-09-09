import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type UserOut } from "../api";
import { useAuth } from "../auth/AuthContext";
import { newPasswordError } from "../auth/password";

function nameParts(user: UserOut) {
  if (user.first_name || user.last_name) {
    return { firstName: user.first_name || "", lastName: user.last_name || "" };
  }
  const [firstName = "", ...rest] = user.display_name.trim().split(/\s+/);
  return { firstName, lastName: rest.join(" ") };
}

export default function AccountPage() {
  const { user, updateUser, logout } = useAuth();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [locale, setLocale] = useState("es-ES");
  const [emailPassword, setEmailPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState<"" | "profile" | "password">("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    const parts = nameParts(user);
    setFirstName(parts.firstName);
    setLastName(parts.lastName);
    setEmail(user.email);
    setPhone(user.phone || "");
    setLocale(user.locale || "es-ES");
  }, [user]);

  if (!user) return null;

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy("profile");
    setError(null);
    setNotice(null);
    try {
      const updated = await api.patch<UserOut>("/api/v1/auth/me/profile", {
        first_name: firstName,
        last_name: lastName,
        email,
        phone,
        locale,
        // The server only reads this when the email actually changes.
        current_password: emailPassword || null,
      });
      updateUser(updated);
      setEmailPassword("");
      setNotice("Tus datos de cuenta se han actualizado.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setNotice(null);
    if (newPassword !== confirmPassword) {
      setError("La nueva contraseña y su confirmación no coinciden.");
      return;
    }
    const passwordError = newPasswordError(newPassword);
    if (passwordError) { setError(passwordError); return; }
    setBusy("password");
    try {
      await api.post("/api/v1/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      // Password rotation invalidates every JWT, including this browser.
      logout();
      navigate("/login", { replace: true, state: { notice: "Contraseña actualizada. Inicia sesión de nuevo." } });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="page">
      <h1>Mi cuenta</h1>
      <p className="subtitle">
        Datos personales de acceso para tu perfil. Esta pestaña no muestra ni modifica tu información clínica.
      </p>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="info" role="status">{notice}</p>}

      <section className="card">
        <h2>Datos de usuario</h2>
        <form className="auth-form" onSubmit={saveProfile}>
          <div className="account-grid">
            <label>
              Nombre
              <input value={firstName} onChange={(e) => setFirstName(e.target.value)} required maxLength={100} autoComplete="given-name" />
            </label>
            <label>
              Apellidos
              <input value={lastName} onChange={(e) => setLastName(e.target.value)} maxLength={150} autoComplete="family-name" />
            </label>
          </div>
          <label>
            Correo de acceso
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </label>
          <p className="meta">Para cambiar el correo, confirma la contraseña actual. El cambio queda registrado en auditoría.</p>
          <label>
            Contraseña actual para confirmar el correo (solo si lo cambias)
            <input type="password" value={emailPassword} onChange={(e) => setEmailPassword(e.target.value)} autoComplete="current-password" />
          </label>
          <div className="account-grid">
            <label>
              Teléfono
              <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={40} autoComplete="tel" />
            </label>
            <label>
              Idioma
              <select value={locale} onChange={(e) => setLocale(e.target.value)}>
                <option value="es-ES">Español</option>
                <option value="en">English</option>
              </select>
            </label>
          </div>
          <button type="submit" disabled={!!busy}>{busy === "profile" ? "Guardando…" : "Guardar datos"}</button>
        </form>
      </section>

      <section className="card">
        <h2>Cambiar contraseña</h2>
        <p className="meta">Usa al menos 12 caracteres y un máximo de 72 bytes. Al guardarla se cerrará la sesión en todos los dispositivos.</p>
        <form className="auth-form" onSubmit={savePassword}>
          <label>
            Contraseña actual
            <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required autoComplete="current-password" />
          </label>
          <label>
            Nueva contraseña
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={12} maxLength={256} autoComplete="new-password" />
          </label>
          <label>
            Confirmar nueva contraseña
            <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={12} maxLength={256} autoComplete="new-password" />
          </label>
          <button type="submit" disabled={!!busy}>{busy === "password" ? "Actualizando…" : "Cambiar contraseña"}</button>
        </form>
      </section>

      {user.role === "admin_clinical" && (
        <section className="card no-print">
          <h2>Opciones Administrativas</h2>
          <p className="meta">Exporta un informe de tu identidad y nivel de acceso actual.</p>
          <button type="button" className="btn-secondary" onClick={() => window.print()}>
            Exportar PDF de Permisos
          </button>
        </section>
      )}

      {user.role === "patient" && (
        <section className="card no-print">
          <h2>Historial Clínico</h2>
          <p className="meta">Para consultar tu historial clínico, gráficas y notas de sesión, dirígete a tu panel principal.</p>
          <button type="button" onClick={() => navigate("/")}>
            Ir a Mi Panel Clínico
          </button>
        </section>
      )}
    </div>
  );
}
