import { Check, Loader2, AlertCircle } from "lucide-react";
import { useAnalysisWebSocket } from "@/api/websocket";
import { formatDuration } from "@/lib/utils";

const PIPELINE_STEPS = [
  { key: "lines_agent", label: "Lines Agent", desc: "Fetching odds from sportsbooks" },
  { key: "stats_agent", label: "Stats Agent", desc: "Gathering team stats & injuries" },
  { key: "analysis_agent", label: "Analysis Agent", desc: "Calculating EV & probabilities" },
  { key: "communication_agent", label: "Communication Agent", desc: "Formatting results" },
];

interface AnalysisProgressProps {
  runId: string;
  onComplete?: () => void;
}

export function AnalysisProgress({ runId, onComplete }: AnalysisProgressProps) {
  const ws = useAnalysisWebSocket({
    runId,
    onComplete: () => onComplete?.(),
  });

  return (
    <div className="rounded-lg border bg-white p-6">
      <h3 className="text-sm font-semibold">
        Analysis Progress
        {ws.isComplete && (
          <span className="ml-2 text-green-600">
            &middot; Complete ({ws.opportunities.length} opportunities)
          </span>
        )}
        {ws.error && (
          <span className="ml-2 text-red-600">&middot; Error</span>
        )}
      </h3>

      <div className="mt-4 space-y-3">
        {PIPELINE_STEPS.map((step) => {
          const completed = ws.completedSteps.find(
            (s) => s.agent === step.key
          );
          const isCurrent = ws.currentStep === step.key;

          return (
            <div key={step.key} className="flex items-center gap-3">
              <div className="flex h-6 w-6 items-center justify-center">
                {completed ? (
                  <Check className="h-5 w-5 text-green-600" />
                ) : isCurrent ? (
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                ) : (
                  <div className="h-3 w-3 rounded-full bg-gray-200" />
                )}
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium">{step.label}</div>
                <div className="text-xs text-muted-foreground">{step.desc}</div>
              </div>
              {completed && (
                <span className="text-xs text-muted-foreground">
                  {formatDuration(completed.duration_ms)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {ws.error && (
        <div className="mt-4 flex items-center gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" />
          {ws.error}
        </div>
      )}
    </div>
  );
}
