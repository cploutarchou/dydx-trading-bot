import { Activity, ArrowUpRight, BarChart3, CheckCircle2, RadioTower } from 'lucide-react';
import React, { useMemo, useState } from 'react';

const marketRows = [
  {
    symbol: 'ETH/USDC',
    venue: 'Main route',
    price: '$3,418.20',
    change: '+2.4%',
    spread: '0.08%',
    depth: '$18.6M',
    quality: 'A',
    route: 'CEX quote -> DEX fill -> hedge',
    points: [34, 38, 36, 45, 51, 49, 58, 64, 61, 72],
  },
  {
    symbol: 'BTC/USDC',
    venue: 'Deep book',
    price: '$68,420',
    change: '+1.1%',
    spread: '0.05%',
    depth: '$42.1M',
    quality: 'A',
    route: 'Index watch -> spot fill -> basis check',
    points: [42, 45, 48, 46, 54, 57, 55, 63, 68, 71],
  },
  {
    symbol: 'SOL/USDC',
    venue: 'Fast lane',
    price: '$182.74',
    change: '+4.8%',
    spread: '0.14%',
    depth: '$7.8M',
    quality: 'B+',
    route: 'Momentum scan -> spread lock -> size guard',
    points: [26, 34, 31, 42, 45, 53, 58, 56, 64, 76],
  },
  {
    symbol: 'ARB/USDC',
    venue: 'L2 watch',
    price: '$1.42',
    change: '+3.2%',
    spread: '0.18%',
    depth: '$4.3M',
    quality: 'B',
    route: 'L2 spread -> execution guard -> rebalance',
    points: [28, 30, 35, 32, 39, 47, 44, 52, 57, 62],
  },
] as const;

const tapeRows = [
  ...marketRows,
  {
    symbol: 'DYDX/USDC',
    venue: 'Runtime watch',
    price: '$2.86',
    change: '+2.9%',
    spread: '0.16%',
    depth: '$3.9M',
    quality: 'B+',
    route: 'Signal watch -> route check -> execution',
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
    <div className="public-market-tape" aria-label="Market price tape">
      <div className="public-market-tape-label">
        <RadioTower className="h-3.5 w-3.5" />
        Market watch
      </div>
      <div className="public-market-tape-window">
        <div className="public-market-tape-track">
          {tapeItems.map((item, index) => (
            <div key={`${item.symbol}-${index}`} className="public-market-tape-item">
              <strong>{item.symbol}</strong>
              <span>{item.price}</span>
              <em>{item.change}</em>
              <small>{item.spread} spread</small>
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
  eyebrow = 'Market pulse',
  title = 'Route quality, spread, and depth stay visible before live action.',
  description = 'Scan the pairs that matter, compare spread discipline, and keep route context close to every evaluation path.',
}) => {
  const [activeSymbol, setActiveSymbol] =
    useState<(typeof marketRows)[number]['symbol']>('ETH/USDC');
  const activeMarket = useMemo(
    () => marketRows.find((market) => market.symbol === activeSymbol) ?? marketRows[0],
    [activeSymbol]
  );
  const chartPath = useMemo(() => buildChartPath(activeMarket.points), [activeMarket]);

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
          {marketRows.map((market) => (
            <button
              key={market.symbol}
              type="button"
              onClick={() => setActiveSymbol(market.symbol)}
              className={`public-market-pair ${activeMarket.symbol === market.symbol ? 'is-active' : ''}`}
            >
              <span>{market.symbol}</span>
              <strong>{market.price}</strong>
              <em>{market.change}</em>
            </button>
          ))}
        </div>
      </div>

      <div className="public-market-chart-card">
        <div className="public-market-chart-header">
          <div>
            <span>{activeMarket.venue}</span>
            <strong>{activeMarket.symbol}</strong>
          </div>
          <div className="public-market-quality">
            <CheckCircle2 className="h-4 w-4" />
            Quality {activeMarket.quality}
          </div>
        </div>

        <div className="public-market-chart">
          <svg viewBox="0 0 500 230" role="img" aria-label={`${activeMarket.symbol} market trend`}>
            <defs>
              <linearGradient id="marketPulseLine" x1="0%" x2="100%" y1="0%" y2="0%">
                <stop offset="0%" stopColor="#67e8f9" />
                <stop offset="100%" stopColor="#84cc16" />
              </linearGradient>
              <linearGradient id="marketPulseFill" x1="0%" x2="0%" y1="0%" y2="100%">
                <stop offset="0%" stopColor="rgba(45,212,191,0.28)" />
                <stop offset="100%" stopColor="rgba(45,212,191,0)" />
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
            {activeMarket.points.map((point, index) => {
              const max = Math.max(...activeMarket.points);
              const min = Math.min(...activeMarket.points);
              const normalized = max === min ? 0.5 : (point - min) / (max - min);
              const x = index * (500 / (activeMarket.points.length - 1));
              const y = 190 - normalized * 190 + 12;
              return (
                <circle
                  key={`${point}-${index}`}
                  cx={x}
                  cy={y}
                  r={index === activeMarket.points.length - 1 ? 5 : 3}
                />
              );
            })}
          </svg>
        </div>

        <div className="public-market-metrics">
          <div>
            <span>Spread</span>
            <strong>{activeMarket.spread}</strong>
          </div>
          <div>
            <span>Depth</span>
            <strong>{activeMarket.depth}</strong>
          </div>
          <div>
            <span>Route intelligence</span>
            <strong className="text-cyan-300">{activeMarket.route}</strong>
          </div>
        </div>

        <div className="public-market-action-row">
          <BarChart3 className="h-4 w-4" />
          <span>Illustrative market feed for route evaluation</span>
          <ArrowUpRight className="h-4 w-4" />
        </div>
      </div>
    </div>
  );
};

export default PublicMarketPulsePanel;
