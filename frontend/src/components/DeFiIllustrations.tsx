import React from 'react';

interface IllustrationProps {
  className?: string;
}

type ServiceIllustrationVariant = 'research' | 'runtime' | 'intelligence' | 'security';

export const DeFiHeroIllustration: React.FC<IllustrationProps> = ({ className = '' }) => {
  return (
    <div className={`market-illustration-shell ${className}`.trim()}>
      <svg viewBox="0 0 720 520" role="img" aria-label="ExecutionLab technical systems illustration">
        <defs>
          <linearGradient id="hero-bg" x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(34,211,238,0.25)" />
            <stop offset="55%" stopColor="rgba(37,99,235,0.08)" />
            <stop offset="100%" stopColor="rgba(16,185,129,0.18)" />
          </linearGradient>
          <linearGradient id="hero-stroke" x1="0%" x2="100%">
            <stop offset="0%" stopColor="#67e8f9" />
            <stop offset="100%" stopColor="#60a5fa" />
          </linearGradient>
          <linearGradient id="hero-gain" x1="0%" x2="0%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="#34d399" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#0f766e" stopOpacity="0.35" />
          </linearGradient>
          <filter id="hero-glow">
            <feGaussianBlur stdDeviation="10" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect x="20" y="20" width="680" height="480" rx="34" fill="url(#hero-bg)" opacity="0.9" />
        <g opacity="0.28">
          {Array.from({ length: 9 }).map((_, index) => (
            <line
              key={`vertical-${index}`}
              x1={80 + index * 70}
              y1="65"
              x2={80 + index * 70}
              y2="450"
              stroke="rgba(148,163,184,0.15)"
              strokeWidth="1"
            />
          ))}
          {Array.from({ length: 5 }).map((_, index) => (
            <line
              key={`horizontal-${index}`}
              x1="70"
              y1={110 + index * 70}
              x2="650"
              y2={110 + index * 70}
              stroke="rgba(148,163,184,0.12)"
              strokeWidth="1"
            />
          ))}
        </g>

        <g className="market-route">
          <path
            d="M120 330 C220 250, 270 250, 340 190 S500 130, 610 180"
            fill="none"
            stroke="url(#hero-stroke)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray="10 12"
          />
          <path
            d="M120 360 C200 290, 290 285, 350 320 S500 390, 620 330"
            fill="none"
            stroke="rgba(52,211,153,0.85)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray="8 12"
          />
        </g>

        <g filter="url(#hero-glow)">
          {[
            { x: 130, y: 340, label: 'IDEA', fill: '#0891b2' },
            { x: 330, y: 190, label: 'BUILD', fill: '#2563eb' },
            { x: 615, y: 182, label: 'SHIP', fill: '#7c3aed' },
            { x: 350, y: 318, label: 'TEST', fill: '#0ea5e9' },
            { x: 610, y: 332, label: 'AUTO', fill: '#14b8a6' },
          ].map((node) => (
            <g key={node.label} className="market-node">
              <circle cx={node.x} cy={node.y} r="34" fill={node.fill} opacity="0.24" />
              <circle cx={node.x} cy={node.y} r="23" fill="#08111f" stroke="rgba(125,211,252,0.4)" />
              <text
                x={node.x}
                y={node.y + 5}
                textAnchor="middle"
                fontSize="12"
                fontWeight="700"
                fill="#f8fafc"
                fontFamily="Manrope, sans-serif"
              >
                {node.label}
              </text>
            </g>
          ))}
        </g>

        <g>
          {[110, 150, 190, 230, 270, 310, 350].map((x, index) => {
            const high = [300, 250, 280, 180, 220, 150, 120][index];
            const low = [370, 330, 350, 240, 300, 220, 190][index];
            const bodyTop = [320, 270, 300, 200, 245, 170, 140][index];
            const bodyHeight = [28, 42, 24, 30, 38, 36, 42][index];
            return (
              <g key={x}>
                <line x1={x} y1={high} x2={x} y2={low} stroke="rgba(125,211,252,0.65)" strokeWidth="2" />
                <rect
                  x={x - 12}
                  y={bodyTop}
                  width="24"
                  height={bodyHeight}
                  rx="8"
                  fill={index % 2 === 0 ? 'url(#hero-gain)' : 'rgba(14,165,233,0.48)'}
                  stroke="rgba(125,211,252,0.45)"
                />
              </g>
            );
          })}
        </g>

        <g>
          <rect x="430" y="82" width="210" height="108" rx="24" fill="rgba(8,15,28,0.78)" stroke="rgba(125,211,252,0.18)" />
          <text x="458" y="116" fill="#94a3b8" fontSize="12" letterSpacing="2.2" fontFamily="Manrope, sans-serif">
            EXECUTION MAP
          </text>
          <text x="458" y="154" fill="#f8fafc" fontSize="34" fontWeight="800" fontFamily="Sora, sans-serif">
            READY
          </text>
          <text x="458" y="177" fill="#34d399" fontSize="14" fontWeight="700" fontFamily="Manrope, sans-serif">
            Build / test / launch route active
          </text>
        </g>

        <g>
          <rect x="82" y="84" width="176" height="74" rx="22" fill="rgba(8,15,28,0.82)" stroke="rgba(96,165,250,0.18)" />
          <text x="104" y="116" fill="#94a3b8" fontSize="12" letterSpacing="2.2" fontFamily="Manrope, sans-serif">
            SYSTEM HEALTH
          </text>
          <text x="104" y="145" fill="#f8fafc" fontSize="22" fontWeight="800" fontFamily="Sora, sans-serif">
            STEADY
          </text>
        </g>
      </svg>
    </div>
  );
};

