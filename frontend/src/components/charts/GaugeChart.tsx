import React from 'react';
import { Band, ApiConfig } from '../../types';
import { BandChip } from '../BandChip';
import { DEFAULT_CONFIG } from '../../lib/constants';

interface GaugeChartProps {
  overall: number;
  band: Band;
  config?: ApiConfig;
  pendingDeep?: boolean;
}

export const GaugeChart: React.FC<GaugeChartProps> = ({
  overall,
  band,
  config = DEFAULT_CONFIG,
  pendingDeep = false,
}) => {
  const lowMax = config.bands?.low_max ?? 0.35;
  const mediumMax = config.bands?.medium_max ?? 0.65;

  // Arc math: 180-degree semicircular gauge from -180° to 0°
  const radius = 90;
  const cx = 110;
  const cy = 110;
  const strokeWidth = 14;

  // Converts score [0..1] to angle in radians (-PI to 0)
  const scoreToAngle = (score: number) => {
    const clamped = Math.max(0, Math.min(1, score));
    return Math.PI + clamped * Math.PI;
  };

  const describeArc = (startScore: number, endScore: number) => {
    const startAngle = scoreToAngle(startScore);
    const endAngle = scoreToAngle(endScore);

    const x1 = cx + radius * Math.cos(startAngle);
    const y1 = cy + radius * Math.sin(startAngle);
    const x2 = cx + radius * Math.cos(endAngle);
    const y2 = cy + radius * Math.sin(endAngle);

    const largeArcFlag = endAngle - startAngle <= Math.PI ? '0' : '1';

    return `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`;
  };

  // Needle angle in degrees (-90 to 90)
  const needleAngle = -90 + Math.max(0, Math.min(1, overall)) * 180;

  return (
    <div className="flex flex-col items-center justify-center p-4 apple-glass-card pencil-hover rounded-2xl border border-stone-200/80 shadow-xs">
      <div className="relative w-[220px] h-[130px]">
        <svg viewBox="0 0 220 135" className="w-full h-full overflow-visible">
          {/* Green Zone (Authentic) */}
          <path
            d={describeArc(0, lowMax)}
            fill="none"
            stroke="#2e7d32"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            className="opacity-85"
          />

          {/* Amber Zone (Suspicious) */}
          <path
            d={describeArc(lowMax, mediumMax)}
            fill="none"
            stroke="#ef6c00"
            strokeWidth={strokeWidth}
            className="opacity-85"
          />

          {/* Red Zone (Manipulated) */}
          <path
            d={describeArc(mediumMax, 1.0)}
            fill="none"
            stroke="#c62828"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            className="opacity-85"
          />

          {/* Tick marks */}
          <text x="18" y="128" className="text-[10px] fill-stone-500 font-mono font-semibold">0.0</text>
          <text x="104" y="24" className="text-[10px] fill-stone-500 font-mono font-semibold">0.5</text>
          <text x="188" y="128" className="text-[10px] fill-stone-500 font-mono font-semibold">1.0</text>

          {/* Pivot Center */}
          <circle cx={cx} cy={cy} r="6" className="fill-stone-800" />

          {/* Needle */}
          <g transform={`rotate(${needleAngle} ${cx} ${cy})`} className="transition-transform duration-700 ease-out">
            <line
              x1={cx}
              y1={cy}
              x2={cx}
              y2={cy - radius + 6}
              stroke="#0f172a"
              strokeWidth="3.5"
              strokeLinecap="round"
              className="shadow-md"
            />
            <circle cx={cx} cy={cy - radius + 6} r="3" fill="#dc2626" />
          </g>
        </svg>
      </div>

      <div className="mt-1 flex flex-col items-center gap-1.5">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-extrabold tracking-tight font-mono text-stone-900">
            {overall.toFixed(2)}
          </span>
          <span className="text-xs text-stone-500 font-mono font-semibold">/ 1.00</span>
        </div>

        <div className="flex items-center gap-2 mt-1">
          <BandChip band={band} size="md" />
          {pendingDeep && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-800 border border-blue-200 animate-pulse">
              Deep scan running…
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
