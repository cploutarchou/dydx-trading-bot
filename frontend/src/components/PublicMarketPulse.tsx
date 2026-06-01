import { Activity, ArrowUpRight, BarChart3, CheckCircle2, RadioTower } from 'lucide-react';
import React, { useMemo, useState } from 'react';

const workflowRows = [
  {
    symbol: 'SCOPE',
    lane: 'Discovery lane',
    state: 'Defined',
    signal: 'Ready',
    control: 'Clear',
    owner: 'Mapped',
    quality: 'Strong',
    route: 'Brief -> constraints -> execution plan',
    points: [34, 38, 36, 45, 51, 49, 58, 64, 61, 72],
  },
  {
    symbol: 'BUILD',
    lane: 'Engineering lane',
    state: 'Active',
    signal: 'In motion',
    control: 'Stable',
    owner: 'Owned',
    quality: 'Strong',
    route: 'Architecture -> implementation -> review',
    points: [42, 45, 48, 46, 54, 57, 55, 63, 68, 71],
  },
  {
    symbol: 'TEST',
    lane: 'Quality lane',
    state: 'Gated',
    signal: 'Verified',
    control: 'Covered',
    owner: 'Traced',
    quality: 'Strong',
    route: 'Contracts -> regression -> release signal',
    points: [26, 34, 31, 42, 45, 53, 58, 56, 64, 76],
  },
  {
    symbol: 'SHIP',
    lane: 'Launch lane',
    state: 'Queued',
    signal: 'Controlled',
    control: 'Observable',
    owner: 'Supported',
    quality: 'Strong',
    route: 'Deploy -> observe -> iterate',
    points: [28, 30, 35, 32, 39, 47, 44, 52, 57, 62],
  },
] as const;

const tapeRows = [
  ...workflowRows,
  {
    symbol: 'AUTO',
    lane: 'Automation watch',
    state: 'Live',
    signal: 'Monitored',
    control: 'Guarded',
    owner: 'Ready',
    quality: 'Strong',
    route: 'Trigger -> action -> verification',
    points: [30, 33, 37, 36, 42, 46, 51, 49, 56, 60],
  },
] as const;

const buildChartPath = (points: readonly number[]) => {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const width = 500;
  const height = 190;
  const xStep = width / (points.length - 1);

  return points
    .map((point, index) => {
      const normalized = max === min ? 0.5 : (point - min) / (max - min);
      const x = index * xStep;
      const y = height - normalized * height + 12;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
};

export const PublicMarketTape: React.FC = () => {
  const tapeItems = [...tapeRows, ...tapeRows];

  return (
    <div className="public-market-tape" aria-label="Execution workflow tape">
      <div className="public-market-tape-label">
        <RadioTower className="h-3.5 w-3.5" />
        Execution watch
      </div>
      <div className="public-market-tape-window">
        <div className="public-market-tape-track">
          {tapeItems.map((item, index) => (
            <div key={`${item.symbol}-${index}`} className="public-market-tape-item">
              <strong>{item.symbol}</strong>
              <span>{item.state}</span>
              <em>{item.signal}</em>
              <small>{item.control}</small>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

interface PublicMarketPulsePanelProps {
  eyebrow?: string;
  title?: string;
  description?: string;
}

export const PublicMarketPulsePanel: React.FC<PublicMarketPulsePanelProps> = ({
  eyebrow = 'Execution pulse',
  title = 'Scope, build, test, and launch state stay visible before action.',
  description = 'Scan the workstreams that matter, compare readiness, and keep execution context close to every decision path.',
}) => {
  const [activeSymbol, setActiveSymbol] =
    useState<(typeof workflowRows)[number]['symbol']>('SCOPE');
  const activeWorkflow = useMemo(
    () => workflowRows.find((workflow) => workflow.symbol === activeSymbol) ?? workflowRows[0],
    [activeSymbol]
  );
  const chartPath = useMemo(() => buildChartPath(activeWorkflow.points), [activeWorkflow]);

  return (
    <div className="public-market-panel">
      <div className="public-market-panel-copy">
        <div className="surface-label">
          <Activity className="h-3.5 w-3.5" />
          {eyebrow}
        </div>
        <h2>{title}</h2>
        <p>{description}</p>

        <div className="public-market-pair-grid">
          {workflowRows.map((workflow) => (
            <button
              key={workflow.symbol}
              type="button"
              onClick={() => setActiveSymbol(workflow.symbol)}
              className={`public-market-pair ${
                activeWorkflow.symbol === workflow.symbol ? 'is-active' : ''
              }`}
            >
              <span>{workflow.symbol}</span>
              <strong>{workflow.state}</strong>
              <em>{workflow.signal}</em>
            </button>
          ))}
        </div>
      </div>

      <div className="public-market-chart-card">
        <div className="public-market-chart-header">
          <div>
            <span>{activeWorkflow.lane}</span>
            <strong>{activeWorkflow.symbol}</strong>
          </div>
          <div className="public-market-quality">
            <CheckCircle2 className="h-4 w-4" />
            {activeWorkflow.quality} signal
          </div>
        </div>

        <div className="public-market-chart">
          <svg
            viewBox="0 0 500 230"
            role="img"
            aria-label={`${activeWorkflow.symbol} execution trend`}
          >
            <defs>
              <linearGradient id="marketPulseLine" x1="0%" x2="100%" y1="0%" y2="0%">
                <stop offset="0%" stopColor="#00D4FF" />
                <stop offset="58%" stopColor="#38BDF8" />
                <stop offset="100%" stopColor="#7C3AED" />
              </linearGradient>
              <linearGradient id="marketPulseFill" x1="0%" x2="0%" y1="0%" y2="100%">
                <stop offset="0%" stopColor="rgba(0,212,255,0.26)" />
                <stop offset="100%" stopColor="rgba(0,212,255,0)" />
              </linearGradient>
            </defs>
            <g className="public-market-grid-lines">
              {[32, 78, 124, 170, 216].map((y) => (
                <line key={y} x1="0" x2="500" y1={y} y2={y} />
              ))}
              {[60, 160, 260, 360, 460].map((x) => (
                <line key={x} x1={x} x2={x} y1="18" y2="218" />
              ))}
            </g>
            <path d={`${chartPath} L 500 220 L 0 220 Z`} fill="url(#marketPulseFill)" />
            <path d={chartPath} className="public-market-line" />
            {activeWorkflow.points.map((point, index) => {
              const max = Math.max(...activeWorkflow.points);
              const min = Math.min(...activeWorkflow.points);
              const normalized = max === min ? 0.5 : (point - min) / (max - min);
              const x = index * (500 / (activeWorkflow.points.length - 1));
              const y = 190 - normalized * 190 + 12;
              return (
                <circle
                  key={`${point}-${index}`}
                  cx={x}
                  cy={y}
                  r={index === activeWorkflow.points.length - 1 ? 5 : 3}
                />
              );
            })}
          </svg>
        </div>

        <div className="public-market-metrics">
          <div>
            <span>Control</span>
            <strong>{activeWorkflow.control}</strong>
          </div>
          <div>
            <span>Ownership</span>
            <strong>{activeWorkflow.owner}</strong>
          </div>
          <div>
            <span>Execution path</span>
            <strong className="text-cyan-300">{activeWorkflow.route}</strong>
          </div>
        </div>

        <div className="public-market-action-row">
          <BarChart3 className="h-4 w-4" />
          <span>Execution workflow signal for delivery planning</span>
          <ArrowUpRight className="h-4 w-4" />
        </div>
      </div>
    </div>
  );
};

export default PublicMarketPulsePanel;
