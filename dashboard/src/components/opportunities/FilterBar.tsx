import { useState } from "react";

interface FilterBarProps {
  onFilterChange: (filters: {
    min_ev?: number;
    confidence?: string;
    team?: string;
    market?: string;
  }) => void;
}

export function FilterBar({ onFilterChange }: FilterBarProps) {
  const [minEv, setMinEv] = useState<number>(0);
  const [confidence, setConfidence] = useState<string>("");
  const [team, setTeam] = useState<string>("");
  const [market, setMarket] = useState<string>("");

  const apply = () => {
    onFilterChange({
      min_ev: minEv > 0 ? minEv / 100 : undefined,
      confidence: confidence || undefined,
      team: team || undefined,
      market: market || undefined,
    });
  };

  return (
    <div className="flex flex-wrap items-end gap-4 rounded-lg border bg-white p-4">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">
          Min EV %
        </label>
        <input
          type="range"
          min={0}
          max={20}
          step={0.5}
          value={minEv}
          onChange={(e) => setMinEv(Number(e.target.value))}
          className="w-32"
        />
        <span className="text-xs text-muted-foreground">{minEv}%</span>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">
          Confidence
        </label>
        <select
          value={confidence}
          onChange={(e) => setConfidence(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm"
        >
          <option value="">All</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">
          Team
        </label>
        <input
          type="text"
          placeholder="e.g. BOS"
          value={team}
          onChange={(e) => setTeam(e.target.value.toUpperCase())}
          className="w-20 rounded-md border px-3 py-1.5 text-sm"
          maxLength={3}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">
          Market
        </label>
        <select
          value={market}
          onChange={(e) => setMarket(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm"
        >
          <option value="">All</option>
          <option value="h2h">Moneyline</option>
          <option value="spreads">Spread</option>
          <option value="totals">Totals</option>
        </select>
      </div>

      <button
        onClick={apply}
        className="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-white hover:bg-primary/90"
      >
        Apply
      </button>
    </div>
  );
}
