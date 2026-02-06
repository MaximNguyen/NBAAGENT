import { useState } from "react";
import { TrendingUp, Target, BarChart3, Clock } from "lucide-react";
import { useOpportunities, useLatestAnalysis } from "@/api/hooks";
import { OpportunitiesTable } from "@/components/opportunities/OpportunitiesTable";
import { FilterBar } from "@/components/opportunities/FilterBar";
import { formatEV, formatDuration } from "@/lib/utils";
import type { OpportunityFilters } from "@/api/client";

export function DashboardPage() {
  const [filters, setFilters] = useState<OpportunityFilters>({});
  const { data: oppsData } = useOpportunities(filters);
  const { data: latest } = useLatestAnalysis();

  const opportunities = oppsData?.opportunities ?? [];

  // Summary stats
  const bestEv = opportunities.length > 0
    ? Math.max(...opportunities.map((o) => o.ev_pct))
    : 0;
  const avgConfidence = opportunities.length > 0
    ? opportunities.filter((o) => o.confidence === "high").length / opportunities.length
    : 0;

  const cards = [
    {
      label: "Total Opportunities",
      value: opportunities.length,
      icon: TrendingUp,
      color: "text-blue-600",
    },
    {
      label: "Best EV",
      value: bestEv > 0 ? formatEV(bestEv) : "-",
      icon: Target,
      color: "text-green-600",
    },
    {
      label: "High Confidence %",
      value: opportunities.length > 0 ? `${(avgConfidence * 100).toFixed(0)}%` : "-",
      icon: BarChart3,
      color: "text-purple-600",
    },
    {
      label: "Last Run",
      value:
        latest?.duration_ms != null
          ? formatDuration(latest.duration_ms)
          : "-",
      icon: Clock,
      color: "text-orange-600",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">+EV Opportunities</h2>
        <p className="text-sm text-muted-foreground">
          Positive expected value betting opportunities from the latest analysis
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {cards.map((card) => (
          <div
            key={card.label}
            className="rounded-lg border bg-white p-4"
          >
            <div className="flex items-center gap-2">
              <card.icon className={`h-4 w-4 ${card.color}`} />
              <span className="text-xs font-medium text-muted-foreground">
                {card.label}
              </span>
            </div>
            <div className="mt-2 text-2xl font-bold">{card.value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <FilterBar onFilterChange={setFilters} />

      {/* Table */}
      <OpportunitiesTable opportunities={opportunities} />
    </div>
  );
}