export const ProfitShareIllustration: React.FC<IllustrationProps> = ({ className = '' }) => {
  return (
    <div className={`market-illustration-shell market-illustration-compact ${className}`.trim()}>
      <svg viewBox="0 0 680 460" role="img" aria-label="ExecutionLab engagement model illustration">
        <defs>
          <linearGradient id="profit-bg" x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(37,99,235,0.18)" />
            <stop offset="100%" stopColor="rgba(16,185,129,0.18)" />
          </linearGradient>
          <linearGradient id="profit-line" x1="0%" x2="100%">
            <stop offset="0%" stopColor="#67e8f9" />
            <stop offset="100%" stopColor="#34d399" />
          </linearGradient>
        </defs>

        <rect x="24" y="24" width="632" height="412" rx="34" fill="url(#profit-bg)" opacity="0.88" />

        <g>
          <rect x="62" y="88" width="170" height="260" rx="28" fill="rgba(8,15,28,0.84)" stroke="rgba(125,211,252,0.18)" />
          <text x="92" y="126" fill="#94a3b8" fontSize="12" letterSpacing="2.2" fontFamily="Manrope, sans-serif">
            OPERATOR
          </text>
          <text x="92" y="170" fill="#f8fafc" fontSize="28" fontWeight="800" fontFamily="Sora, sans-serif">
            SCOPE
          </text>
          <text x="92" y="198" fill="#34d399" fontSize="15" fontWeight="700" fontFamily="Manrope, sans-serif">
            validated execution brief
          </text>
          {[0, 1, 2].map((index) => (
            <rect
              key={index}
              x="90"
              y={226 + index * 34}
              width={110 + index * 18}
              height="14"
              rx="7"
              fill={index === 2 ? 'rgba(52,211,153,0.55)' : 'rgba(59,130,246,0.42)'}
            />
          ))}
        </g>

        <g className="market-route">
          <path
            d="M232 220 C300 220, 325 150, 376 150 S470 220, 520 220"
            fill="none"
            stroke="url(#profit-line)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray="10 12"
          />
          <path
            d="M232 260 C300 260, 326 330, 376 330 S470 260, 520 260"
            fill="none"
            stroke="rgba(96,165,250,0.68)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray="9 11"
          />
        </g>

        <g>
          <circle cx="376" cy="150" r="42" fill="rgba(8,15,28,0.9)" stroke="rgba(103,232,249,0.26)" />
          <text x="376" y="145" textAnchor="middle" fill="#f8fafc" fontSize="14" fontWeight="700" fontFamily="Manrope, sans-serif">
            BUILD
          </text>
          <text x="376" y="166" textAnchor="middle" fill="#67e8f9" fontSize="18" fontWeight="800" fontFamily="Sora, sans-serif">
            LAB
          </text>
          <circle cx="376" cy="330" r="42" fill="rgba(8,15,28,0.9)" stroke="rgba(52,211,153,0.26)" />
          <text x="376" y="325" textAnchor="middle" fill="#f8fafc" fontSize="12" fontWeight="700" fontFamily="Manrope, sans-serif">
            EXECUTE
          </text>
          <text x="376" y="346" textAnchor="middle" fill="#34d399" fontSize="18" fontWeight="800" fontFamily="Sora, sans-serif">
            LOOP
          </text>
        </g>

        <g>
          <rect x="520" y="88" width="98" height="98" rx="26" fill="rgba(8,15,28,0.84)" stroke="rgba(125,211,252,0.18)" />
          <text x="569" y="125" textAnchor="middle" fill="#94a3b8" fontSize="11" letterSpacing="2" fontFamily="Manrope, sans-serif">
            MODEL
          </text>
          <text x="569" y="155" textAnchor="middle" fill="#f8fafc" fontSize="30" fontWeight="800" fontFamily="Sora, sans-serif">
            FIT
          </text>
          <rect x="520" y="216" width="98" height="132" rx="26" fill="rgba(8,15,28,0.84)" stroke="rgba(52,211,153,0.18)" />
          <text x="569" y="252" textAnchor="middle" fill="#94a3b8" fontSize="11" letterSpacing="2" fontFamily="Manrope, sans-serif">
            STATE
          </text>
          <text x="569" y="289" textAnchor="middle" fill="#34d399" fontSize="26" fontWeight="800" fontFamily="Sora, sans-serif">
            READY
          </text>
          <text x="569" y="313" textAnchor="middle" fill="#cbd5e1" fontSize="12" fontFamily="Manrope, sans-serif">
            engage when
          </text>
          <text x="569" y="332" textAnchor="middle" fill="#cbd5e1" fontSize="12" fontFamily="Manrope, sans-serif">
            path is clear
          </text>
        </g>
      </svg>
    </div>
  );
};

