import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-white font-bold text-sm">
              EV
            </div>
            <span className="text-lg font-semibold">SportAgent</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="rounded-md px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Login
            </Link>
            <Link
              to="/register"
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90"
            >
              Register
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main className="mx-auto max-w-6xl px-6 py-24 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          NBA +EV Betting Analytics
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-gray-600">
          Find positive expected value betting opportunities with AI-powered
          analysis, real-time odds comparison, and ML probability models.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          <Link
            to="/register"
            className="rounded-md bg-primary px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-primary/90"
          >
            Get Started
          </Link>
          <Link
            to="/login"
            className="rounded-md border px-6 py-3 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
          >
            Sign In
          </Link>
        </div>
      </main>
    </div>
  );
}
