import {
  Activity,
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Command,
  Radar,
  ShieldCheck,
  Sparkles,
  Waves,
} from 'lucide-react';
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { DeFiHeroIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import PublicSiteShell from '../components/PublicSiteShell';

const heroStats = [
  ['Realtime', 'stream-first control surfaces', 'designed to update without losing operator context'],
  ['12%', 'performance-aligned commercial model', 'clear economics that match delivered upside'],
  ['24/7', 'runtime visibility posture', 'health, sync state, and execution awareness stay visible'],
  ['Role-based', 'workspace governance', 'clear separation between operators, admins, and backoffice'],
];

const platformPillars = [
  {
    icon: BrainCircuit,
    title: 'Research cockpit',
    description:
      'Run comparative backtests, inspect signal quality, and identify which strategies deserve confidence before going live.',
  },
  {
    icon: Waves,
    title: 'Live-state awareness',
    description:
      'Stream progress, health, and runtime status in place so the workspace feels stable under live updates.',
  },
  {
    icon: Bot,
    title: 'Execution controls',
    description:
      'Manage bots, strategy runtime, and backtests from one operator-first shell with faster route jumping and clearer hierarchy.',
  },
  {
    icon: ShieldCheck,
    title: 'Trust semantics',
    description:
      'Security posture, access state, and workflow readiness are surfaced like product features instead of buried utilities.',
  },
];

const workflowStages = [
  {
    label: '01',
    title: 'Model the opportunity',
    description:
      'Move from market thesis into backtests quickly, compare setups, and understand if the edge survives more than one lucky run.',
  },
  {
    label: '02',
    title: 'Pressure-test the strategy',
    description:
      'Review PnL shape, drawdown discipline, run health, and trade detail from dense but readable fintech-grade surfaces.',
  },
  {
    label: '03',
    title: 'Operate live with confidence',
    description:
      'Promote into runtime, monitor execution state, and keep command surfaces close to navigation and context.',
  },
];

const standards = [
  {
    title: 'Stable live updates',
    body: 'Data should refresh softly in place, not wipe out already-rendered context with heavy spinners.',
  },
  {
    title: 'Signal-rich tables',
    body: 'Rows should expose a primary fact, a secondary context line, and consistent profit/loss semantics.',
  },
  {
    title: 'Operator-first navigation',
    body: 'Command palette access, grouped workflows, and visible environment context reduce movement cost.',
  },
];

const faqs = [
  {
    q: 'Is the product only for live trading teams?',
    a: 'No. The workflow is intentionally staged so teams can begin with research, validate quality, and then move into runtime with more confidence.',
  },
  {
    q: 'What makes the UX fintech-grade here?',
    a: 'Clear status semantics, denser information hierarchy, stable live updates, stronger security cues, and less separation between research and execution.',
  },
  {
    q: 'Why lead with a public site instead of sending users straight to auth?',
    a: 'Fintech trust starts before login. Pricing, product narrative, and onboarding have to explain the operating model before the user commits.',
  },
];

const tableRows = [
  ['Basis spread monitor', 'Healthy stream', '+4.8%', '0.82'],
  ['Funding divergence scan', 'Reconnecting', '+2.1%', '0.44'],
  ['Cross-market mean reversion', 'Ready', '+6.3%', '0.91'],
];

export const LandingPage: React.FC = () => {
  const [openFaq, setOpenFaq] = useState(0);

  return (
    <PublicSiteShell>
      <section className="public-shell-container relative pt-10 sm:pt-12 lg:pt-14">
        <div className="premium-orb -left-6 top-16 h-40 w-40 bg-cyan-400/16" />
        <div
          className="premium-orb right-8 top-8 h-48 w-48 bg-blue-500/14"
          style={{ animationDelay: '1.3s' }}
        />

        <MotionReveal className="relative">
          <div className="premium-hero px-6 py-8 sm:px-8 sm:py-10 xl:px-12 xl:py-12">
            <div className="grid gap-10 xl:grid-cols-[0.95fr,1.05fr] xl:items-center">
              <div className="relative z-10">
                <div className="surface-label">
                  <Radar className="h-3.5 w-3.5" />
                  Fintech-grade DeFi operator experience
                </div>
                <h1 className="mt-6 max-w-4xl text-4xl font-bold leading-[0.98] text-white sm:text-5xl xl:text-[4.65rem]">
                  One platform for research conviction, runtime clarity, and premium trading UX.
                </h1>
                <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
                  dYdX Arbitrage OS is designed like a serious operator product: strong public-site
                  trust, cleaner onboarding, signal-rich dashboards, and realtime execution context
                  that stays stable while you work.
                </p>

                <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                  <Link
                    to="/register"
                    className="premium-button premium-button-primary min-w-[13rem] justify-center rounded-[1.3rem] px-6 py-3.5 text-sm font-semibold text-white"
                  >
                    Start evaluation
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    to="/pricing"
                    className="premium-button premium-button-secondary min-w-[13rem] justify-center rounded-[1.3rem] px-6 py-3.5 text-sm font-medium"
                  >
                    Review pricing
                  </Link>
                </div>

                <div className="mt-8 flex flex-wrap gap-3">
                  {[
                    'Command-palette navigation',
                    'Security-aware onboarding',
                    'Live-state visibility without reset behavior',
                  ].map((item) => (
                    <div key={item} className="data-chip">
                      <span className="h-2 w-2 rounded-full bg-cyan-300" />
                      {item}
                    </div>
                  ))}
                </div>
              </div>

              <div className="relative">
                <div className="market-illustration-shell p-3 sm:p-4">
                  <DeFiHeroIllustration />
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-[1.1fr,0.9fr]">
                  <div className="signal-card signal-card-strong px-5 py-5">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                          Workspace pulse
                        </p>
                        <p className="mt-2 text-xl font-semibold text-white">
                          Research and runtime should feel like one continuous system.
                        </p>
                      </div>
                      <div className="rounded-2xl bg-cyan-500/10 p-3 text-cyan-300">
                        <Activity className="h-5 w-5" />
                      </div>
                    </div>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                      <div className="metric-tile px-4 py-4">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                          Sync state
                        </p>
                        <p className="mt-2 text-sm font-semibold text-emerald-300">Healthy stream</p>
                      </div>
                      <div className="metric-tile px-4 py-4">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                          Last update
                        </p>
                        <p className="mt-2 text-sm font-semibold text-cyan-300">Live, under 1s</p>
                      </div>
                    </div>
                  </div>

                  <div className="signal-card px-5 py-5">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      Design intent
                    </p>
                    <div className="mt-4 space-y-3">
                      {standards.map((item) => (
                        <div key={item.title} className="rounded-2xl border border-slate-800/80 bg-slate-950/55 px-4 py-3">
                          <p className="text-sm font-semibold text-white">{item.title}</p>
                          <p className="mt-1 text-sm leading-6 text-slate-400">{item.body}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </MotionReveal>
      </section>

      <section className="public-shell-container py-8 sm:py-10">
        <div className="grid gap-4 lg:grid-cols-4">
          {heroStats.map(([value, title, body], index) => (
            <MotionReveal key={title} delayMs={index * 60} className="metric-tile px-5 py-5">
              <p className="text-3xl font-bold text-white">{value}</p>
              <p className="mt-2 text-sm font-semibold text-slate-200">{title}</p>
              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">{body}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section id="platform" className="public-shell-container py-16">
        <div className="grid gap-6 xl:grid-cols-[0.86fr,1.14fr]">
          <MotionReveal className="editorial-band pr-4 lg:pr-10">
            <div className="surface-label">
              <Sparkles className="h-3.5 w-3.5" />
              Platform pillars
            </div>
            <h2 className="mt-5 text-3xl font-bold text-white sm:text-4xl">
              The frontend should make operators faster, calmer, and more informed.
            </h2>
            <p className="mt-5 max-w-xl text-base leading-8 text-slate-300">
              That means better hierarchy, stronger status semantics, fintech-grade copy, and
              layouts that explain the product before the user ever enters the workspace.
            </p>
            <div className="mt-8 space-y-4">
              {[
                'Premium public pages that explain the operating model before auth.',
                'Authentication screens that reinforce security and next-step clarity.',
                'Operator chrome that keeps command surfaces, environment, and navigation visible.',
              ].map((line) => (
                <div key={line} className="flex items-start gap-3 text-sm text-slate-300">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                  <span className="leading-7">{line}</span>
                </div>
              ))}
            </div>
          </MotionReveal>

          <div className="grid gap-5 md:grid-cols-2">
            {platformPillars.map((pillar, index) => {
              const Icon = pillar.icon;
              return (
                <MotionReveal key={pillar.title} delayMs={index * 70} className="signal-card px-6 py-6">
                  <div className="w-fit rounded-[1.1rem] border border-slate-800 bg-slate-950/80 p-3 text-cyan-200">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-5 text-xl font-semibold text-white">{pillar.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-slate-400">{pillar.description}</p>
                </MotionReveal>
              );
            })}
          </div>
        </div>
      </section>

      <section id="workflow" className="public-shell-container py-16">
        <MotionReveal className="mb-8">
          <div className="surface-label">
            <Command className="h-3.5 w-3.5" />
            Workflow
          </div>
          <h2 className="mt-4 max-w-3xl text-3xl font-bold text-white sm:text-4xl">
            A product flow shaped around how a trading desk actually works.
          </h2>
        </MotionReveal>
        <div className="grid gap-5 lg:grid-cols-3">
          {workflowStages.map((item, index) => (
            <MotionReveal key={item.label} delayMs={index * 80} className="signal-card px-6 py-6">
              <div className="inline-flex rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-200">
                Step {item.label}
              </div>
              <h3 className="mt-5 text-2xl font-semibold text-white">{item.title}</h3>
              <p className="mt-4 text-sm leading-7 text-slate-400">{item.description}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="public-shell-container py-16">
        <div className="grid gap-6 xl:grid-cols-[1fr,0.95fr]">
          <MotionReveal className="signal-card signal-card-strong px-6 py-6 sm:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="surface-label">
                  <Activity className="h-3.5 w-3.5" />
                  Control-room preview
                </div>
                <h2 className="mt-4 max-w-2xl text-3xl font-bold text-white">
                  More terminal-grade signal, less generic admin clutter.
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
                  Tables, panels, and status chips should immediately explain what is healthy,
                  what is changing, and what needs operator attention.
                </p>
              </div>
              <div className="hidden rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 lg:block">
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Last updated</p>
                <p className="mt-1 text-sm font-semibold text-cyan-300">Live stream active</p>
              </div>
            </div>

            <div className="table-preview mt-6">
              <div className="table-preview-row bg-slate-950/82 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                <span>Strategy</span>
                <span>Status</span>
                <span>Return</span>
                <span>Sharpe</span>
              </div>
              {tableRows.map((row, index) => (
                <div
                  key={row[0]}
                  className={`table-preview-row text-sm ${index % 2 === 0 ? 'bg-slate-950/34' : 'bg-slate-900/28'}`}
                >
                  <div>
                    <p className="font-medium text-white">{row[0]}</p>
                    <p className="mt-1 text-xs text-slate-500">Primary metric with supporting context</p>
                  </div>
                  <span
                    className={`font-medium ${
                      row[1] === 'Healthy stream'
                        ? 'text-emerald-300'
                        : row[1] === 'Reconnecting'
                          ? 'text-amber-300'
                          : 'text-cyan-300'
                    }`}
                  >
                    {row[1]}
                  </span>
                  <span className="font-semibold text-emerald-300">{row[2]}</span>
                  <span className="font-medium text-slate-200">{row[3]}</span>
                </div>
              ))}
            </div>
          </MotionReveal>

          <div className="grid gap-5">
            {[
              {
                title: 'Navigation built for operators',
                body: 'Grouped workflows, a global command palette, and visible environment context make movement cheaper.',
              },
              {
                title: 'Public copy that earns trust',
                body: 'Messaging should describe how the product operates, not lean on generic crypto hype or vague SaaS language.',
              },
              {
                title: 'Auth that feels premium',
                body: 'Login and registration should explain access state, security posture, and what comes next.',
              },
            ].map((item, index) => (
              <MotionReveal key={item.title} delayMs={index * 80} className="signal-card px-6 py-6">
                <p className="text-lg font-semibold text-white">{item.title}</p>
                <p className="mt-3 text-sm leading-7 text-slate-400">{item.body}</p>
              </MotionReveal>
            ))}
          </div>
        </div>
      </section>

      <section id="security" className="public-shell-container py-16">
        <div className="grid gap-6 xl:grid-cols-[0.9fr,1.1fr]">
          <MotionReveal className="editorial-band pr-4 lg:pr-10">
            <div className="surface-label">
              <ShieldCheck className="h-3.5 w-3.5" />
              Security and trust
            </div>
            <h2 className="mt-5 text-3xl font-bold text-white sm:text-4xl">
              Trust is a UX requirement in fintech, not a marketing subsection.
            </h2>
            <p className="mt-5 max-w-xl text-base leading-8 text-slate-300">
              Users should understand access state, onboarding posture, and readiness for live
              operation without reading docs or guessing what happens next.
            </p>
          </MotionReveal>

          <div className="grid gap-5 md:grid-cols-2">
            {[
              ['Security-aware onboarding', 'Login and registration explicitly explain invitation status, account readiness, and next steps.'],
              ['Role-sensitive workspace', 'Navigation and controls are grouped by workflow and filtered by operator responsibility.'],
              ['Live-state semantics', 'Healthy, reconnecting, degraded, and active states use predictable color and copy patterns.'],
              ['Consistent CTA strategy', 'Public pages lead into evaluation, pricing, or sign-in without forcing users through unclear paths.'],
            ].map(([title, body], index) => (
              <MotionReveal key={title} delayMs={index * 70} className="signal-card px-6 py-6">
                <p className="text-lg font-semibold text-white">{title}</p>
                <p className="mt-3 text-sm leading-7 text-slate-400">{body}</p>
              </MotionReveal>
            ))}
          </div>
        </div>
      </section>

      <section id="faq" className="public-shell-container pb-24 pt-10">
        <MotionReveal className="mb-8">
          <div className="surface-label">
            <ChevronDown className="h-3.5 w-3.5" />
            FAQ
          </div>
          <h2 className="mt-4 max-w-3xl text-3xl font-bold text-white sm:text-4xl">
            Clear answers before the user commits to the workspace.
          </h2>
        </MotionReveal>

        <div className="grid gap-4 lg:grid-cols-[0.95fr,1.05fr]">
          <MotionReveal className="signal-card signal-card-strong px-6 py-6">
            <h3 className="text-2xl font-semibold text-white">Start with trust, then prove speed.</h3>
            <p className="mt-3 text-sm leading-7 text-slate-300">
              The strongest fintech products do both: they make the model understandable and the
              operator workflow feel obviously competent.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/register"
                className="premium-button premium-button-primary justify-center rounded-[1.3rem] px-6 py-3.5 text-sm font-semibold text-white"
              >
                Enter evaluation
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/pricing"
                className="premium-button premium-button-secondary justify-center rounded-[1.3rem] px-6 py-3.5 text-sm font-medium"
              >
                Explore subscriptions
              </Link>
            </div>
          </MotionReveal>

          <div className="space-y-4">
            {faqs.map((faq, index) => {
              const isOpen = openFaq === index;
              return (
                <MotionReveal key={faq.q} delayMs={index * 60}>
                  <button
                    type="button"
                    onClick={() => setOpenFaq(index)}
                    className="faq-card signal-card w-full px-6 py-5 text-left"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <p className="text-base font-semibold text-white">{faq.q}</p>
                      <ChevronDown
                        className={`h-5 w-5 text-slate-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                      />
                    </div>
                    <div className={`faq-answer mt-3 ${isOpen ? 'is-open' : ''}`}>
                      <div>
                        <p className="text-sm leading-7 text-slate-400">{faq.a}</p>
                      </div>
                    </div>
                  </button>
                </MotionReveal>
              );
            })}
          </div>
        </div>
      </section>
    </PublicSiteShell>
  );
};

export default LandingPage;
