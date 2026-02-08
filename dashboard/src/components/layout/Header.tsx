import { LogOut } from "lucide-react";
import { useHealth } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";

export function Header() {
  const { data: health } = useHealth();
  const { user, logout } = useAuth();

  const displayLabel = user?.display_name || user?.email || "User";

  return (
    <header className="flex h-16 items-center justify-between border-b bg-white px-6">
      <h1 className="text-xl font-semibold text-gray-900">
        NBA Betting Dashboard
      </h1>
      <div className="flex items-center gap-4">
        {health && (
          <div className="flex items-center gap-2 text-sm">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                health.status === "ok" ? "bg-green-500" : "bg-yellow-500"
              )}
            />
            <span className="text-muted-foreground">
              v{health.version} &middot; {health.status}
            </span>
          </div>
        )}
        <div className="flex items-center gap-3 border-l pl-4">
          <span className="text-sm text-muted-foreground">{displayLabel}</span>
          <button
            onClick={logout}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-gray-100 hover:text-gray-900"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}
