import {
	ArrowRight,
	CheckCircle2,
	Radar,
	ShieldCheck,
	Sparkles,
	TrendingUp,
	Waypoints,
} from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { DeFiHeroIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import { PublicMarketPulsePanel } from '../components/PublicMarketPulse';
import PublicSiteShell from '../components/PublicSiteShell';

const pathItems = [
  [Waypoints, 'Research', 'Frame markets, pairs, assumptions, and execution constraints first'],
  [ShieldCheck, 'Validate', 'Backtest strategy logic with risk controls before runtime promotion'],
  [TrendingUp, 'Execute', 'Move into dYdX bot operations only when readiness is visible'],
] as const;

const valueItems = [
  [
    Radar,
    'Strategy confidence',
    'Compare market context, backtest evidence, and operating risk before a strategy moves live.',
  ],
  [
    ShieldCheck,
    'Secure operator entry',
    'Keep account setup, MFA posture, and credential readiness visible before trading workflows.',
  ],
  [
    Sparkles,
    'Runtime clarity',
    'Make bot state, backtest progress, and degraded conditions readable the moment they change.',
  ],
] as const;

const proofItems = [
  ['Validation first', 'Research and backtest evidence reviewed before live runtime'],
  ['Operational control', 'Bot state, health, and action paths kept close together'],
  ['Execution clarity', 'Market intel, strategies, backtests, and admin workflows connected'],
] as const;

const trustItems = [
  [
    'Controls-first onboarding',
    'Credential checks, environment confirmation, and operator gating before runtime actions',
  ],
  [
    'Validation-led operating model',
    'Research and backtests first, then execution only when risk context is measurable',
  ],
  [
    'Audit-ready operations',
    'Traceable API paths, runtime status evidence, and role-based visibility across surfaces',
  ],
] as const;

const riskItems = [
  'Crypto trading carries risk, including volatility, liquidity gaps, fees, latency, and execution uncertainty.',
  'Backtests are evidence for planning, not guarantees of live production behavior.',
  'Runtime quality depends on reliable systems, valid credentials, market data, and disciplined operator decisions.',
  'Operators remain responsible for wallet security, compliance, jurisdiction, and capital risk decisions.',
] as const;

const workflowStages = [
  {
    id: 'research',
    label: 'Research',
    title: 'Frame the market before deploying capital.',
    body: 'Review market structure, pair context, and execution assumptions so every next step starts with evidence.',
    metrics: ['Market context', 'Pair signal', 'Execution constraints'],
    cta: 'Refine the strategy brief',
    icon: Waypoints,
  },
  {
    id: 'validate',
    label: 'Validate',
    title: 'Turn hypotheses into measured backtest evidence.',
    body: 'Measure performance, compare scenarios, and surface the risks that matter before a strategy reaches runtime.',
    metrics: ['Backtest quality', 'Risk profile', 'Promotion readiness'],
    cta: 'Review engagement options',
    icon: ShieldCheck,
  },
  {
    id: 'execute',
    label: 'Execute',
    title: 'Move from validated intent into controlled runtime.',
    body: 'Keep operator state, access, and bot health visible so live workflows stay transparent as conditions change.',
    metrics: ['Bot health', 'Operator access', 'Live readiness'],
    cta: 'Request platform access',
    icon: TrendingUp,
  },
] as const;

const roadmapTracks = [
  {
    id: 'automation',
    label: 'Automation',
    title: 'Execution flow automation',
    summary: 'Workflow routing, state awareness, and safer operational handoffs.',
    pulse: [18, 28, 22, 35, 42, 47, 55, 60],
    status: 'Coming next',
  },
  {
    id: 'signals',
    label: 'Signals',
    title: 'Market signal intelligence',
    summary: 'Sharper market context, strategy cues, and review-ready signal cards.',
    pulse: [24, 30, 38, 45, 43, 50, 58, 66],
    status: 'In progress',
  },
  {
    id: 'controls',
    label: 'Controls',
    title: 'Operator control surfaces',
    summary: 'Faster access, better permissions cues, and safer launch actions.',
    pulse: [30, 32, 31, 39, 46, 52, 59, 67],
    status: 'Planned',
  },
  {
    id: 'insights',
    label: 'Insights',
    title: 'Live insight panels',
    summary: 'Readable runtime state, readiness indicators, and trend snapshots.',
    pulse: [16, 22, 30, 36, 44, 53, 57, 65],
    status: 'Queued',
  },
] as const;

const roadmapTrackDetails = {
  automation: [
    'Safer handoffs between research and live control',
    'Operator actions become easier to preview before launch',
    'Future releases can attach to the same workflow rails',
  ],
  signals: [
    'Market cues become easier to compare at a glance',
    'Strategy review gets a clearer read on momentum shifts',
    'Animated states highlight what changed since last visit',
  ],
  controls: [
    'Permissions and access states stay visible up front',
    'Critical action paths can be designed with fewer surprises',
    'Approvals and guardrails remain part of the product story',
  ],
  insights: [
    'Future dashboards can surface live readiness faster',
    'Operators see signal quality before diving into details',
    'The product can present more of its runtime intelligence',
  ],
} as const;

const buildRoadmapPath = (points: readonly number[]): string => {
  const width = 500;
  const height = 180;
  const xStep = width / (points.length - 1);
  const max = Math.max(...points);
  const min = Math.min(...points);

  return points
    .map((point, index) => {
      const normalized = max === min ? 0.5 : (point - min) / (max - min);
      const x = index * xStep;
      const y = height - normalized * height + 14;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
};

export const LandingPage: React.FC = () => {
  const [selectedWorkflowStage, setSelectedWorkflowStage] = useState(workflowStages[0].id);
  const [selectedRoadmapTrack, setSelectedRoadmapTrack] = useState(roadmapTracks[0].id);
  const [isRoadmapHovered, setIsRoadmapHovered] = useState(false);
  const [hoveredRoadmapMetric, setHoveredRoadmapMetric] = useState<string | null>(null);
  const autoRotateRef = useRef<number | null>(null);
  const activeWorkflowStage =
    workflowStages.find((stage) => stage.id === selectedWorkflowStage) ?? workflowStages[0];
  const ActiveWorkflowIcon = activeWorkflowStage.icon;
  const activeRoadmapTrack =
    roadmapTracks.find((track) => track.id === selectedRoadmapTrack) ?? roadmapTracks[0];
  const activeRoadmapPath = buildRoadmapPath(activeRoadmapTrack.pulse);
  const activeRoadmapDetails = roadmapTrackDetails[selectedRoadmapTrack];

  useEffect(() => {
    if (isRoadmapHovered) {
      if (autoRotateRef.current !== null) {
        window.clearInterval(autoRotateRef.current);
        autoRotateRef.current = null;
      }
      return undefined;
    }

    autoRotateRef.current = window.setInterval(() => {
      setSelectedRoadmapTrack((current) => {
        const currentIndex = roadmapTracks.findIndex((track) => track.id === current);
        const nextIndex = (currentIndex + 1) % roadmapTracks.length;
        return roadmapTracks[nextIndex].id;
      });
    }, 4800);

    return () => {
      if (autoRotateRef.current !== null) {
        window.clearInterval(autoRotateRef.current);
        autoRotateRef.current = null;
      }
    };
  }, [isRoadmapHovered]);

  return (
    <PublicSiteShell>
      <div className="public-modern-page">
        <section className="public-modern-hero public-modern-hero-intelligence">
          <div className="public-modern-container public-modern-hero-grid">
            <MotionReveal className="public-modern-copy" distancePx={18}>
              <div className="surface-label">
                <Radar className="h-3.5 w-3.5" />
                DeFi execution intelligence
              </div>
              <h1>ExecutionLab</h1>
              <p>
                Research markets, validate crypto strategies, and operate dYdX execution workflows
                from a controlled fintech-grade workspace.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  to="/register"
                  className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3.5 text-sm font-semibold text-white"
                >
                  Request platform access
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/pricing"
                  className="premium-button premium-button-secondary justify-center px-6 py-3.5 text-sm font-medium"
                >
                  View engagement model
                </Link>
              </div>

              <div className="mt-6 flex flex-wrap gap-3 text-xs text-slate-400">
                <span className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-2 text-cyan-200">
                  Research to runtime
                </span>
                <span className="rounded-full border border-slate-700/70 bg-slate-950/40 px-3 py-2">
                  Click to explore the workflow
                </span>
                <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-emerald-200">
                  Operator-grade visibility
                </span>
              </div>
            </MotionReveal>

            <MotionReveal className="public-modern-visual" delayMs={90} distancePx={18}>
              <div className="public-visual-photo" aria-hidden="true" />
              <div className="public-visual-terminal">
                <div className="public-terminal-bar">
                  <span />
                  <span />
                  <span />
                  <strong>EXECUTION LAB</strong>
                </div>
                <DeFiHeroIllustration />
              </div>
              <div className="public-visual-tags">
                <span>Research evidence</span>
                <span>Runtime control</span>
                <span>Automation ready</span>
              </div>
            </MotionReveal>
          </div>
        </section>

        <section id="workflow-explorer" className="public-modern-container public-outcome-stage">
          <MotionReveal className="public-modern-section-copy" distancePx={18}>
            <div className="surface-label">
              <Sparkles className="h-3.5 w-3.5" />
              Interactive workflow explorer
            </div>
            <h2>Click a stage to preview how ExecutionLab guides the next move.</h2>
            <p>
              This keeps the product story tactile: operators can jump between research, validation,
              and execution without losing the thread.
            </p>
          </MotionReveal>

          <MotionReveal className="mt-8 grid gap-6 lg:grid-cols-[0.42fr,0.58fr]" distancePx={18}>
            <div className="space-y-3">
              {workflowStages.map((stage, index) => {
                const isActive = stage.id === selectedWorkflowStage;
                return (
                  <button
                    key={stage.id}
                    type="button"
                    onClick={() => setSelectedWorkflowStage(stage.id)}
                    className={`w-full rounded-2xl border p-4 text-left transition duration-200 ${
                      isActive
                        ? 'border-cyan-500/40 bg-cyan-500/10 shadow-lg shadow-cyan-500/10'
                        : 'border-slate-700/70 bg-slate-950/60 hover:border-slate-500 hover:bg-slate-900/80'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="surface-label">
                          <span className="h-3.5 w-3.5 rounded-full bg-current opacity-70" />
                          Step {String(index + 1).padStart(2, '0')}
                        </div>
                        <h3 className="mt-3 text-lg font-semibold text-white">{stage.label}</h3>
                      </div>
                      <stage.icon
                        className={`h-5 w-5 ${isActive ? 'text-cyan-300' : 'text-slate-400'}`}
                      />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-400">{stage.body}</p>
                  </button>
                );
              })}
            </div>

            <div className="rounded-3xl border border-slate-700/70 bg-slate-950/70 p-6 shadow-2xl shadow-black/30">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="surface-label">
                    <ActiveWorkflowIcon className="h-3.5 w-3.5" />
                    {activeWorkflowStage.label}
                  </div>
                  <h3 className="mt-4 text-2xl font-semibold text-white sm:text-3xl">
                    {activeWorkflowStage.title}
                  </h3>
                </div>
                <span className="rounded-full border border-slate-700/70 bg-slate-900/80 px-3 py-1 text-xs font-medium text-slate-300">
                  Interactive
                </span>
              </div>

              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-400 sm:text-base">
                {activeWorkflowStage.body}
              </p>

              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                {activeWorkflowStage.metrics.map((metric) => (
                  <div
                    key={metric}
                    className="rounded-2xl border border-slate-700/70 bg-slate-900/80 px-4 py-4"
                  >
                    <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-300/80">Focus</p>
                    <p className="mt-2 text-sm font-semibold text-white">{metric}</p>
                  </div>
                ))}
              </div>

              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <Link
                  to="/register"
                  className="premium-button premium-button-primary justify-center px-5 py-3 text-sm font-semibold text-white"
                >
                  {activeWorkflowStage.cta}
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/pricing"
                  className="premium-button premium-button-secondary justify-center px-5 py-3 text-sm font-medium"
                >
                  Review the engagement model
                </Link>
              </div>
            </div>
          </MotionReveal>
        </section>

        <section className="public-modern-container public-outcome-stage">
          <MotionReveal className="public-modern-section-copy" distancePx={18}>
            <div className="surface-label">
              <TrendingUp className="h-3.5 w-3.5" />
              Coming next preview
            </div>
            <h2>Interactive release roadmap with animated growth signals.</h2>
            <p>
              Visitors can click the roadmap to see what’s coming across automation, signals,
              controls, and insights before launch.
            </p>
          </MotionReveal>

          <MotionReveal
            className="mt-8 grid gap-6 lg:grid-cols-[0.38fr,0.62fr]"
            distancePx={18}
            as="div"
          >
            <div className="space-y-3">
              {roadmapTracks.map((track, index) => {
                const isActive = track.id === selectedRoadmapTrack;
                return (
                  <button
                    key={track.id}
                    type="button"
                    onClick={() => setSelectedRoadmapTrack(track.id)}
                    className={`w-full rounded-2xl border p-4 text-left transition duration-200 ${
                      isActive
                        ? 'border-emerald-500/40 bg-emerald-500/10 shadow-lg shadow-emerald-500/10'
                        : 'border-slate-700/70 bg-slate-950/60 hover:border-slate-500 hover:bg-slate-900/80'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="surface-label">
                          <span className="h-2.5 w-2.5 rounded-full bg-current opacity-70" />
                          Preview {String(index + 1).padStart(2, '0')}
                        </div>
                        <h3 className="mt-3 text-lg font-semibold text-white">{track.label}</h3>
                      </div>
                      <span
                        className={`rounded-full border px-3 py-1 text-xs font-medium ${
                          isActive
                            ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-200'
                            : 'border-slate-700/70 bg-slate-900/80 text-slate-400'
                        }`}
                      >
                        {track.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-400">{track.summary}</p>
                  </button>
                );
              })}
            </div>

            <div
              className="rounded-3xl border border-slate-700/70 bg-slate-950/70 p-6 shadow-2xl shadow-black/30"
              onMouseEnter={() => setIsRoadmapHovered(true)}
              onMouseLeave={() => setIsRoadmapHovered(false)}
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="surface-label">
                    <Sparkles className="h-3.5 w-3.5" />
                    {activeRoadmapTrack.label}
                  </div>
                  <h3 className="mt-4 text-2xl font-semibold text-white sm:text-3xl">
                    {activeRoadmapTrack.title}
                  </h3>
                </div>
                <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-200">
                  {isRoadmapHovered ? 'Paused on hover' : 'Animated preview'}
                </span>
              </div>

              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-400 sm:text-base">
                {activeRoadmapTrack.summary}
              </p>

              <div className="mt-6 rounded-2xl border border-slate-700/70 bg-slate-900/80 p-4">
                <div className="mb-4 flex items-center justify-between gap-3 text-xs text-slate-400">
                  <span>Projected engagement pulse</span>
                  <span className="text-emerald-200">{activeRoadmapTrack.status}</span>
                </div>
                <svg
                  viewBox="0 0 500 220"
                  role="img"
                  aria-label={`${activeRoadmapTrack.label} roadmap trend`}
                  className="h-55 w-full"
                >
                  <defs>
                    <linearGradient id="roadmapPulseLine" x1="0%" x2="100%" y1="0%" y2="0%">
                      <stop offset="0%" stopColor="#34d399" />
                      <stop offset="60%" stopColor="#22d3ee" />
                      <stop offset="100%" stopColor="#8b5cf6" />
                    </linearGradient>
                    <linearGradient id="roadmapPulseFill" x1="0%" x2="0%" y1="0%" y2="100%">
                      <stop offset="0%" stopColor="rgba(52,211,153,0.28)" />
                      <stop offset="100%" stopColor="rgba(52,211,153,0)" />
                    </linearGradient>
                  </defs>

                  <g opacity="0.26">
                    {[28, 72, 116, 160, 204].map((y) => (
                      <line key={y} x1="0" x2="500" y1={y} y2={y} stroke="rgba(148,163,184,0.14)" />
                    ))}
                    {[60, 160, 260, 360, 460].map((x) => (
                      <line key={x} x1={x} x2={x} y1="18" y2="206" stroke="rgba(148,163,184,0.1)" />
                    ))}
                  </g>

                  <path
                    d={`${activeRoadmapPath} L 500 208 L 0 208 Z`}
                    fill="url(#roadmapPulseFill)"
                  />
                  <path
                    d={activeRoadmapPath}
                    fill="none"
                    stroke="url(#roadmapPulseLine)"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />

                  {activeRoadmapTrack.pulse.map((point, index) => {
                    const max = Math.max(...activeRoadmapTrack.pulse);
                    const min = Math.min(...activeRoadmapTrack.pulse);
                    const normalized = max === min ? 0.5 : (point - min) / (max - min);
                    const x = index * (500 / (activeRoadmapTrack.pulse.length - 1));
                    const y = 180 - normalized * 180 + 14;
                    const isLast = index === activeRoadmapTrack.pulse.length - 1;
                    return (
                      <g key={`${activeRoadmapTrack.id}-${point}-${index}`}>
                        <circle
                          cx={x}
                          cy={y}
                          r={isLast ? 6 : 4}
                          fill={isLast ? '#34d399' : '#22d3ee'}
                          className={isLast ? 'animate-pulse' : ''}
                        />
                      </g>
                    );
                  })}
                </svg>
              </div>

              <div className="mt-4 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-white">Hover insight</span>
                  <span className="text-xs uppercase tracking-[0.2em] text-cyan-200/80">
                    {hoveredRoadmapMetric ? 'Metric detail' : 'Track detail'}
                  </span>
                </div>
                <p className="mt-2 leading-6">{hoveredRoadmapMetric || activeRoadmapDetails[0]}</p>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-4">
                {activeRoadmapTrack.pulse.map((value, index) => {
                  const detail = activeRoadmapDetails[index % activeRoadmapDetails.length];
                  return (
                    <div
                      key={`${activeRoadmapTrack.id}-metric-${index}`}
                      className="rounded-2xl border border-slate-700/70 bg-slate-900/80 px-4 py-4"
                      onMouseEnter={() => setHoveredRoadmapMetric(detail)}
                      onMouseLeave={() => setHoveredRoadmapMetric(null)}
                    >
                      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">
                        Signal {String(index + 1).padStart(2, '0')}
                      </p>
                      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
                      <p className="mt-2 text-xs leading-5 text-slate-400">{detail}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </MotionReveal>
        </section>

        <section className="public-modern-container public-proof-strip">
          {proofItems.map(([title, body], index) => (
            <MotionReveal key={title} className="public-proof-item" delayMs={index * 60}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{title}</strong>
              <p>{body}</p>
            </MotionReveal>
          ))}
        </section>

        <section className="public-modern-container public-proof-strip">
          {trustItems.map(([title, body], index) => (
            <MotionReveal key={title} className="public-proof-item" delayMs={index * 60}>
              <span>T{String(index + 1).padStart(2, '0')}</span>
              <strong>{title}</strong>
              <p>{body}</p>
            </MotionReveal>
          ))}
        </section>

        <section className="public-modern-container public-market-section">
          <MotionReveal distancePx={18}>
            <PublicMarketPulsePanel
              eyebrow="Market intelligence"
              title="Scope, build, test, and launch readiness stay close to every execution decision."
              description="Compare market context, validation quality, and runtime readiness before a strategy moves toward live execution."
            />
          </MotionReveal>
        </section>

        <section className="public-modern-band">
          <div className="public-modern-container public-modern-split">
            <MotionReveal className="public-modern-section-copy" distancePx={18}>
              <div className="surface-label">Evaluation path</div>
              <h2>Move from market signal to controlled runtime without losing context.</h2>
              <p>
                The experience matches the ExecutionLab promise: research, account readiness,
                strategy validation, bot operations, and admin control sit in one intentional
                journey.
              </p>
            </MotionReveal>

            <div className="public-capability-grid">
              {pathItems.map(([Icon, title, body], index) => (
                <MotionReveal
                  key={title}
                  className="public-capability-card landing-modern-card"
                  delayMs={index * 70}
                >
                  <Icon className="landing-modern-icon" />
                  <span>Step {String(index + 1).padStart(2, '0')}</span>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </MotionReveal>
              ))}
            </div>
          </div>
        </section>

        <section className="public-modern-container public-outcome-stage">
          <MotionReveal className="public-modern-section-copy" distancePx={18}>
            <div className="surface-label">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Product promise
            </div>
            <h2>Confidence before deployment. Clarity after every runtime change.</h2>
            <p>
              Each surface helps serious DeFi operators understand evidence, access, and action
              priority without feeling like they entered a disconnected portal.
            </p>
          </MotionReveal>

          <div className="public-outcome-grid">
            {valueItems.map(([Icon, title, body], index) => (
              <MotionReveal
                key={title}
                className="public-outcome-modern landing-modern-card"
                delayMs={index * 70}
              >
                <Icon className="landing-modern-icon" />
                <span>Outcome {String(index + 1).padStart(2, '0')}</span>
                <strong>{title}</strong>
                <p>{body}</p>
              </MotionReveal>
            ))}
          </div>
        </section>

        <section className="public-modern-container public-modern-cta">
          <MotionReveal className="public-modern-cta-inner" distancePx={18}>
            <div>
              <div className="surface-label">
                <ShieldCheck className="h-4 w-4" />
                Ready for execution review
              </div>
              <h2>Start with context. Continue into disciplined DeFi execution.</h2>
              <p>
                Review access options, align on security expectations, and complete onboarding
                before backtests, runtime workflows, or partner operations begin.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                to="/register"
                className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3 text-sm font-semibold text-white"
              >
                Request platform access
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/services/security"
                className="premium-button premium-button-secondary justify-center px-6 py-3 text-sm font-medium"
              >
                Review security
              </Link>
            </div>
          </MotionReveal>
        </section>

        <section className="public-modern-container public-outcome-stage">
          <MotionReveal className="public-modern-section-copy" distancePx={18}>
            <div className="surface-label">Risk disclosure</div>
            <h2>Clear risk language before execution begins.</h2>
            <p>
              We keep expectations explicit so operators can evaluate execution quality, risk
              posture, and runtime readiness with no hidden assumptions.
            </p>
          </MotionReveal>

          <div className="public-outcome-grid">
            {riskItems.map((item, index) => (
              <MotionReveal key={item} className="public-outcome-modern" delayMs={index * 70}>
                <span>Disclosure {String(index + 1).padStart(2, '0')}</span>
                <p>{item}</p>
              </MotionReveal>
            ))}
          </div>
        </section>
      </div>
    </PublicSiteShell>
  );
};

export default LandingPage;
