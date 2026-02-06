import type { SportsbookMetrics } from "@/types";

interface SportsbookCoverageProps {
  data: SportsbookMetrics[];
}

export function SportsbookCoverage({ data }: SportsbookCoverageProps) {
  return (
    <div className="rounded-lg border bg-white">
      <div className="border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Sportsbook Coverage</h3>
      </div>
      <table className="w-full">
        <thead>
          <tr className="border-b text-left text-xs font-medium text-muted-foreground">
            <th className="px-4 py-2">Sportsbook</th>
            <th className="px-4 py-2">Games</th>
            <th className="px-4 py-2">Markets</th>
            <th className="px-4 py-2">Coverage</th>
          </tr>
        </thead>
        <tbody>
          {data.map((book) => (
            <tr key={book.name} className="border-b">
              <td className="px-4 py-2 text-sm font-medium">{book.name}</td>
              <td className="px-4 py-2 text-sm">{book.games_with_odds}</td>
              <td className="px-4 py-2 text-sm">
                {book.markets_available.join(", ")}
              </td>
              <td className="px-4 py-2">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-100">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${book.availability_pct}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {book.availability_pct}%
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {data.length === 0 && (
        <div className="p-8 text-center text-sm text-muted-foreground">
          No sportsbook data available. Run an analysis first.
        </div>
      )}
    </div>
  );
}
