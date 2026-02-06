import { useState } from "react";
import { usePerformance, useMonthlyROI, useModelAccuracy } from "@/api/hooks";
import { ROIChart } from "@/components/charts/ROIChart";
import { MonthlyROIBar } from "@/components/charts/MonthlyROIBar";
import { ModelAccuracyChart } from "@/components/charts/ModelAccuracyChart";
import { BankrollChart } from "@/components/charts/BankrollChart";

export function HistoryPage() {
  const [season, setSeason] = useState("2023-24");

  const { data: performance } = usePerformance(season);
  const { data: monthlyRoi } = useMonthlyROI(season);
  const { data: modelAccuracy } = useModelAccuracy(season);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Historical Performance</h2>
          <p className="text-sm text-muted-foreground">
            Backtest results and model performance metrics
          </p>
        </div>
        <select
          value={season}
          onChange={(e) => setSeason(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm"
        >
          <option value="2023-24">2023-24</option>
          <option value="2022-23">2022-23</option>
          <option value="2021-22">2021-22</option>
        </select>
      </div>

      {/* Performance Summary Cards */}
      {performance && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg border bg-white p-4">
            <div className="text-xs font-medium text-muted-foreground">
              Total Bets
            </div>
            <div className="mt-1 text-2xl font-bold">
              {performance.total_bets}
            </div>
          </div>
          <div className="rounded-lg border bg-white p-4">
            <div className="text-xs font-medium text-muted-foreground">
              Win Rate
            </div>
            <div className="mt-1 text-2xl font-bold">
              {(performance.win_rate * 100).toFixed(1)}%
            </div>
          </div>
          <div className="rounded-lg border bg-white p-4">
            <div className="text-xs font-medium text-muted-foreground">ROI</div>
            <div
              className={`mt-1 text-2xl font-bold ${
                performance.roi_pct >= 0 ? "text-green-600" : "text-red-600"
              }`}
            >
              {performance.roi_pct >= 0 ? "+" : ""}
              {performance.roi_pct.toFixed(1)}%
            </div>
          </div>
          <div className="rounded-lg border bg-white p-4">
            <div className="text-xs font-medium text-muted-foreground">
              Net Profit
            </div>
            <div
              className={`mt-1 text-2xl font-bold ${
                performance.net_profit >= 0 ? "text-green-600" : "text-red-600"
              }`}
            >
              ${performance.net_profit.toFixed(2)}
            </div>
          </div>
        </div>
      )}

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        {monthlyRoi && monthlyRoi.length > 0 && (
          <>
            <ROIChart data={monthlyRoi} />
            <MonthlyROIBar data={monthlyRoi} />
            <BankrollChart data={monthlyRoi} />
          </>
        )}
        {modelAccuracy && <ModelAccuracyChart data={modelAccuracy} />}
      </div>

      {!monthlyRoi?.length && !performance?.total_bets && (
        <div className="rounded-lg border bg-white p-12 text-center text-muted-foreground">
          No historical data available for {season}. Import game data to see
          backtest results.
        </div>
      )}
    </div>
  );
}
