import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { MonthlyROI } from "@/types";

interface BankrollChartProps {
  data: MonthlyROI[];
  initialBankroll?: number;
}

export function BankrollChart({
  data,
  initialBankroll = 1000,
}: BankrollChartProps) {
  let bankroll = initialBankroll;
  const chartData = [{ month: "Start", bankroll: initialBankroll }];

  for (const d of data) {
    bankroll += d.net_profit;
    chartData.push({ month: d.month, bankroll: Math.round(bankroll) });
  }

  return (
    <div className="rounded-lg border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold">Bankroll Growth</h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${v}`} />
          <Tooltip
            formatter={(value: number) => [`$${value.toFixed(0)}`, "Bankroll"]}
          />
          <Area
            type="monotone"
            dataKey="bankroll"
            stroke="hsl(221.2, 83.2%, 53.3%)"
            fill="hsl(221.2, 83.2%, 53.3%)"
            fillOpacity={0.1}
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
