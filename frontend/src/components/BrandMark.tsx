import React from 'react';

interface BrandMarkProps {
  compact?: boolean;
  className?: string;
  subtitle?: string;
}

export const BrandMark: React.FC<BrandMarkProps> = ({
  compact = false,
  className = '',
  subtitle = 'DeFi execution lab',
}) => {
  return (
    <div className={`execution-brand-mark ${compact ? 'is-compact' : ''} ${className}`.trim()}>
      <div className="execution-brand-symbol" aria-hidden="true">
        <span className="execution-brand-bracket">[</span>
        <span className="execution-brand-core">EL</span>
        <span className="execution-brand-cursor" />
      </div>
      {!compact && (
        <div className="min-w-0">
          <p className="execution-brand-name">ExecutionLab</p>
          <p className="execution-brand-subtitle">{subtitle}</p>
        </div>
      )}
    </div>
  );
};