export const ServicePulseIllustration: React.FC<
  IllustrationProps & { variant: ServiceIllustrationVariant }
> = ({ className = '', variant }) => {
  const variantMeta = {
    research: {
      title: 'Research signal map',
      subtitle: 'Backtest quality and confidence flow',
      stroke: 'rgba(34,211,238,0.9)',
      fill: 'rgba(8,47,73,0.55)',
      points: ['M60 230 L150 190 L230 205 L315 145 L405 130 L490 110'],
    },
    runtime: {
      title: 'Runtime state flow',
      subtitle: 'Health, stream, and control visibility',
      stroke: 'rgba(52,211,153,0.9)',
      fill: 'rgba(6,78,59,0.52)',
      points: ['M60 220 L145 170 L225 180 L305 140 L395 165 L490 135'],
    },
    intelligence: {
      title: 'Context conviction path',
      subtitle: 'Market narrative and timing clarity',
      stroke: 'rgba(96,165,250,0.9)',
      fill: 'rgba(30,58,138,0.5)',
      points: ['M60 235 L140 205 L225 190 L305 155 L400 140 L490 118'],
    },
    security: {
      title: 'Security readiness path',
      subtitle: 'Account trust and access sequencing',
      stroke: 'rgba(20,184,166,0.92)',
      fill: 'rgba(19,78,74,0.52)',
      points: ['M60 245 L150 218 L235 200 L315 168 L395 145 L490 122'],
    },
  }[variant];

  return (
    <div className={`market-illustration-shell market-illustration-compact ${className}`.trim()}>
      <svg viewBox="0 0 560 320" role="img" aria-label={`${variantMeta.title} illustration`}>
        <defs>
          <linearGradient id={`service-bg-${variant}`} x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(14,165,233,0.2)" />
            <stop offset="100%" stopColor="rgba(16,185,129,0.16)" />
          </linearGradient>
        </defs>

        <rect x="20" y="20" width="520" height="280" rx="26" fill={`url(#service-bg-${variant})`} />

        <g opacity="0.28">
          {Array.from({ length: 6 }).map((_, idx) => (
            <line
              key={`service-v-${variant}-${idx}`}
              x1={65 + idx * 80}
              y1="55"
              x2={65 + idx * 80}
              y2="262"
              stroke="rgba(148,163,184,0.18)"
              strokeWidth="1"
            />
          ))}
          {Array.from({ length: 4 }).map((_, idx) => (
            <line
              key={`service-h-${variant}-${idx}`}
              x1="52"
              y1={90 + idx * 50}
              x2="505"
              y2={90 + idx * 50}
              stroke="rgba(148,163,184,0.14)"
              strokeWidth="1"
            />
          ))}
        </g>

        <g className="market-route">
          {variantMeta.points.map((path) => (
            <path
              key={path}
              d={path}
              fill="none"
              stroke={variantMeta.stroke}
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray="10 12"
            />
          ))}
        </g>

        <g>
          {[80, 160, 240, 320, 400, 480].map((x, idx) => (
            <g key={`service-node-${variant}-${x}`} className="market-node">
              <circle cx={x} cy={250 - idx * 18} r="12" fill={variantMeta.fill} stroke={variantMeta.stroke} />
            </g>
          ))}
        </g>

        <g>
          <rect x="55" y="50" width="235" height="72" rx="18" fill="rgba(8,15,28,0.84)" stroke="rgba(148,163,184,0.22)" />
          <text x="74" y="78" fill="#94a3b8" fontSize="11" letterSpacing="1.8" fontFamily="Manrope, sans-serif">
            {variantMeta.title.toUpperCase()}
          </text>
          <text x="74" y="100" fill="#f8fafc" fontSize="12" fontWeight="700" fontFamily="Manrope, sans-serif">
            {variantMeta.subtitle}
          </text>
        </g>
      </svg>
    </div>
  );
};
