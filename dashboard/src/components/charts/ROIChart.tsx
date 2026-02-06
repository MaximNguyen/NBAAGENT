import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { MonthlyROI } from "@/types";

interface ROIChartProps {
  data: MonthlyROI[];
}

export function ROIChart({ data }: ROIChartProps) {
  // Build cumulative ROI data
  let cumulative = 0;
  const chartData = data.map((d) => {
    cumulative += d.roi_pct;
    return { month: d.month, roi: cumulative };
  });

  return (
    <div className="rounded-lg border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold">Cumulative ROI</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} unit="%" />
          <Tooltip
            formatter={(value: number) => [`${value.toFixed(1)}%`, "ROI"]}
          />
          <Line
            type="monotone"
            dataKey="roi"
            stroke="hsl(221.2, 83.2%, 53.3%)"
            strokeWidth={2}
            dot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
