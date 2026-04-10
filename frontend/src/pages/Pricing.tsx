import {
  ArrowRight,
  CheckCircle2,
  ShieldCheck,
  Sparkles,
  TimerReset,
  Waves,
} from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import { ProfitShareIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import PublicSiteShell from '../components/PublicSiteShell';

const plans = [
  {
    name: 'Explorer',
    price: '$0',
    cadence: 'evaluation access',
    description:
      'For teams that want to validate the operator flow, review the platform quality, and understand how the workspace behaves before economics begin.',
    features: [
      'Premium onboarding and account setup',
      'Historical backtests and workspace access',
      'Foundational market intelligence surfaces',
      'Single-operator evaluation posture',
    ],
    audience: 'Best for initial product evaluation',
  },
  {
    name: 'Performance',
    price: '12%',
    cadence: 'of net profit',
    description:
      'For serious solo traders and lean DeFi teams who want commercial terms aligned to live outcomes instead of fixed software rent.',
    features: [
      'Live bot control and runtime workflow',
      'Realtime status, stream health, and progress UX',
      'Signal-rich research and backtest views',
      'No flat recurring platform fee',
    ],
    audience: 'Best for active operators',
    featured: true,
  },
  {
    name: 'Desk',
    price: 'Custom',
    cadence: 'commercial structure',
    description:
      'For teams with more complex rollout needs, multiple operators, or a tailored commercial arrangement around support and workflow fit.',
    features: [
      'Tailored onboarding and enablement',
      'Desk-level commercial discussion',
      'Multi-operator workflow alignment',
      'Negotiated support and rollout planning',
    ],
    audience: 'Best for larger teams and partnerships',
  },
];

const principles = [
  {
    icon: TimerReset,
    title: 'Lower friction up front',
    body: 'Users can evaluate the platform before any live economics are active, which improves trust and reduces pressure during onboarding.',
  },
  {
    icon: Waves,
    title: 'Aligned to real usage',
    body: 'Profit-share makes more sense for a live trading platform than a generic SaaS subscription because it maps to delivered operator value.',
  },
  {
    icon: ShieldCheck,
    title: 'Commercial story matches UX',
    body: 'The public site, auth flow, and product surfaces all reinforce the same promise: a premium operator platform with a coherent model.',
  },
];

const comparisonRows = [
  ['Public-site onboarding', 'Included', 'Included', 'Included'],
  ['Backtest intelligence workspace', 'Included', 'Advanced', 'Advanced'],
  ['Live runtime operations', 'Preview posture', 'Included', 'Included'],
  ['Realtime stream-first UX', 'Preview posture', 'Included', 'Included'],
  ['Commercial model', 'No fee', '12% of net profit', 'Negotiated'],
];

const rolloutSteps = [
  ['1', 'Evaluate the product', 'Start with the Explorer tier to inspect the UI, workflow, and backtest experience.'],
  ['2', 'Enable live operating mode', 'Move into the Performance tier when the strategy and operator workflow are ready.'],
  ['3', 'Expand the partnership', 'Use Desk for multi-operator rollout, support depth, and commercial tailoring.'],
];

export const PricingPage: React.FC = () => {
  return (
    <PublicSiteShell>
      <section className="public-shell-container pt-10 sm:pt-12 lg:pt-14">
        <MotionReveal className="signal-card signal-card-strong overflow-hidden px-6 py-8 sm:px-8 xl:px-10 xl:py-10">
          <div className="grid gap-10 xl:grid-cols-[0.92fr,1.08fr] xl:items-center">
            <div>
              <div className="surface-label">
                <Sparkles className="h-3.5 w-3.5" />
                Commercial model
              </div>
              <h1 className="mt-6 text-4xl font-bold leading-[1.02] text-white sm:text-5xl xl:text-6xl">
                Pricing that feels native to a serious trading product.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
                Start with an evaluation posture, then activate aligned economics once the product
                is earning its place in live operations. The structure is clear, lower-friction, and
                easier to trust than generic monthly platform rent.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  to="/register"
                  className="premium-button premium-button-primary min-w-[13rem] justify-center rounded-[1.3rem] px-6 py-3.5 text-sm font-semibold text-white"
                >
                  Start evaluation
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/login"
                  className="premium-button premium-button-secondary min-w-[13rem] justify-center rounded-[1.3rem] px-6 py-3.5 text-sm font-medium"
                >
                  Sign in
                </Link>
              </div>

              <div className="mt-8 flex flex-wrap gap-3">
                {[
                  'No flat fee to begin',
                  'Aligned to realized upside',
                  'Clear progression from evaluation to live',
                ].map((item) => (
                  <div key={item} className="data-chip">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-4">
              <div className="market-illustration-shell p-4 sm:p-5">
                <ProfitShareIllustration />
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                {[
                  ['Explorer', '$0', 'Evaluate product quality before live economics activate'],
                  ['Performance', '12%', 'Net-profit share for active operators'],
                  ['Desk', 'Custom', 'Commercially tailored rollout for larger teams'],
                ].map(([title, value, body]) => (
                  <div key={title} className="metric-tile px-4 py-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{title}</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
                    <p className="mt-2 text-xs leading-5 text-slate-400">{body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </MotionReveal>
      </section>

      <section className="public-shell-container py-16">
        <MotionReveal className="mb-8">
          <div className="surface-label">
            <ShieldCheck className="h-3.5 w-3.5" />
            Why it works
          </div>
          <h2 className="mt-4 max-w-3xl text-3xl font-bold text-white sm:text-4xl">
            The fee model should reinforce trust, not introduce skepticism.
          </h2>
        </MotionReveal>
        <div className="grid gap-5 lg:grid-cols-3">
          {principles.map((item, index) => {
            const Icon = item.icon;
            return (
              <MotionReveal key={item.title} delayMs={index * 70} className="signal-card px-6 py-6">
                <div className="rounded-2xl bg-cyan-500/10 p-3 text-cyan-300 w-fit">
                  <Icon className="h-5 w-5" />
                </div>
                <p className="mt-5 text-lg font-semibold text-white">{item.title}</p>
                <p className="mt-3 text-sm leading-7 text-slate-400">{item.body}</p>
              </MotionReveal>
            );
          })}
        </div>
      </section>

      <section className="public-shell-container py-8">
        <div className="grid gap-5 lg:grid-cols-3">
          {plans.map((plan, index) => (
            <MotionReveal
              key={plan.name}
              delayMs={index * 90}
              className={`px-7 py-7 ${plan.featured ? 'signal-card signal-card-strong' : 'signal-card'}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{plan.name}</p>
                  <div className="mt-4 flex items-end gap-2">
                    <p className="text-4xl font-semibold text-white">{plan.price}</p>
                    <p className="pb-1 text-sm text-slate-400">{plan.cadence}</p>
                  </div>
                </div>
                {plan.featured ? (
                  <div className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
                    Recommended
                  </div>
                ) : null}
              </div>

              <p className="mt-4 text-sm leading-7 text-slate-400">{plan.description}</p>
              <div className="mt-4 rounded-2xl border border-slate-800/80 bg-slate-950/55 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Fit</p>
                <p className="mt-1 text-sm font-medium text-slate-200">{plan.audience}</p>
              </div>

              <div className="mt-6 space-y-3">
                {plan.features.map((feature) => (
                  <div key={feature} className="flex items-start gap-3 text-sm text-slate-300">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                    <span>{feature}</span>
                  </div>
                ))}
              </div>

              <div className="mt-8">
                <Link
                  to="/register"
                  className={`premium-button inline-flex w-full items-center justify-center gap-2 rounded-[1.3rem] px-5 py-3.5 text-sm font-semibold ${
                    plan.featured ? 'premium-button-primary text-white' : 'premium-button-secondary'
                  }`}
                >
                  {plan.name === 'Desk' ? 'Discuss rollout' : 'Start now'}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="public-shell-container py-16">
        <div className="grid gap-6 xl:grid-cols-[1.02fr,0.98fr]">
          <MotionReveal className="signal-card px-6 py-6">
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Capability comparison</p>
            <div className="mt-6 overflow-x-auto rounded-[1.4rem] border border-slate-800/80 bg-slate-950/35">
              <table className="min-w-[760px] text-sm">
                <thead>
                  <tr className="bg-slate-950/90 text-left">
                    <th className="px-5 py-4 text-[11px] uppercase tracking-[0.16em] text-slate-500">Capability</th>
                    <th className="px-5 py-4 text-[11px] uppercase tracking-[0.16em] text-slate-500">Explorer</th>
                    <th className="px-5 py-4 text-[11px] uppercase tracking-[0.16em] text-slate-500">Performance</th>
                    <th className="px-5 py-4 text-[11px] uppercase tracking-[0.16em] text-slate-500">Desk</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonRows.map((row, index) => (
                    <tr
                      key={row[0]}
                      className={`border-t border-slate-800/70 ${index % 2 === 0 ? 'bg-slate-900/46' : 'bg-slate-950/32'}`}
                    >
                      {row.map((cell, cellIndex) => (
                        <td
                          key={`${row[0]}-${cellIndex}`}
                          className={`px-5 py-4 ${cellIndex === 0 ? 'font-medium text-slate-100' : 'text-slate-300'}`}
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </MotionReveal>

          <div className="space-y-5">
            <MotionReveal className="signal-card signal-card-strong px-6 py-6">
              <p className="text-lg font-semibold text-white">Recommended progression</p>
              <div className="mt-5 space-y-4">
                {rolloutSteps.map(([step, title, body]) => (
                  <div key={step} className="flex items-start gap-4 rounded-2xl border border-slate-800/80 bg-slate-950/45 px-4 py-4">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cyan-500/20 bg-cyan-500/10 text-sm font-semibold text-cyan-200">
                      {step}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white">{title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-400">{body}</p>
                    </div>
                  </div>
                ))}
              </div>
            </MotionReveal>

            <MotionReveal className="signal-card px-6 py-6">
              <p className="text-lg font-semibold text-white">Why this reads as premium</p>
              <p className="mt-3 text-sm leading-7 text-slate-400">
                Good fintech UX is not just visual polish. It is making pricing, onboarding, security,
                and workflow progression feel consistent enough that the user trusts the platform
                before they rely on it operationally.
              </p>
              <Link
                to="/register"
                className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-cyan-300 transition hover:text-cyan-200"
              >
                Create an account
                <ArrowRight className="h-4 w-4" />
              </Link>
            </MotionReveal>
          </div>
        </div>
      </section>
    </PublicSiteShell>
  );
};

export default PricingPage;
