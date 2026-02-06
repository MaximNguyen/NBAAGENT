import type { OddsComparison } from "@/types";

interface OddsHeatmapProps {
  data: OddsComparison;
}

export function OddsHeatmap({ data }: OddsHeatmapProps) {
  const bookmakers = [...new Set(data.outcomes.map((o) => o.bookmaker))];
  const outcomeNames = [...new Set(data.outcomes.map((o) => o.outcome))];

  // Find price range for color scaling
  const prices = data.outcomes.map((o) => o.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const range = maxPrice - minPrice || 1;

  const getColor = (price: number) => {
    const ratio = (price - minPrice) / range;
    const green = Math.round(ratio * 200);
    return `rgb(${200 - green}, ${100 + green}, 100)`;
  };

  return (
    <div className="rounded-lg border bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold">Odds Heatmap</h3>
      <div className="grid gap-1" style={{ gridTemplateColumns: `auto repeat(${bookmakers.length}, 1fr)` }}>
        <div />
        {bookmakers.map((book) => (
          <div key={book} className="text-center text-xs font-medium text-muted-foreground truncate px-1">
            {book}
          </div>
        ))}
        {outcomeNames.map((outcome) => (
          <>
            <div key={outcome} className="text-xs font-medium py-2 pr-2">{outcome}</div>
            {bookmakers.map((book) => {
              const odds = data.outcomes.find(
                (o) => o.outcome === outcome && o.bookmaker === book
              );
              return (
                <div
                  key={`${outcome}-${book}`}
                  className="rounded py-2 text-center text-xs font-mono text-white"
                  style={{
                    backgroundColor: odds ? getColor(odds.price) : "#e5e7eb",
                  }}
                >
                  {odds ? odds.price.toFixed(2) : "-"}
                </div>
              );
            })}
          </>
        ))}
      </div>
    </div>
  );
}
