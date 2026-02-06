import { useState } from "react";
import { Play } from "lucide-react";
import { useTriggerAnalysis } from "@/api/hooks";

interface AnalysisPanelProps {
  onRunStarted: (runId: string) => void;
}

export function AnalysisPanel({ onRunStarted }: AnalysisPanelProps) {
  const [query, setQuery] = useState("find best bets tonight");
  const [minEv, setMinEv] = useState<string>("");
  const [confidence, setConfidence] = useState<string>("");
  const [limit, setLimit] = useState<string>("10");

  const triggerMutation = useTriggerAnalysis();

  const handleRun = () => {
    triggerMutation.mutate(
      {
        query,
        min_ev: minEv ? parseFloat(minEv) / 100 : undefined,
        confidence: confidence || undefined,
        limit: limit ? parseInt(limit) : undefined,
      },
      {
        onSuccess: (data) => {
          onRunStarted(data.run_id);
        },
      }
    );
  };

  return (
    <div className="rounded-lg border bg-white p-6">
      <h2 className="text-lg font-semibold">Run Analysis</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Enter a query to analyze NBA betting opportunities
      </p>

      <div className="mt-4 space-y-4">
        <div>
          <label className="text-sm font-medium">Query</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='e.g., "best bets tonight", "celtics vs lakers"'
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          />
        </div>

        <div className="flex gap-4">
          <div className="flex-1">
            <label className="text-sm font-medium">Min EV %</label>
            <input
              type="number"
              value={minEv}
              onChange={(e) => setMinEv(e.target.value)}
              placeholder="2"
              className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
            />
          </div>
          <div className="flex-1">
            <label className="text-sm font-medium">Confidence</label>
            <select
              value={confidence}
              onChange={(e) => setConfidence(e.target.value)}
              className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
            >
              <option value="">Any</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="text-sm font-medium">Limit</label>
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              placeholder="10"
              className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
            />
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={triggerMutation.isPending || !query.trim()}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {triggerMutation.isPending ? "Starting..." : "Run Analysis"}
        </button>
      </div>
    </div>
  );
}
