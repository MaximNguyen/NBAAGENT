import { useState, useEffect, useCallback, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

export function RegisterPage() {
  const { loginWithGoogle, isLoading, error, clearError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleGoogleCallback = useCallback(
    (response: { credential: string }) => {
      loginWithGoogle(response.credential);
    },
    [loginWithGoogle]
  );

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => {
      window.google?.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleCallback,
      });
      const btnEl = document.getElementById("google-signup-btn");
      if (btnEl) {
        window.google?.accounts.id.renderButton(btnEl, {
          theme: "outline",
          size: "large",
          width: "100%",
          text: "signup_with",
        });
      }
    };
    document.body.appendChild(script);

    return () => {
      document.body.removeChild(script);
    };
  }, [handleGoogleCallback]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          display_name: displayName || undefined,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setSubmitError(body?.detail ?? `Registration failed (${res.status})`);
        return;
      }

      setSubmitted(true);
    } catch {
      setSubmitError("Cannot reach server. Is the backend running?");
    }
  };

  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="w-full max-w-sm">
          <div className="rounded-xl border bg-white p-8 shadow-sm text-center">
            <div className="mb-4 flex justify-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-600 text-xl">
                &#10003;
              </div>
            </div>
            <h2 className="text-lg font-semibold">Check your email</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              We sent a verification link to <strong>{email}</strong>. Click the
              link to verify your account, then come back to sign in.
            </p>
            <Link
              to="/login"
              className="mt-6 inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90"
            >
              Go to Login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm">
        <div className="rounded-xl border bg-white p-8 shadow-sm">
          {/* Logo */}
          <div className="mb-6 flex flex-col items-center gap-2">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-white text-lg font-bold">
              EV
            </div>
            <h1 className="text-xl font-semibold">Create Account</h1>
            <p className="text-sm text-muted-foreground">
              Register to access the dashboard
            </p>
          </div>

          {/* Error */}
          {(submitError || error) && (
            <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {submitError || error}
              <button
                onClick={() => {
                  setSubmitError(null);
                  clearError();
                }}
                className="ml-2 text-red-500 hover:text-red-700"
              >
                x
              </button>
            </div>
          )}

          {/* Google Sign-Up */}
          {GOOGLE_CLIENT_ID && (
            <>
              <div id="google-signup-btn" className="mb-4 flex justify-center" />
              <div className="mb-4 flex items-center gap-3">
                <div className="h-px flex-1 bg-gray-200" />
                <span className="text-xs text-muted-foreground">or</span>
                <div className="h-px flex-1 bg-gray-200" />
              </div>
            </>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="displayName" className="mb-1 block text-sm font-medium">
                Display Name (optional)
              </label>
              <input
                id="displayName"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="Your name"
              />
            </div>

            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
                className="w-full rounded-md border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-medium">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
                minLength={8}
                className="w-full rounded-md border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="Min 8 characters"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading || !email || !password || password.length < 8}
              className="w-full rounded-md bg-primary py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
            >
              {isLoading ? "Creating account..." : "Create Account"}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link to="/login" className="text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
