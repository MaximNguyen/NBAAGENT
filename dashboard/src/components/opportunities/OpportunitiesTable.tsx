import { useState } from "react";
import type { Opportunity } from "@/types";
import { toAmericanOdds, formatEV, formatProb, confidenceColor } from "@/lib/utils";
import { OpportunityDetail } from "./OpportunityDetail";

interface OpportunitiesTableProps {
  opportunities: Opportunity[];
}

export function OpportunitiesTable({ opportunities }: OpportunitiesTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (opportunities.length === 0) {
    return (
      <div className="rounded-lg border bg-white p-8 text-center text-muted-foreground">
        No opportunities found. Run an analysis or adjust your filters.
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-white">
      <table className="w-full">
        <thead>
          <tr className="border-b text-left text-xs font-medium text-muted-foreground">
            <th className="px-4 py-3">#</th>
            <th className="px-4 py-3">Bet</th>
            <th className="px-4 py-3">Odds</th>
            <th className="px-4 py-3">EV%</th>
            <th className="px-4 py-3">Confidence</th>
            <th className="px-4 py-3">Book</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((opp, i) => {
            const key = `${opp.game_id}-${opp.outcome}-${opp.bookmaker}`;
            const isExpanded = expandedId === key;
            return (
              <>
                <tr
                  key={key}
                  onClick={() => setExpandedId(isExpanded ? null : key)}
                  className="cursor-pointer border-b transition-colors hover:bg-gray-50"
                >
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {i + 1}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium">{opp.outcome}</div>
                    <div className="text-xs text-muted-foreground">
                      {opp.matchup} &middot; {opp.market}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-sm">
                    {toAmericanOdds(opp.market_odds)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`font-mono text-sm font-semibold ${
                        opp.ev_pct >= 0 ? "text-green-600" : "text-red-600"
                      }`}
                    >
                      {formatEV(opp.ev_pct)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${confidenceColor(
                        opp.confidence
                      )}`}
                    >
                      {opp.confidence}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">{opp.bookmaker}</td>
                </tr>
                {isExpanded && (
                  <tr key={`${key}-detail`}>
                    <td colSpan={6} className="bg-gray-50 px-4 py-4">
                      <OpportunityDetail opportunity={opp} />
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
