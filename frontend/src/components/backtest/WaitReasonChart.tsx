import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type WaitReasonRow = { reason: string; count: number };

export function WaitReasonChart({ rows }: { rows: WaitReasonRow[] }) {
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows}>
          <CartesianGrid stroke="#e5e7eb" vertical={false} />
          <XAxis dataKey="reason" tick={{ fontSize: 10 }} interval={0} angle={-20} height={70} />
          <YAxis />
          <Tooltip />
          <Bar dataKey="count" fill="#0f766e" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
