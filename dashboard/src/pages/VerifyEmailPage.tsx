import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    token ? "loading" : "error"
  );
  const [message, setMessage] = useState(
    token ? "Verifying your email..." : "No verification token provided."
  );

  useEffect(() => {
    if (!token) return;

    (async () => {
      try {
        const res = await fetch("/api/auth/verify-email", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });

        const body = await res.json().catch(() => null);

        if (res.ok) {
          setStatus("success");
          setMessage(body?.message ?? "Email verified successfully!");
        } else {
          setStatus("error");
          setMessage(body?.detail ?? "Verification failed.");
        }
      } catch {
        setStatus("error");
        setMessage("Cannot reach server. Please try again later.");
      }
    })();
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm">
        <div className="rounded-xl border bg-white p-8 shadow-sm text-center">
          <div className="mb-4 flex justify-center">
            {status === "loading" && (
              <div className="h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-primary" />
            )}
            {status === "success" && (
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-600 text-xl">
                &#10003;
              </div>
            )}
            {status === "error" && (
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600 text-xl">
                &#10007;
              </div>
            )}
          </div>

          <h2 className="text-lg font-semibold">
            {status === "loading" && "Verifying..."}
            {status === "success" && "Email Verified"}
            {status === "error" && "Verification Failed"}
          </h2>

          <p className="mt-2 text-sm text-muted-foreground">{message}</p>

          {status !== "loading" && (
            <Link
              to="/login"
              className="mt-6 inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90"
            >
              Go to Login
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
