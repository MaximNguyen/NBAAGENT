import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Play,
  History,
  BarChart3,
  Activity,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/auth/AuthContext";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/dashboard/analysis", label: "Analysis", icon: Play },
  { to: "/dashboard/history", label: "History", icon: History },
  { to: "/dashboard/odds", label: "Odds", icon: BarChart3 },
  { to: "/dashboard/metrics", label: "Metrics", icon: Activity },
];

export function Sidebar() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <aside className="flex w-64 flex-col border-r bg-white">
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-white font-bold text-sm">
          EV
        </div>
        <span className="text-lg font-semibold">NBA Betting</span>
      </div>
      <nav className="flex-1 space-y-1 p-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/dashboard"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </NavLink>
        ))}
        {isAdmin && (
          <NavLink
            to="/dashboard/admin"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              )
            }
          >
            <Shield className="h-5 w-5" />
            Admin
          </NavLink>
        )}
      </nav>
    </aside>
  );
}
