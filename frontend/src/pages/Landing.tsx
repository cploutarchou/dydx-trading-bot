import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ShieldCheck,
  Sparkles,
  Target,
  Waves,
  Zap,
} from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import PublicSiteShell from '../components/PublicSiteShell';

const pillars = [
  {
    icon: BrainCircuit,
    title: 'Quant Research',
    description:
      'Explore pair relationships, rank backtests, and inspect risk-adjusted performance before capital touches the market.',
  },
  {
    icon: Bot,
    title: 'Live Operations',
    description:
      'Run bot instances, monitor runtime health, and observe execution telemetry from a websocket-first control surface.',
  },
  {
    icon: Waves,
    title: 'Realtime Insight',
    description:
      'Backtest progress, activity logs, runtime stats, and market context stream into the UI without hard refreshes.',
  },
  {
    icon: ShieldCheck,
    title: 'Operator Trust',
    description:
      'Structured auth flows, 2FA onboarding, and production-minded UX patterns reduce friction where mistakes cost money.',
  },
];

const plans = [
  {
    name: 'Explorer',
    price: '$0',
    description: 'For evaluating the platform and validating a small research workflow.',
    bullets: ['Evaluation workspace', 'Historical backtests', 'Foundational market intel'],
  },
  {
    name: 'Performance',
    price: '12% profit share',
    description: 'For solo operators and small teams who prefer fees only when the platform delivers upside.',
    bullets: ['No flat platform fee', 'Live bot control', 'Premium research cockpit'],
    featured: true,
  },
  {
    name: 'Desk',
    price: 'Custom success fee',
    description: 'For serious teams that need tailored rollout, controls, and negotiated economics.',
    bullets: ['Multi-operator workflow', 'White-glove onboarding', 'Negotiated success-fee support'],
  },
];

const faqs = [
  {
    q: 'Is this just a dashboard?',
    a: 'No. The platform combines product-facing onboarding with a real operator cockpit for research, live execution, and runtime management.',
  },
  {
    q: 'Can users start with research before going live?',
    a: 'Yes. The UX is designed so teams can move from intelligence and backtests into bot execution without switching tools.',
  },
  {
    q: 'Why position this around DeFi arbitrage?',
    a: 'Because latency, state visibility, and signal trust matter more in arbitrage than in generic retail trading products, and the UX should reflect that.',
  },
];

