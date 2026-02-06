import type { OddsComparison as OddsComparisonType } from "@/types";
import { toAmericanOdds } from "@/lib/utils";

interface OddsComparisonProps {
  data: OddsComparisonType;
}

export function OddsComparison({ data }: OddsComparisonProps) {
  // Build matrix: rows=outcomes, cols=bookmakers
  const bookmakers = [...new Set(data.outcomes.map((o) => o.bookmaker))];
  const outcomeNames = [...new Set(data.outcomes.map((o) => o.outcome))];

  const getOdds = (outcome: string, bookmaker: string) =>
    data.outcomes.find(
      (o) => o.outcome === outcome && o.bookmaker === bookmaker
    );

  const bestForOutcome = (outcome: string) => {
    const matching = data.outcomes.filter((o) => o.outcome === outcome);
    return matching.reduce((best, o) => (o.price > best.price ? o : best), matching[0]);
  };

  return (
    <div className="overflow-x-auto rounded-lg border bg-white">
      <table className="w-full">
        <thead>
          <tr className="border-b text-left text-xs font-medium text-muted-foreground">
            <th className="px-4 py-3">Outcome</th>
            {bookmakers.map((book) => (
              <th key={book} className="px-4 py-3 text-center">
                {book}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {outcomeNames.map((outcome) => {
            const best = bestForOutcome(outcome);
            return (
              <tr key={outcome} className="border-b">
                <td className="px-4 py-3 text-sm font-medium">{outcome}</td>
                {bookmakers.map((book) => {
                  const odds = getOdds(outcome, book);
                  const isBest =
                    odds && best && odds.price === best.price;
                  return (
                    <td
                      key={book}
                      className={`px-4 py-3 text-center font-mono text-sm ${
                        isBest
                          ? "bg-green-50 font-semibold text-green-700"
                          : ""
                      }`}
                    >
                      {odds ? toAmericanOdds(odds.price) : "-"}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
