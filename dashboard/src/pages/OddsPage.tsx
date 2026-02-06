import { useState } from "react";
import { useLatestAnalysis, useOddsComparison } from "@/api/hooks";
import { OddsComparison } from "@/components/odds/OddsComparison";
import { OddsHeatmap } from "@/components/odds/OddsHeatmap";

export function OddsPage() {
  const { data: latest } = useLatestAnalysis();
  const [selectedGameId, setSelectedGameId] = useState<string>("");

  const { data: oddsData, isLoading } = useOddsComparison(selectedGameId);

  // Build game list from latest run's opportunities
  const gameIds = new Map<string, string>();
  if (latest?.opportunities) {
    for (const opp of latest.opportunities) {
      if (!gameIds.has(opp.game_id)) {
        gameIds.set(opp.game_id, opp.matchup);
      }
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Odds Comparison</h2>
        <p className="text-sm text-muted-foreground">
          Compare odds across sportsbooks for each game
        </p>
      </div>

      <div className="flex items-center gap-4">
        <label className="text-sm font-medium">Select Game</label>
        <select
          value={selectedGameId}
          onChange={(e) => setSelectedGameId(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm"
        >
          <option value="">Choose a game...</option>
          {[...gameIds.entries()].map(([id, matchup]) => (
            <option key={id} value={id}>
              {matchup}
            </option>
          ))}
        </select>
      </div>

      {!selectedGameId && (
        <div className="rounded-lg border bg-white p-12 text-center text-muted-foreground">
          {gameIds.size > 0
            ? "Select a game above to view odds comparison."
            : "No games available. Run an analysis first."}
        </div>
      )}

      {isLoading && (
        <div className="rounded-lg border bg-white p-12 text-center text-muted-foreground">
          Loading odds data...
        </div>
      )}

      {oddsData && (
        <div className="space-y-6">
          <OddsComparison data={oddsData} />
          <OddsHeatmap data={oddsData} />
        </div>
      )}
    </div>
  );
}
