import type { Opportunity } from "@/types";
import { formatProb, formatEV, toAmericanOdds } from "@/lib/utils";

interface OpportunityDetailProps {
  opportunity: Opportunity;
}

export function OpportunityDetail({ opportunity: opp }: OpportunityDetailProps) {
  return (
    <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
      <div>
        <h4 className="text-xs font-medium text-muted-foreground">
          EV Breakdown
        </h4>
        <div className="mt-2 space-y-1 text-sm">
          <div className="flex justify-between">
            <span>Our Probability</span>
            <span className="font-mono">{formatProb(opp.our_prob)}</span>
          </div>
          <div className="flex justify-between">
            <span>Fair Odds</span>
            <span className="font-mono">{toAmericanOdds(opp.fair_odds)}</span>
          </div>
          <div className="flex justify-between">
            <span>Market Odds</span>
            <span className="font-mono">
              {toAmericanOdds(opp.market_odds)}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Kelly %</span>
            <span className="font-mono">
              {(opp.kelly_bet_pct * 100).toFixed(2)}%
            </span>
          </div>
        </div>
      </div>

      {opp.ml_prob != null && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground">
            ML Model
          </h4>
          <div className="mt-2 space-y-1 text-sm">
            <div className="flex justify-between">
              <span>ML Probability</span>
              <span className="font-mono">{formatProb(opp.ml_prob)}</span>
            </div>
            {opp.ml_explanation && (
              <p className="mt-1 text-xs text-muted-foreground">
                {opp.ml_explanation}
              </p>
            )}
          </div>
        </div>
      )}

      {opp.llm_insight && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground">
            Claude Insight
          </h4>
          <p className="mt-2 text-sm">{opp.llm_insight}</p>
        </div>
      )}

      <div>
        <h4 className="text-xs font-medium text-muted-foreground">
          Edge Signals
        </h4>
        <div className="mt-2 space-y-1 text-sm">
          {opp.sharp_edge != null && (
            <div className="flex justify-between">
              <span>Sharp Edge</span>
              <span className="font-mono">{formatEV(opp.sharp_edge)}</span>
            </div>
          )}
          {opp.rlm_signal && (
            <div className="flex justify-between">
              <span>RLM Signal</span>
              <span>{opp.rlm_signal}</span>
            </div>
          )}
          {opp.sharp_edge == null && !opp.rlm_signal && (
            <span className="text-muted-foreground">No signals</span>
          )}
        </div>
      </div>
    </div>
  );
}
