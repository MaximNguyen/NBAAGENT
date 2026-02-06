import type { ModelAccuracy } from "@/types";

interface ModelAccuracyChartProps {
  data: ModelAccuracy;
}

export function ModelAccuracyChart({ data }: ModelAccuracyChartProps) {
  const brierMax = 0.25; // Target threshold
  const brierPct = Math.min((data.brier_score / brierMax) * 100, 100);
  const brierGood = data.brier_score < brierMax;

  const calMax = 0.1;
  const calPct = Math.min((data.calibration_error / calMax) * 100, 100);
  const calGood = data.calibration_error < calMax;

  return (
    <div className="rounded-lg border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold">Model Accuracy</h3>

      <div className="space-y-6">
        <div>
          <div className="flex items-center justify-between text-sm">
            <span>Brier Score</span>
            <span className={`font-mono ${brierGood ? "text-green-600" : "text-red-600"}`}>
              {data.brier_score.toFixed(4)}
            </span>
          </div>
          <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-gray-100">
            <div
              className={`h-full rounded-full transition-all ${brierGood ? "bg-green-500" : "bg-red-500"}`}
              style={{ width: `${100 - brierPct}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Target: &lt; {brierMax} (lower is better)
          </p>
        </div>

        <div>
          <div className="flex items-center justify-between text-sm">
            <span>Calibration Error</span>
            <span className={`font-mono ${calGood ? "text-green-600" : "text-red-600"}`}>
              {data.calibration_error.toFixed(4)}
            </span>
          </div>
          <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-gray-100">
            <div
              className={`h-full rounded-full transition-all ${calGood ? "bg-green-500" : "bg-red-500"}`}
              style={{ width: `${100 - calPct}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Target: &lt; {calMax} (lower is better)
          </p>
        </div>

        {data.clv_pct != null && (
          <div className="flex items-center justify-between text-sm">
            <span>Closing Line Value</span>
            <span className={`font-mono ${data.clv_pct > 0 ? "text-green-600" : "text-red-600"}`}>
              {data.clv_pct > 0 ? "+" : ""}{data.clv_pct.toFixed(2)}%
            </span>
          </div>
        )}

        <div className="flex items-center justify-between text-sm">
          <span>Total Predictions</span>
          <span className="font-mono">{data.total_predictions}</span>
        </div>
      </div>
    </div>
  );
}
