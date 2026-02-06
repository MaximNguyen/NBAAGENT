import { useState } from "react";
import { AnalysisPanel } from "@/components/analysis/AnalysisPanel";
import { AnalysisProgress } from "@/components/analysis/AnalysisProgress";
import { OpportunitiesTable } from "@/components/opportunities/OpportunitiesTable";
import { useAnalysisStatus } from "@/api/hooks";

export function AnalysisPage() {
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const { data: runStatus } = useAnalysisStatus(activeRunId);

  const isComplete = runStatus?.status === "completed";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Run Analysis</h2>
        <p className="text-sm text-muted-foreground">
          Trigger a new analysis pipeline and watch the agents work
        </p>
      </div>

      <AnalysisPanel onRunStarted={setActiveRunId} />

      {activeRunId && (
        <AnalysisProgress
          runId={activeRunId}
          onComplete={() => {
            // Trigger a re-fetch of the status
          }}
        />
      )}

      {isComplete && runStatus.opportunities.length > 0 && (
        <div>
          <h3 className="mb-3 text-lg font-semibold">Results</h3>
          <OpportunitiesTable opportunities={runStatus.opportunities} />
        </div>
      )}

      {isComplete && runStatus.recommendation && (
        <div className="rounded-lg border bg-white p-4">
          <h3 className="text-sm font-semibold">Recommendation</h3>
          <pre className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground font-sans">
            {runStatus.recommendation.replace(/\[\/?\w+[^\]]*\]/g, "")}
          </pre>
        </div>
      )}

      {isComplete && runStatus.errors.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <h3 className="text-sm font-semibold text-red-800">
            Errors ({runStatus.errors.length})
          </h3>
          <ul className="mt-2 space-y-1">
            {runStatus.errors.map((err, i) => (
              <li key={i} className="text-sm text-red-700">
                {err}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
