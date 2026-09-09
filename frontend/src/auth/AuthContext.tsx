import { createContext, useContext, useEffect, useRef, useState, ReactNode } from "react";
import { api, ApiError, getToken, setToken, UserOut } from "../api";

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  sessionError: string | null;
  retrySession: () => Promise<void>;
  login: (email: string, password: string) => Promise<UserOut>;
  register: (email: string, password: string, displayName: string) => Promise<UserOut>;
  updateUser: (user: UserOut) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const sessionAttempt = useRef(0);

  async function retrySession() {
    const attempt = ++sessionAttempt.current;
    const token = getToken();
    setSessionError(null);
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const restored = await api.get<UserOut>("/api/v1/auth/me");
      if (attempt === sessionAttempt.current && token === getToken()) setUser(restored);
    } catch (error) {
      if (attempt !== sessionAttempt.current || token !== getToken()) return;
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        setToken(null);
        setUser(null);
      } else {
        setSessionError((error as Error).message);
      }
    } finally {
      if (attempt === sessionAttempt.current) setLoading(false);
    }
  }

  useEffect(() => {
    void retrySession();
    return () => { sessionAttempt.current += 1; };
  }, []);

  async function login(email: string, password: string): Promise<UserOut> {
    const res = await api.post<{ access_token: string; user: UserOut }>("/api/v1/auth/login", { email, password });
    sessionAttempt.current += 1;
    setSessionError(null);
    setLoading(false);
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  }

  async function register(email: string, password: string, displayName: string): Promise<UserOut> {
    const res = await api.post<{ access_token: string; user: UserOut }>("/api/v1/auth/register", {
      email,
      password,
      display_name: displayName,
    });
    sessionAttempt.current += 1;
    setSessionError(null);
    setLoading(false);
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  }

  function logout() {
    sessionAttempt.current += 1;
    setSessionError(null);
    setLoading(false);
    setToken(null);
    setUser(null);
  }

  function updateUser(nextUser: UserOut) {
    setUser(nextUser);
  }

  return <AuthContext.Provider value={{ user, loading, sessionError, retrySession, login, register, updateUser, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
