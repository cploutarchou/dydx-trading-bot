import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Radio,
  ShieldCheck,
  Sparkles,
  Target,
  Waves,
  Zap,
} from 'lucide-react';
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { DeFiHeroIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import PublicSiteShell from '../components/PublicSiteShell';

const pillars = [
  {
    icon: BrainCircuit,
    title: 'Quant Research',
    description:
      'Rank opportunities, inspect robustness, and move from signal discovery to decision without leaving the product.',
  },
  {
    icon: Bot,
    title: 'Live Operations',
    description:
      'Control runtimes, recover state, and stay aware of execution conditions from one operator surface.',
  },
  {
    icon: Waves,
    title: 'Realtime Insight',
    description:
      'Stream progress, runtime health, and strategy state over websocket-first interfaces that feel alive.',
  },
  {
    icon: ShieldCheck,
    title: 'Operator Trust',
    description:
      'Security posture, auth flow quality, and runtime visibility are treated as product features, not afterthoughts.',
  },
];

const operatingLoop = [
  {
    step: '01',
    title: 'Research the spread',
    description:
      'Profile candidate pairs, compare backtests, and identify where the edge is persistent enough to deserve capital.',
  },
  {
    step: '02',
    title: 'Validate under pressure',
    description:
      'Inspect live progress, trade detail, PnL shape, and risk-adjusted outcomes before anything goes into production.',
  },
  {
    step: '03',
    title: 'Operate with conviction',
    description:
      'Promote strategies into runtime, monitor health, and react from one command surface built around state clarity.',
  },
];

const plans = [
  {
    name: 'Explorer',
    price: '$0',
    description: 'Evaluate the platform and validate a focused research workflow before turning on any economics.',
    bullets: ['Evaluation workspace', 'Historical backtests', 'Foundational market intel'],
  },
  {
    name: 'Performance',
    price: '12% profit share',
    description:
      'For solo operators and lean teams who want the platform economics aligned to actual delivered upside.',
    bullets: ['No flat platform fee', 'Live bot control', 'Premium research cockpit'],
    featured: true,
  },
  {
    name: 'Desk',
    price: 'Custom success fee',
    description:
      'For teams that need negotiated onboarding, tailored workflows, and deeper operational support.',
    bullets: ['Multi-operator workflow', 'White-glove onboarding', 'Negotiated success-fee support'],
  },
];

const faqs = [
  {
    q: 'Is this just a dashboard?',
    a: 'No. It is meant to behave like a trading operating system: product-grade onboarding outside, dense execution-grade control inside.',
  },
  {
    q: 'Can users start with research before going live?',
    a: 'Yes. The workflow is intentionally staged so teams can validate strategy quality first, then activate runtime operations with confidence.',
  },
  {
    q: 'Why center the product around DeFi arbitrage?',
    a: 'Because arbitrage workflows demand more than charts: latency awareness, runtime trust, and strong state visibility are product-critical.',
  },
];

const telemetryTape = [
  'Realtime runtime telemetry',
  'Backtests with live progress',
  'Profit-share aligned pricing',
  'Operator-grade authentication',
  'Research to runtime workflow',
];

const statTiles = [
  ['14', 'live operator surfaces', 'research, runtime, and command flows'],
  ['99.94%', 'execution health target', 'designed around production confidence'],
  ['12%', 'performance package', 'aligned to net realized upside'],
  ['24/7', 'state visibility', 'stream-first UX across critical workflows'],
];

export const LandingPage: React.FC = () => {
  const [openFaq, setOpenFaq] = useState(0);

  return (
    <PublicSiteShell>
      <section className="public-shell-container relative pt-10 sm:pt-12 lg:pt-14">
        <div className="premium-orb -left-6 top-16 h-40 w-40 bg-cyan-400/16" />
        <div className="premium-orb right-8 top-8 h-48 w-48 bg-blue-500/14" style={{ animationDelay: '1.3s' }} />
        <MotionReveal className="relative">
          <div className="grid gap-12 xl:grid-cols-[0.92fr,1.08fr] xl:items-center">
            <div className="relative z-10">
              <div className="premium-kicker">
                <Sparkles className="h-3.5 w-3.5" />
                Production-Ready DeFi Arbitrage Platform
              </div>
              <h1 className="mt-6 max-w-4xl text-4xl font-bold leading-[0.98] text-white sm:text-5xl xl:text-[4.75rem]">
                Research the edge. Validate the thesis. Run the strategy from one product.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
                dYdX Arbitrage OS gives serious operators a single environment for quant research,
                backtesting, live bot orchestration, runtime telemetry, and high-signal decision support.
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
                  Explore subscriptions
                </Link>
              </div>

              <div className="mt-8 flex flex-wrap gap-3 text-sm text-slate-400">
                {[
                  'Websocket-first live UX',
                  'Interactive backtest intelligence',
                  'Operator-grade runtime flows',
                ].map((item) => (
                  <span
                    key={item}
                    className="rounded-full border border-slate-800/80 bg-slate-950/55 px-3 py-1.5"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>

            <div className="relative">
              <div className="market-illustration-shell p-3 sm:p-4">
                <DeFiHeroIllustration />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="micro-panel p-5">
                  <div className="flex items-center gap-3 text-cyan-300">
                    <div className="rounded-xl bg-cyan-500/10 p-2.5">
                      <Target className="h-4 w-4" />
                    </div>
                    <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Research to Runtime
                    </span>
                  </div>
                  <p className="mt-4 text-lg font-semibold text-white">
                    The workflow is continuous, not split across different tools.
                  </p>
                </div>
                <div className="micro-panel p-5">
                  <div className="flex items-center gap-3 text-emerald-300">
                    <div className="rounded-xl bg-emerald-500/10 p-2.5">
                      <Zap className="h-4 w-4" />
                    </div>
                    <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Live-State Aware
                    </span>
                  </div>
                  <p className="mt-4 text-lg font-semibold text-white">
                    Critical telemetry stays visible while the operator is making decisions.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="editorial-band mt-10">
            <div className="mb-3 inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
              <Radio className="h-3.5 w-3.5 text-cyan-300" />
              Live operator tape
            </div>
            <div className="telemetry-marquee">
              <div className="telemetry-marquee-track">
                {[...telemetryTape, ...telemetryTape].map((item, index) => (
                  <div key={`${item}-${index}`} className="telemetry-chip">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    <span>{item}</span>
                    <strong>active</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </MotionReveal>
      </section>

      <section className="public-shell-container py-8 sm:py-10">
        <div className="grid gap-4 lg:grid-cols-4">
          {statTiles.map(([value, title, body], index) => (
            <MotionReveal
              key={title}
              delayMs={index * 60}
              className="rounded-[1.6rem] border border-slate-800/70 bg-slate-950/45 px-5 py-5"
            >
              <p className="text-3xl font-bold text-white">{value}</p>
              <p className="mt-2 text-sm font-semibold text-slate-200">{title}</p>
              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">{body}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section id="platform" className="public-shell-container py-16">
        <div className="grid gap-6 xl:grid-cols-[0.88fr,1.12fr]">
          <MotionReveal className="editorial-band pr-4 lg:pr-10">
            <div className="premium-kicker">Platform</div>
            <h2 className="mt-5 text-3xl font-bold text-white sm:text-4xl">
              A workflow built around how DeFi arbitrage desks actually operate.
            </h2>
            <p className="mt-5 max-w-xl text-base leading-8 text-slate-300">
              The public site should create trust, but the product itself has to carry the real weight:
              signal discovery, validation, runtime control, and state clarity under pressure.
            </p>
            <div className="mt-8 space-y-4">
              {[
                'See the whole path from research to runtime, not disconnected product fragments.',
                'Feel latency awareness and telemetry density in the UX before the user even logs in.',
                'Reduce the confidence gap between marketing promise and operational reality.',
              ].map((line) => (
                <div key={line} className="flex items-start gap-3 text-sm text-slate-300">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                  <span className="leading-7">{line}</span>
                </div>
              ))}
            </div>
          </MotionReveal>

          <div className="grid gap-5 md:grid-cols-2">
            {pillars.map((pillar, index) => {
              const Icon = pillar.icon;
              return (
                <MotionReveal
                  key={pillar.title}
                  delayMs={index * 70}
                  className="micro-panel p-6"
                >
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

      <section className="public-shell-container py-16">
        <MotionReveal className="mb-8">
          <div className="premium-kicker">Operating Loop</div>
          <h2 className="mt-4 max-w-3xl text-3xl font-bold text-white sm:text-4xl">
            A product flow that mirrors the operator decision cycle.
          </h2>
        </MotionReveal>
        <div className="grid gap-5 lg:grid-cols-3">
          {operatingLoop.map((item, index) => (
            <MotionReveal
              key={item.step}
              delayMs={index * 80}
              className="micro-panel p-6"
            >
              <div className="inline-flex rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-200">
                Step {item.step}
              </div>
              <h3 className="mt-5 text-2xl font-semibold text-white">{item.title}</h3>
              <p className="mt-4 text-sm leading-7 text-slate-400">{item.description}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section id="why" className="public-shell-container py-16">
        <div className="grid gap-6 xl:grid-cols-[1fr,0.92fr]">
          <MotionReveal className="editorial-band pr-4 lg:pr-10">
            <div className="premium-kicker">Why Teams Switch</div>
            <h2 className="mt-5 text-3xl font-bold text-white sm:text-4xl">
              Most products stop at charts. Operators need decisions.
            </h2>
            <div className="mt-8 space-y-4">
              {[
                'Know which strategies are actually robust instead of drowning in fragmented backtest output.',
                'Understand runtime health and execution state without babysitting multiple disconnected surfaces.',
                'Move from polished product experience into an operator workspace that still feels intentional and premium.',
              ].map((line) => (
                <div key={line} className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-300" />
                  <p className="text-sm leading-7 text-slate-300">{line}</p>
                </div>
              ))}
            </div>
          </MotionReveal>

          <MotionReveal delayMs={120} className="editorial-band">
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">What Users Feel</p>
            <div className="mt-6 space-y-4">
              {[
                ['Clarity', 'The platform explains why a strategy matters before asking the operator to trust a live runtime.'],
                ['Control', 'Once inside, the product behaves like an execution environment, not an admin interface.'],
                ['Confidence', 'Streaming telemetry, dense data surfaces, and structured workflows reduce hesitation.'],
              ].map(([title, body]) => (
                <div key={title} className="micro-panel p-5">
                  <p className="text-lg font-semibold text-white">{title}</p>
                  <p className="mt-2 text-sm leading-7 text-slate-400">{body}</p>
                </div>
              ))}
            </div>
          </MotionReveal>
        </div>
      </section>

      <section className="public-shell-container py-16">
        <MotionReveal className="mb-8 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="premium-kicker">Subscriptions</div>
            <h2 className="mt-4 text-3xl font-bold text-white sm:text-4xl">
              Fee models that align with trading outcomes.
            </h2>
          </div>
          <Link to="/pricing" className="inline-flex items-center gap-2 text-sm font-medium text-cyan-300 hover:text-cyan-200">
            See full pricing details
            <ArrowRight className="h-4 w-4" />
          </Link>
        </MotionReveal>
        <div className="grid gap-5 lg:grid-cols-3">
          {plans.map((plan, index) => (
            <MotionReveal
              key={plan.name}
              delayMs={index * 90}
              className={`p-7 ${
                plan.featured
                  ? 'micro-panel micro-panel-strong'
                  : 'micro-panel'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{plan.name}</p>
                  <p className="mt-4 text-4xl font-semibold text-white">{plan.price}</p>
                </div>
                {plan.featured ? (
                  <div className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
                    Recommended
                  </div>
                ) : null}
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-400">{plan.description}</p>
              <div className="mt-6 space-y-3">
                {plan.bullets.map((bullet) => (
                  <div key={bullet} className="flex items-start gap-3 text-sm text-slate-300">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                    <span>{bullet}</span>
                  </div>
                ))}
              </div>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section id="faq" className="public-shell-container py-16">
        <div className="grid gap-8 xl:grid-cols-[0.78fr,1.22fr]">
          <MotionReveal>
            <div className="premium-kicker">FAQ</div>
            <h2 className="mt-4 text-3xl font-bold text-white sm:text-4xl">
              Questions users ask before they trust a trading platform.
            </h2>
            <p className="mt-4 max-w-xl text-base leading-8 text-slate-400">
              The public website needs to answer credibility questions quickly and then get out of the operator’s way.
            </p>
          </MotionReveal>

          <div className="space-y-4">
            {faqs.map((faq, index) => {
              const isOpen = openFaq === index;
              return (
                <MotionReveal
                  key={faq.q}
                  delayMs={index * 70}
                  className="faq-card micro-panel p-2"
                >
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-4 rounded-[1.2rem] px-4 py-4 text-left"
                    onClick={() => setOpenFaq(isOpen ? -1 : index)}
                    aria-expanded={isOpen}
                  >
                    <div>
                      <p className="text-lg font-semibold text-white">{faq.q}</p>
                      <p className="mt-1 text-sm text-slate-500">Trust, workflow quality, and execution readiness</p>
                    </div>
                    <ChevronDown
                      className={`h-5 w-5 shrink-0 text-slate-400 transition-transform duration-200 ${isOpen ? 'rotate-180 text-cyan-300' : ''}`}
                    />
                  </button>
                  <div className={`faq-answer px-4 pb-4 ${isOpen ? 'is-open' : ''}`}>
                    <div>
                      <p className="text-sm leading-7 text-slate-400">{faq.a}</p>
                    </div>
                  </div>
                </MotionReveal>
              );
            })}
          </div>
        </div>
      </section>

      <section className="public-shell-container pb-24 pt-6">
        <MotionReveal className="editorial-band overflow-hidden px-1 py-8 sm:px-2 lg:px-0">
          <div className="grid gap-8 lg:grid-cols-[1.15fr,0.85fr] lg:items-end">
            <div>
              <div className="premium-kicker">Launch</div>
              <h2 className="mt-4 max-w-3xl text-3xl font-bold text-white sm:text-4xl">
                Start with research clarity. Scale into live arbitrage when the edge is proven.
              </h2>
              <p className="mt-4 max-w-2xl text-base leading-8 text-slate-300">
                The website should feel like the first layer of the platform: confident, legible, and aligned with how the product actually behaves under load.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                ['Evaluation first', 'Explore the platform before any capital-linked fee is activated.'],
                ['Live-ready UX', 'Promote strategies into an operator cockpit built for state-aware execution.'],
              ].map(([title, body]) => (
                <div key={title} className="micro-panel p-5">
                  <p className="text-lg font-semibold text-white">{title}</p>
                  <p className="mt-2 text-sm leading-7 text-slate-400">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </MotionReveal>
      </section>
    </PublicSiteShell>
  );
};

export default LandingPage;
