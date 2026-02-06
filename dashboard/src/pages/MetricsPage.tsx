import { useSportsbookMetrics, useCacheMetrics, useHealth } from "@/api/hooks";
import { SportsbookCoverage } from "@/components/metrics/SportsbookCoverage";
import { CachePerformance } from "@/components/metrics/CachePerformance";

export function MetricsPage() {
  const { data: sportsbookData } = useSportsbookMetrics();
  const { data: cacheData } = useCacheMetrics();
  const { data: health } = useHealth();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">System Metrics</h2>
        <p className="text-sm text-muted-foreground">
          Sportsbook coverage, cache performance, and system health
        </p>
      </div>

      {/* Health Status */}
      {health && (
        <div className="rounded-lg border bg-white p-4">
          <h3 className="text-sm font-semibold">System Health</h3>
          <div className="mt-3 grid grid-cols-3 gap-4">
            <div>
              <span className="text-xs text-muted-foreground">Status</span>
              <div className="mt-1 flex items-center gap-2">
                <span
                  className={`h-2 w-2 rounded-full ${
                    health.status === "ok" ? "bg-green-500" : "bg-yellow-500"
                  }`}
                />
                <span className="text-sm font-medium">{health.status}</span>
              </div>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Version</span>
              <div className="mt-1 text-sm font-medium">{health.version}</div>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Timestamp</span>
              <div className="mt-1 text-sm font-medium">
                {new Date(health.timestamp).toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Sportsbook Coverage */}
        <div className="lg:col-span-2">
          <SportsbookCoverage data={sportsbookData ?? []} />
        </div>

        {/* Cache Performance */}
        {cacheData && <CachePerformance data={cacheData} />}
      </div>
    </div>
  );
}
