import { Navigate } from "react-router-dom";
import { ReactNode } from "react";
import { homePathForRole, UserRole } from "../api";
import { useAuth } from "../auth/AuthContext";
import PsychDeepLoader from "./PsychDeepLoader";

export default function ProtectedRoute({
  children,
  professionalOnly = false,
  patientOnly = false,
  roles,
}: {
  children: ReactNode;
  professionalOnly?: boolean;
  patientOnly?: boolean;
  roles?: UserRole[];
}) {
  const { user, loading, sessionError, retrySession } = useAuth();

  if (loading) return <div className="loading"><PsychDeepLoader size="md" label="Cargando PsychDeep…" /></div>;
  if (sessionError) return (
    <div className="page">
      <h1>No se pudo comprobar tu sesión</h1>
      <p className="error" role="alert">{sessionError}</p>
      <button type="button" onClick={() => void retrySession()}>Reintentar conexión</button>
    </div>
  );
  if (!user) return <Navigate to="/login" replace />;
  if (professionalOnly && user.role === "patient") return <Navigate to="/" replace />;
  if (patientOnly && user.role !== "patient") return <Navigate to="/professional" replace />;
  if (roles && !roles.includes(user.role as UserRole)) {
    return <Navigate to={homePathForRole(user.role)} replace />;
  }

  return <>{children}</>;
}
