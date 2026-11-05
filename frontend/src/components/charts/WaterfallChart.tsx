import React, { useState } from 'react';
import { getFriendlyName } from '../../lib/constants';

interface WaterfallChartProps {
  waterfall: [string, number][]; // [["baseline", 0.5], ["localizer", 0.21], ...]
  overall: number;
}

export const WaterfallChart: React.FC<WaterfallChartProps> = ({ waterfall, overall }) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (!waterfall || waterfall.length === 0) {
    return <div className="text-xs text-zinc-400 p-4">No waterfall data available.</div>;
  }

  // Calculate cumulative steps
  // Item 0: baseline (from 0 to val)
  // Subsequent: from previous running total to running total + val
  // Final bar: from 0 to overall
  let running = 0;
  const bars = waterfall.map(([name, val], idx) => {
    const isBaseline = idx === 0 || name.toLowerCase() === 'baseline';
    const start = isBaseline ? 0 : running;
    const end = isBaseline ? val : running + val;
    running = end;

    const friendly = isBaseline ? 'Baseline Prior' : getFriendlyName(name);
    const isPositive = val >= 0;

    return {
      name,
      friendly,
      val,
      start,
      end,
      isBaseline,
      color: isBaseline
        ? '#64748b' // Slate for baseline
        : isPositive
        ? '#c62828' // Red: pushed toward fraud
        : '#2e7d32', // Green: pushed toward authentic
    };
  });

  // Append Total / Final bar
  bars.push({
    name: 'overall',
    friendly: 'Overall Score',
    val: overall,
    start: 0,
    end: overall,
    isBaseline: false,
    color: overall >= 0.65 ? '#c62828' : overall >= 0.35 ? '#ef6c00' : '#2e7d32',
  });

  // Calculate min/max range for scaling
  const allValues = [0, 1, ...bars.flatMap((b) => [b.start, b.end])];
  const minVal = Math.min(0, ...allValues);
  const maxVal = Math.max(1, ...allValues);
  const range = maxVal - minVal || 1;

  const height = 260;
  const paddingBottom = 75;
  const chartHeight = height - paddingBottom;
  const barWidth = 38;
  const gap = 20;
  const totalWidth = Math.max(500, bars.length * (barWidth + gap) + 40);

  const getY = (val: number) => {
    return chartHeight - ((val - minVal) / range) * chartHeight;
  };

  const zeroY = getY(0);

  return (
    <div className="w-full apple-glass-card pencil-hover p-5 rounded-2xl border border-stone-200/80 shadow-xs">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="text-sm font-bold text-stone-900 tracking-tight">
            Score Attribution Waterfall
          </h4>
          <p className="text-xs text-stone-600 font-medium">
            Factors shifting score toward fraud (<span className="text-rose-700 font-bold">+red</span>) or authentic (<span className="text-emerald-700 font-bold">-green</span>)
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-semibold text-stone-600">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-700" /> Fraud (+score)
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-700" /> Authentic (-score)
          </span>
        </div>
      </div>

      <div className="overflow-x-auto pb-2">
        <svg
          width={totalWidth}
          height={height}
          className="overflow-visible font-sans"
        >
          {/* Grid lines */}
          <line
            x1="20"
            y1={zeroY}
            x2={totalWidth - 20}
            y2={zeroY}
            stroke="#94a3b8"
            strokeDasharray="2,2"
            strokeWidth="1"
            className="opacity-40"
          />

          {/* Reference line for 0.5 */}
          <line
            x1="20"
            y1={getY(0.5)}
            x2={totalWidth - 20}
            y2={getY(0.5)}
            stroke="#cbd5e1"
            strokeDasharray="4,4"
            strokeWidth="1"
            className="opacity-40"
          />

          {bars.map((bar, idx) => {
            const x = 30 + idx * (barWidth + gap);
            const topVal = Math.max(bar.start, bar.end);
            const btmVal = Math.min(bar.start, bar.end);
            const y = getY(topVal);
            const h = Math.max(3, getY(btmVal) - y);
            const isHovered = hoveredIdx === idx;

            return (
              <g
                key={idx}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                className="cursor-pointer transition-opacity"
              >
                {/* Connecting dotted connector line to previous bar */}
                {idx > 0 && idx < bars.length - 1 && (
                  <line
                    x1={x - gap}
                    y1={getY(bar.start)}
                    x2={x}
                    y2={getY(bar.start)}
                    stroke="#94a3b8"
                    strokeDasharray="2,2"
                    strokeWidth="1"
                    className="opacity-50"
                  />
                )}

                {/* The Bar */}
                <rect
                  x={x}
                  y={y}
                  width={barWidth}
                  height={h}
                  rx="4"
                  fill={bar.color}
                  className={`transition-all duration-200 ${isHovered ? 'brightness-110 filter drop-shadow-md' : 'opacity-90'}`}
                />

                {/* Delta / Value label on top or bottom */}
                <text
                  x={x + barWidth / 2}
                  y={y - 6}
                  textAnchor="middle"
                  className="text-[10px] font-mono font-bold fill-stone-800"
                >
                  {bar.isBaseline || bar.name === 'overall'
                    ? bar.val.toFixed(2)
                    : `${bar.val > 0 ? '+' : ''}${bar.val.toFixed(2)}`}
                </text>

                {/* X-axis friendly label (rotated for space) */}
                <text
                  x={x + barWidth / 2}
                  y={chartHeight + 16}
                  textAnchor="end"
                  transform={`rotate(-40, ${x + barWidth / 2}, ${chartHeight + 16})`}
                  className={`text-[11px] transition-colors ${
                    isHovered
                      ? 'fill-stone-950 font-bold'
                      : 'fill-stone-700 font-semibold'
                  }`}
                >
                  {bar.friendly}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
