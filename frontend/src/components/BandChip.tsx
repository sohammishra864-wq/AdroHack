import React from 'react';
import { Band } from '../types';
import { BAND_CONFIG } from '../lib/constants';

interface BandChipProps {
  band: Band | null | undefined;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export const BandChip: React.FC<BandChipProps> = ({ band, size = 'md', showLabel = true }) => {
  if (!band) return null;

  const config = BAND_CONFIG[band] || BAND_CONFIG.UNCERTAIN;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs font-semibold gap-1.5',
    md: 'px-2.5 py-1 text-xs font-bold gap-2',
    lg: 'px-3.5 py-1.5 text-sm font-bold gap-2.5',
  };

  const dotSizes = {
    sm: 'w-1.5 h-1.5',
    md: 'w-2 h-2',
    lg: 'w-2.5 h-2.5',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border transition-colors ${config.bg} ${config.text} ${config.border} ${sizeClasses[size]}`}
      role="status"
      aria-label={`Risk band: ${config.label}`}
    >
      <span
        className={`rounded-full ${dotSizes[size]}`}
        style={{ backgroundColor: config.color }}
        aria-hidden="true"
      />
      {showLabel && <span>{config.label}</span>}
    </span>
  );
};
