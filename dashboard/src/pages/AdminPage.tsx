import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/auth/AuthContext";

type Tab = "users" | "metrics" | "audit";

interface AdminUser {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  email_verified: boolean;
  has_google: boolean;
  created_at: string;
}

interface SystemStats {
  total_users: number;
  verified_users: number;
  google_users: number;
  signups_today: number;
  signups_this_week: number;
}

interface AuditEntry {
  id: number;
  timestamp: string;
  admin_id: string;
  action: string;
  target_id: string | null;
  details: string | null;
}

function authHeaders(token: string | null) {
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function AdminPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState<Tab>("users");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <RunAnalysisButton token={token} />
      </div>

      <div className="flex gap-2 border-b">
        {(["users", "metrics", "audit"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "users" ? "Users" : t === "metrics" ? "Metrics" : "Audit Log"}
          </button>
        ))}
      </div>

      {tab === "users" && <UsersTab token={token} />}
      {tab === "metrics" && <MetricsTab token={token} />}
      {tab === "audit" && <AuditTab token={token} />}
    </div>
  );
}

function RunAnalysisButton({ token }: { token: string | null }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const run = async () => {
    setLoading(true);
    setMsg("");
    try {
      const res = await fetch("/api/admin/analysis/run", {
        method: "POST",
        headers: authHeaders(token),
      });
      if (res.ok) {
        const data = await res.json();
        setMsg(`Analysis started (${data.run_id})`);
      } else {
        setMsg("Failed to trigger analysis");
      }
    } catch {
      setMsg("Error triggering analysis");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      {msg && <span className="text-sm text-gray-600">{msg}</span>}
      <button
        onClick={run}
        disabled={loading}
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
      >
        {loading ? "Running..." : "Run Analysis"}
      </button>
    </div>
  );
}

function UsersTab({ token }: { token: string | null }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/users?limit=200", {
        headers: authHeaders(token),
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data.users);
        setTotal(data.total);
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const changeRole = async (userId: string, newRole: string) => {
    const res = await fetch(`/api/admin/users/${userId}/role`, {
      method: "PATCH",
      headers: authHeaders(token),
      body: JSON.stringify({ role: newRole }),
    });
    if (res.ok) fetchUsers();
  };

  const deleteUser = async (userId: string) => {
    const res = await fetch(`/api/admin/users/${userId}`, {
      method: "DELETE",
      headers: authHeaders(token),
    });
    if (res.ok) {
      setConfirmDelete(null);
      fetchUsers();
    }
  };

  if (loading) return <p className="text-gray-500">Loading users...</p>;

  return (
    <div className="overflow-x-auto">
      <p className="mb-3 text-sm text-gray-500">{total} users total</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="pb-2 pr-4">Email</th>
            <th className="pb-2 pr-4">Name</th>
            <th className="pb-2 pr-4">Role</th>
            <th className="pb-2 pr-4">Verified</th>
            <th className="pb-2 pr-4">Google</th>
            <th className="pb-2 pr-4">Joined</th>
            <th className="pb-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b">
              <td className="py-2 pr-4">{u.email}</td>
              <td className="py-2 pr-4">{u.display_name || "-"}</td>
              <td className="py-2 pr-4">
                <select
                  value={u.role}
                  onChange={(e) => changeRole(u.id, e.target.value)}
                  className="rounded border px-2 py-1 text-sm"
                >
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </td>
              <td className="py-2 pr-4">
                {u.email_verified ? (
                  <span className="text-green-600">Yes</span>
                ) : (
                  <span className="text-red-500">No</span>
                )}
              </td>
              <td className="py-2 pr-4">{u.has_google ? "Yes" : "No"}</td>
              <td className="py-2 pr-4">
                {new Date(u.created_at).toLocaleDateString()}
              </td>
              <td className="py-2">
                {confirmDelete === u.id ? (
                  <span className="flex gap-2">
                    <button
                      onClick={() => deleteUser(u.id)}
                      className="text-red-600 text-sm font-medium"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => setConfirmDelete(null)}
                      className="text-gray-500 text-sm"
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setConfirmDelete(u.id)}
                    className="text-red-500 text-sm hover:text-red-700"
                  >
                    Delete
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricsTab({ token }: { token: string | null }) {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/admin/stats", {
          headers: authHeaders(token),
        });
        if (res.ok) setStats(await res.json());
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  if (loading) return <p className="text-gray-500">Loading metrics...</p>;
  if (!stats) return <p className="text-red-500">Failed to load metrics</p>;

  const cards = [
    { label: "Total Users", value: stats.total_users },
    { label: "Verified", value: stats.verified_users },
    { label: "Google-linked", value: stats.google_users },
    { label: "Signups Today", value: stats.signups_today },
    { label: "Signups This Week", value: stats.signups_this_week },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-lg border bg-white p-4 text-center"
        >
          <p className="text-2xl font-bold">{c.value}</p>
          <p className="text-sm text-gray-500">{c.label}</p>
        </div>
      ))}
    </div>
  );
}

function AuditTab({ token }: { token: string | null }) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [skip, setSkip] = useState(0);
  const limit = 50;

  const fetchLog = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `/api/admin/audit-log?skip=${skip}&limit=${limit}`,
        { headers: authHeaders(token) }
      );
      if (res.ok) {
        const data = await res.json();
        setEntries(data.entries);
        setTotal(data.total);
      }
    } finally {
      setLoading(false);
    }
  }, [token, skip]);

  useEffect(() => {
    fetchLog();
  }, [fetchLog]);

  if (loading) return <p className="text-gray-500">Loading audit log...</p>;

  return (
    <div>
      <p className="mb-3 text-sm text-gray-500">{total} entries total</p>
      {entries.length === 0 ? (
        <p className="text-gray-400">No audit log entries yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="pb-2 pr-4">Time</th>
              <th className="pb-2 pr-4">Admin</th>
              <th className="pb-2 pr-4">Action</th>
              <th className="pb-2 pr-4">Target</th>
              <th className="pb-2">Details</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b">
                <td className="py-2 pr-4 whitespace-nowrap">
                  {new Date(e.timestamp).toLocaleString()}
                </td>
                <td className="py-2 pr-4 font-mono text-xs">
                  {e.admin_id.slice(0, 8)}...
                </td>
                <td className="py-2 pr-4">{e.action}</td>
                <td className="py-2 pr-4 font-mono text-xs">
                  {e.target_id ? `${e.target_id.slice(0, 8)}...` : "-"}
                </td>
                <td className="py-2 text-xs text-gray-600 max-w-xs truncate">
                  {e.details || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {total > limit && (
        <div className="mt-4 flex gap-2">
          <button
            disabled={skip === 0}
            onClick={() => setSkip(Math.max(0, skip - limit))}
            className="rounded border px-3 py-1 text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <button
            disabled={skip + limit >= total}
            onClick={() => setSkip(skip + limit)}
            className="rounded border px-3 py-1 text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