export const LandingPage: React.FC = () => {
  return (
    <PublicSiteShell>
      <section className="mx-auto max-w-7xl px-4 pb-16 pt-16 sm:px-6 lg:px-8 lg:pb-24 lg:pt-20">
        <div className="premium-hero px-6 py-8 sm:px-10 sm:py-12">
          <div className="grid gap-10 xl:grid-cols-[1.15fr,0.85fr] xl:items-end">
            <div className="relative z-10">
              <div className="premium-kicker">
                <Sparkles className="h-3.5 w-3.5" />
                Production-Ready DeFi Arbitrage Platform
              </div>
              <h1 className="mt-6 max-w-4xl text-4xl font-bold leading-[1.05] text-white sm:text-6xl">
                The operating system for research, execution, and confidence in dYdX arbitrage.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
                Move from idea to live runtime with one premium workflow: strategy intelligence,
                backtests, live bot management, runtime telemetry, and market context designed for
                teams trading serious capital in DeFi.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link
                  to="/register"
                  className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-cyan-500 to-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:brightness-105"
                >
                  Start evaluation
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/pricing"
                  className="rounded-2xl border border-slate-700 bg-slate-950/80 px-5 py-3 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:text-white"
                >
                  Explore subscriptions
                </Link>
              </div>
              <div className="mt-8 flex flex-wrap gap-3 text-sm text-slate-400">
                <span className="rounded-full border border-slate-800 bg-slate-950/70 px-3 py-1.5">
                  Websocket-first live UX
                </span>
                <span className="rounded-full border border-slate-800 bg-slate-950/70 px-3 py-1.5">
                  Premium backtest intelligence
                </span>
                <span className="rounded-full border border-slate-800 bg-slate-950/70 px-3 py-1.5">
                  Operator-grade auth and runtime flows
                </span>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-[1.75rem] border border-slate-800 bg-slate-950/65 p-5 sm:col-span-2">
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Platform Value</p>
                <p className="mt-3 text-2xl font-semibold text-white">
                  Built for teams who need their UI to think like an operator.
                </p>
              </div>
              <div className="rounded-[1.75rem] border border-slate-800 bg-slate-950/65 p-5">
                <div className="rounded-2xl bg-cyan-500/10 p-3 text-cyan-300 w-fit">
                  <Target className="h-5 w-5" />
                </div>
                <p className="mt-4 text-lg font-semibold text-white">Research to runtime</p>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  No fragmented workflow between strategy discovery, testing, and live bot control.
                </p>
              </div>
              <div className="rounded-[1.75rem] border border-slate-800 bg-slate-950/65 p-5">
                <div className="rounded-2xl bg-emerald-500/10 p-3 text-emerald-300 w-fit">
                  <Zap className="h-5 w-5" />
                </div>
                <p className="mt-4 text-lg font-semibold text-white">Live-state aware</p>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  Streaming progress, execution context, and sync health stay visible where decisions happen.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="platform" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="mb-8 max-w-2xl">
          <div className="premium-kicker">Platform</div>
          <h2 className="mt-4 text-3xl font-bold text-white sm:text-4xl">
            A workflow built around how DeFi arbitrage desks actually operate.
          </h2>
          <p className="mt-4 text-base leading-7 text-slate-400">
            The website and product should work together: explain the value clearly, then move the
            user into a premium runtime where data density, latency, and trust are first-class.
          </p>
        </div>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {pillars.map((pillar) => {
            const Icon = pillar.icon;
            return (
              <div key={pillar.title} className="rounded-[1.75rem] border border-slate-800 bg-slate-900/70 p-6">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/75 p-3 text-cyan-200 w-fit">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-5 text-xl font-semibold text-white">{pillar.title}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-400">{pillar.description}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section id="why" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
          <div className="rounded-[2rem] border border-slate-800 bg-slate-900/70 p-8">
            <div className="premium-kicker">Why Teams Switch</div>
            <h2 className="mt-4 text-3xl font-bold text-white">Most products stop at charts. Operators need decisions.</h2>
            <div className="mt-6 space-y-4 text-sm text-slate-300">
              {[
                'See which strategies are actually robust instead of drowning in disconnected run logs.',
                'Understand runtime health and execution state without babysitting multiple tools.',
                'Move from polished product marketing into an auth flow and workspace that feels equally premium.',
              ].map((line) => (
                <div key={line} className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-300" />
                  <p className="leading-7">{line}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-slate-800 bg-slate-950/75 p-8">
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">What Users Feel</p>
            <div className="mt-6 space-y-4">
              {[
                ['Clarity', 'The platform explains why strategies matter before asking users to trust a live runtime.'],
                ['Control', 'Once inside, the product feels like an operating desk, not a brochure or an admin panel.'],
                ['Confidence', 'Streaming telemetry, detailed tables, and premium UX reduce hesitation at every step.'],
              ].map(([title, body]) => (
                <div key={title} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                  <p className="text-lg font-semibold text-white">{title}</p>
                  <p className="mt-2 text-sm leading-7 text-slate-400">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="premium-kicker">Subscriptions</div>
            <h2 className="mt-4 text-3xl font-bold text-white">Fee models that align with trading outcomes.</h2>
          </div>
          <Link to="/pricing" className="inline-flex items-center gap-2 text-sm font-medium text-cyan-300 hover:text-cyan-200">
            See full pricing details
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="grid gap-5 lg:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`rounded-[2rem] border p-6 ${
                plan.featured
                  ? 'border-cyan-500/35 bg-[linear-gradient(180deg,rgba(8,145,178,0.18),rgba(10,15,28,0.92))]'
                  : 'border-slate-800 bg-slate-900/70'
              }`}
            >
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{plan.name}</p>
              <p className="mt-4 text-4xl font-semibold text-white">{plan.price}</p>
              <p className="mt-3 text-sm leading-7 text-slate-400">{plan.description}</p>
              <div className="mt-6 space-y-3">
                {plan.bullets.map((bullet) => (
                  <div key={bullet} className="flex items-start gap-3 text-sm text-slate-300">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                    <span>{bullet}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="faq" className="mx-auto max-w-5xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="premium-kicker">FAQ</div>
        <h2 className="mt-4 text-3xl font-bold text-white">Questions users ask before they trust a trading platform.</h2>
        <div className="mt-8 space-y-4">
          {faqs.map((faq) => (
            <div key={faq.q} className="rounded-[1.75rem] border border-slate-800 bg-slate-900/70 p-6">
              <p className="text-lg font-semibold text-white">{faq.q}</p>
              <p className="mt-3 text-sm leading-7 text-slate-400">{faq.a}</p>
            </div>
          ))}
        </div>
      </section>
    </PublicSiteShell>
  );
};

export default LandingPage;
