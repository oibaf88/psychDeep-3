import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { homePathForRole } from "../api";
import { useAuth } from "../auth/AuthContext";
import PsychDeepLogo from "../components/PsychDeepLogo";

const SHOW_LOCAL_DEMO = import.meta.env.DEV;
const DEMO_ACCOUNTS = [
  { role: "Paciente", email: "patient@demo.psychapp.example.com" },
  { role: "Terapeuta", email: "therapist@demo.psychapp.example.com" },
  { role: "Supervisor", email: "supervisor@demo.psychapp.example.com" },
  { role: "Admin clinico", email: "admin@demo.psychapp.example.com" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const notice = typeof location.state?.notice === "string" ? location.state.notice : null;
  const [email, setEmail] = useState(SHOW_LOCAL_DEMO ? "patient@demo.psychapp.example.com" : "");
  const [password, setPassword] = useState(SHOW_LOCAL_DEMO ? "DemoPass123!" : "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const user = await login(email.trim(), password);
      navigate(homePathForRole(user.role), { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-brand" aria-hidden="true">
        <PsychDeepLogo className="auth-brand__logo" />
      </div>
      <h1>PsychDeep</h1>
      <p className="subtitle">
        Herramienta de autorregulacion y autoconciencia. No es un dispositivo medico ni sustituye a tu equipo de
        tratamiento.
      </p>
      <form onSubmit={onSubmit} className="auth-form">
        {notice && <p className="info" role="status">{notice}</p>}
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
        </label>
        <label>
          Contrasena
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Entrando..." : "Entrar"}
        </button>
      </form>
      <p>
        No tienes cuenta? <Link to="/register">Registrate</Link>
      </p>
      {SHOW_LOCAL_DEMO && (
        <div className="demo-hint">
          <p>
            Cuentas demo (contrasena <code>DemoPass123!</code>) - clic para rellenar:
          </p>
          <ul>
            {DEMO_ACCOUNTS.map((d) => (
              <li key={d.email}>
                <button
                  type="button"
                  className="linkish"
                  onClick={() => {
                    setEmail(d.email);
                    setPassword("DemoPass123!");
                  }}
                >
                  {d.role}
                </button>
                : {d.email}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
