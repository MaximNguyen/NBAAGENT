import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface AuthState {
  token: string | null;
  username: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthState | null>(null);

const TOKEN_KEY = "nba_dashboard_token";
const USER_KEY = "nba_dashboard_user";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY)
  );
  const [username, setUsername] = useState<string | null>(() =>
    localStorage.getItem(USER_KEY)
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUsername(null);
  }, []);

  const login = useCallback(async (user: string, pass: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user, password: pass }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const msg = body?.detail ?? `Login failed (${res.status})`;
        setError(msg);
        return;
      }

      const data: { token: string; username: string } = await res.json();
      localStorage.setItem(TOKEN_KEY, data.token);
      localStorage.setItem(USER_KEY, data.username);
      setToken(data.token);
      setUsername(data.username);
    } catch (err: any) {
      setError(
        err?.message === "Failed to fetch"
          ? "Cannot reach server. Is the backend running?"
          : "Login failed. Check your credentials."
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      token,
      username,
      isAuthenticated: !!token,
      login,
      logout,
      isLoading,
      error,
    }),
    [token, username, login, logout, isLoading, error]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
