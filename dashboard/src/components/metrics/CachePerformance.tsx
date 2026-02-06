import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { CacheMetrics } from "@/types";

interface CachePerformanceProps {
  data: CacheMetrics;
}

const COLORS = ["#16a34a", "#dc2626", "#f59e0b"];

export function CachePerformance({ data }: CachePerformanceProps) {
  const total = data.hits + data.misses + data.stale_hits;
  const chartData = [
    { name: "Hits", value: data.hits },
    { name: "Misses", value: data.misses },
    { name: "Stale", value: data.stale_hits },
  ].filter((d) => d.value > 0);

  return (
    <div className="rounded-lg border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold">Cache Performance</h3>

      {total > 0 ? (
        <div className="flex items-center gap-6">
          <ResponsiveContainer width={150} height={150}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={60}
                dataKey="value"
              >
                {chartData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>

          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-green-600" />
              <span>
                Hits: {data.hits} ({data.hit_rate}%)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-red-600" />
              <span>Misses: {data.misses}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-yellow-500" />
              <span>Stale: {data.stale_hits}</span>
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              Fresh hit rate: {data.fresh_hit_rate}%
            </div>
          </div>
        </div>
      ) : (
        <div className="py-8 text-center text-sm text-muted-foreground">
          No cache activity recorded yet.
        </div>
      )}
    </div>
  );
}
