import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { homePathForRole } from "../api";
import { useAuth } from "../auth/AuthContext";
import { newPasswordError } from "../auth/password";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    const passwordError = newPasswordError(password);
    if (passwordError) { setError(passwordError); return; }
    if (!displayName.trim()) { setError("Escribe tu nombre."); return; }
    setBusy(true);
    try {
      const user = await register(email.trim(), password, displayName.trim());
      navigate(homePathForRole(user.role), { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <h1>Crear cuenta</h1>
      <form onSubmit={onSubmit} className="auth-form">
        <label>
          Nombre
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required maxLength={255} autoComplete="name" />
        </label>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </label>
        <label>
          Contraseña (mínimo 12 caracteres)
          <input type="password" minLength={12} maxLength={256} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
        </label>
        <p className="info">
          El registro publico crea cuentas de paciente. Las cuentas profesionales se provisionan de forma interna.
        </p>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Creando..." : "Crear cuenta"}
        </button>
      </form>
      <p>
        <Link to="/login">Volver a entrar</Link>
      </p>
    </div>
  );
}
