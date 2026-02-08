import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface User {
  id: string;
  email: string;
  display_name: string | null;
  role: string | null;
}

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
  isLoading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthState | null>(null);

const TOKEN_KEY = "nba_dashboard_token";
const REFRESH_KEY = "nba_dashboard_refresh";
const USER_KEY = "nba_dashboard_user";

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1];
    const json = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function userFromToken(token: string): User | null {
  const payload = decodeJwtPayload(token);
  if (!payload || !payload.sub) return null;
  return {
    id: payload.sub as string,
    email: (payload.email as string) || "",
    display_name: (payload.display_name as string) || null,
    role: (payload.role as string) || null,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY)
  );
  const [refreshToken, setRefreshToken] = useState<string | null>(() =>
    localStorage.getItem(REFRESH_KEY)
  );
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem(USER_KEY);
    if (saved) {
      try { return JSON.parse(saved); } catch { return null; }
    }
    const t = localStorage.getItem(TOKEN_KEY);
    return t ? userFromToken(t) : null;
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const handleTokens = useCallback((accessToken: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_KEY, refresh);
    const u = userFromToken(accessToken);
    if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
    setToken(accessToken);
    setRefreshToken(refresh);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setRefreshToken(null);
    setUser(null);
  }, []);

  const login = useCallback(async (email: string, pass: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: pass }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const msg = body?.detail ?? `Login failed (${res.status})`;
        setError(msg);
        return;
      }

      const data = await res.json();
      handleTokens(data.access_token, data.refresh_token);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "";
      setError(
        message === "Failed to fetch"
          ? "Cannot reach server. Is the backend running?"
          : "Login failed. Check your credentials."
      );
    } finally {
      setIsLoading(false);
    }
  }, [handleTokens]);

  const loginWithGoogle = useCallback(async (idToken: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: idToken }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const msg = body?.detail ?? `Google sign-in failed (${res.status})`;
        setError(msg);
        return;
      }

      const data = await res.json();
      handleTokens(data.access_token, data.refresh_token);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "";
      setError(
        message === "Failed to fetch"
          ? "Cannot reach server. Is the backend running?"
          : "Google sign-in failed."
      );
    } finally {
      setIsLoading(false);
    }
  }, [handleTokens]);

  const value = useMemo<AuthState>(
    () => ({
      token,
      refreshToken,
      user,
      isAuthenticated: !!token,
      login,
      loginWithGoogle,
      logout,
      clearError,
      isLoading,
      error,
    }),
    [token, refreshToken, user, login, loginWithGoogle, logout, clearError, isLoading, error]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
