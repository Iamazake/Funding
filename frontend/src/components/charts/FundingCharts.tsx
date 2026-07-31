import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { ChartPoint } from "@/types/funding";

const colors = ["#22d3ee", "#818cf8", "#34d399", "#fbbf24", "#fb7185", "#a78bfa"];
const tooltipStyle = { backgroundColor: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 12, color: "hsl(var(--foreground))" };

interface ChartCardProps { title: string; description: string; data: ChartPoint[]; variant?: "area" | "bar" | "donut"; height?: number; }

export function ChartCard({ title, description, data, variant = "area", height = 290 }: ChartCardProps) {
  return <Card className="bg-card/75"><CardHeader><CardTitle className="text-base">{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader><CardContent>
    <div style={{ height }} role="img" aria-label={`${title}. ${description}`}>
      <ResponsiveContainer width="100%" height="100%">
        {variant === "area" ? <AreaChart data={data} margin={{ left: -20, right: 8, top: 8, bottom: 0 }}><defs><linearGradient id="fundingGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#22d3ee" stopOpacity={0.35} /><stop offset="95%" stopColor="#22d3ee" stopOpacity={0} /></linearGradient></defs><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" /><XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} /><YAxis tickLine={false} axisLine={false} fontSize={12} /><Tooltip contentStyle={tooltipStyle} /><Area type="monotone" dataKey="value" name="Captado" stroke="#22d3ee" strokeWidth={2.5} fill="url(#fundingGradient)" /><Area type="monotone" dataKey="secondaryValue" name="Alocado" stroke="#818cf8" strokeWidth={2} fillOpacity={0} /></AreaChart>
          : variant === "bar" ? <BarChart data={data} margin={{ left: -20, right: 8 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" /><XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={11} /><YAxis tickLine={false} axisLine={false} fontSize={12} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="value" radius={[6, 6, 0, 0]}>{data.map((point, index) => <Cell key={point.label} fill={colors[index % colors.length]} />)}</Bar></BarChart>
            : <PieChart><Pie data={data} dataKey="value" nameKey="label" innerRadius={65} outerRadius={98} paddingAngle={4}>{data.map((point, index) => <Cell key={point.label} fill={colors[index % colors.length]} />)}</Pie><Tooltip contentStyle={tooltipStyle} /></PieChart>}
      </ResponsiveContainer>
    </div>
    {variant === "donut" && <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-2">{data.map((point, index) => <span key={point.label} className="flex items-center gap-2 text-xs text-muted-foreground"><span className="size-2 rounded-full" style={{ background: colors[index % colors.length] }} />{point.label}</span>)}</div>}
  </CardContent></Card>;
}
