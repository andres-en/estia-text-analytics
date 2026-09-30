import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { Info } from 'lucide-react'

const RULE_COLOR = '#2a78d6'
const AI_COLOR = '#eda100'

export default function MethodBreakdown({ counts }: { counts: Record<string, number> }) {
  const rule = counts.RULE ?? 0
  const ai = counts.AI ?? 0
  const total = rule + ai

  if (total === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">No classification data yet.</p>
  }

  const rulePct = (rule / total) * 100
  const aiPct = (ai / total) * 100
  const data = [
    { name: 'Rules', value: rule, color: RULE_COLOR },
    { name: 'IA', value: ai, color: AI_COLOR },
  ]

  return (
    <div>
      <div className="flex items-center gap-6">
        <div className="relative shrink-0" style={{ width: 160, height: 160 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} dataKey="value" cx="50%" cy="50%" innerRadius={52} outerRadius={72} paddingAngle={3}>
                {data.map((d) => (
                  <Cell key={d.name} fill={d.color} stroke="none" />
                ))}
              </Pie>
              <Tooltip formatter={(v: unknown) => (Number(v) || 0).toLocaleString('en-US')} />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <div className="text-xl font-semibold text-gray-800 tabular-nums">{total.toLocaleString('en-US')}</div>
            <div className="text-[11px] text-gray-400">conversaciones</div>
          </div>
        </div>

        <div className="flex flex-col gap-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: RULE_COLOR }} />
            <span className="text-gray-600">Rules</span>
            <span className="font-semibold text-gray-800 tabular-nums">{rule.toLocaleString('en-US')}</span>
            <span className="text-gray-400">({rulePct.toFixed(1)}%)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: AI_COLOR }} />
            <span className="text-gray-600">IA</span>
            <span className="font-semibold text-gray-800 tabular-nums">{ai.toLocaleString('en-US')}</span>
            <span className="text-gray-400">({aiPct.toFixed(1)}%)</span>
          </div>
        </div>
      </div>

      <div className="flex items-start gap-2 bg-blue-50 text-blue-900 text-xs rounded-md px-3 py-2 mt-4">
        <Info size={14} className="shrink-0 mt-0.5" />
        <span>AI is only used when the rules could not determine a category (gray zone).</span>
      </div>
    </div>
  )
}
