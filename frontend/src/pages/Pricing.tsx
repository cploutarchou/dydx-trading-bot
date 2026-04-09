import { ArrowRight, CheckCircle2, ShieldCheck, Sparkles, Waves } from 'lucide-react';
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
    description: 'A guided way to evaluate the platform before any capital-linked economics are activated.',
    features: [
      'Premium onboarding into the product',
      'Historical backtests and operator views',
      'Delayed market intelligence context',
      'Single-user workspace',
    ],
  },
  {
    name: 'Performance',
    price: '12%',
    cadence: 'of net profit',
    description:
      'For serious solo traders and lean teams that want the platform economics aligned with realized upside.',
    features: [
      'Live bot runtime control',
      'Realtime backtest and trade streaming',
      'Advanced positions and trade tables',
      'Premium strategy intelligence views',
      'No flat platform fee',
    ],
    featured: true,
  },
  {
    name: 'Desk',
    price: 'Custom',
    cadence: 'success-fee mandate',
    description:
      'For larger operators who need negotiated economics, tailored workflow support, and deeper rollout partnership.',
    features: [
      'Multi-operator operating model',
      'Custom onboarding and enablement',
      'Operational workflow tuning',
      'Negotiated success-fee structure',
    ],
  },
];

const comparison = [
  ['Live runtime operations', 'Preview only', 'Included', 'Included'],
  ['Realtime websocket UX', 'Preview only', 'Included', 'Included'],
  ['Backtest intelligence', 'Included', 'Advanced', 'Advanced'],
  ['Commercial model', 'No fee', '12% of net profit', 'Negotiated'],
];

const valuePillars = [
  ['Aligned economics', 'The platform only earns when it helps produce measurable upside.'],
  ['Lower friction', 'Users can validate workflow quality before they ever feel monetized.'],
  ['Higher credibility', 'Profit-share reads like operator partnership, not generic SaaS extraction.'],
];

export const PricingPage: React.FC = () => {
  return (
    <PublicSiteShell>
      <section className="public-shell-container pt-10 sm:pt-12 lg:pt-14">
        <MotionReveal className="editorial-band overflow-hidden px-1 py-8 sm:px-2 lg:px-0 xl:py-12">
          <div className="grid gap-10 xl:grid-cols-[0.92fr,1.08fr] xl:items-center">
            <div>
              <div className="premium-kicker">
                <Sparkles className="h-3.5 w-3.5" />
                Aligned Fee Model
              </div>
              <h1 className="mt-6 text-4xl font-bold leading-[1.02] text-white sm:text-5xl xl:text-6xl">
                Commercial terms that fit a serious arbitrage product.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
                Start with an evaluation workspace, validate the operator flow, then move into a
                performance model where platform economics only activate when the platform helps
                generate real upside.
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
            </div>

            <div className="grid gap-4">
              <div className="market-illustration-shell p-3 sm:p-5">
                <ProfitShareIllustration />
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                {[
                  ['12%', 'performance plan', 'applies to net realized profit'],
                  ['$0', 'explorer plan', 'start without flat platform rent'],
                  ['Desk', 'custom economics', 'structured for serious operators'],
                ].map(([value, title, body]) => (
                  <div key={title} className="micro-panel p-4">
                    <p className="text-2xl font-bold text-white">{value}</p>
                    <p className="mt-1 text-sm font-semibold text-slate-200">{title}</p>
                    <p className="mt-2 text-xs uppercase tracking-[0.16em] text-slate-500">{body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </MotionReveal>
      </section>

      <section className="public-shell-container py-16">
        <MotionReveal className="mb-8">
          <div className="premium-kicker">Why It Fits</div>
          <h2 className="mt-4 max-w-3xl text-3xl font-bold text-white sm:text-4xl">
            This pricing model feels native to the product because it behaves like operator partnership.
          </h2>
        </MotionReveal>
        <div className="grid gap-5 lg:grid-cols-3">
          {valuePillars.map(([title, body], index) => (
            <MotionReveal
              key={title}
              delayMs={index * 70}
              className="micro-panel p-6"
            >
              <p className="text-lg font-semibold text-white">{title}</p>
              <p className="mt-3 text-sm leading-7 text-slate-400">{body}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="public-shell-container py-8">
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
                  <div className="mt-4 flex items-end gap-2">
                    <p className="text-4xl font-semibold text-white">{plan.price}</p>
                    <p className="pb-1 text-sm text-slate-400">{plan.cadence}</p>
                  </div>
                </div>
                {plan.featured ? (
                  <div className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
                    Best fit
                  </div>
                ) : null}
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-400">{plan.description}</p>
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
                  {plan.name === 'Desk' ? 'Talk to us' : 'Start now'}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="public-shell-container py-16">
        <div className="grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
          <MotionReveal className="editorial-band pr-4 lg:pr-10">
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Package Comparison</p>
            <div className="micro-panel mt-6 overflow-x-auto rounded-[1.6rem]">
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
                  {comparison.map((row, index) => (
                    <tr
                      key={row[0]}
                      className={`border-t border-slate-800/70 transition-colors duration-200 hover:bg-slate-900/70 ${
                        index % 2 === 0 ? 'bg-slate-900/52' : 'bg-slate-950/38'
                      }`}
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
            <MotionReveal
              delayMs={100}
              className="micro-panel micro-panel-strong p-8"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-cyan-500/10 p-3 text-cyan-300">
                  <Waves className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-white">Why profit-share fits better</p>
                  <p className="text-sm text-slate-500">This is an operator platform, not a flat-fee dashboard.</p>
                </div>
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-400">
                Profit-only pricing lowers friction to start, aligns product incentives to actual
                trading outcomes, and feels much more credible in DeFi arbitrage than fixed monthly rent.
              </p>
            </MotionReveal>

            <MotionReveal
              delayMs={180}
              className="micro-panel p-8"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-emerald-500/10 p-3 text-emerald-300">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-white">Trust and onboarding</p>
                  <p className="text-sm text-slate-500">Commercial story and product experience should agree.</p>
                </div>
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-400">
                The public site, pricing model, and auth flow should all tell the same story:
                professional product quality, operator-grade workflows, and aligned economics.
              </p>
              <Link
                to="/register"
                className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-cyan-300 hover:text-cyan-200"
              >
                Create an account
                <ArrowRight className="h-4 w-4" />
              </Link>
            </MotionReveal>
          </div>
        </div>
      </section>

      <section className="public-shell-container pb-24 pt-4">
        <MotionReveal className="editorial-band overflow-hidden px-1 py-8 sm:px-2 lg:px-0">
          <div className="grid gap-8 lg:grid-cols-[1.1fr,0.9fr] lg:items-end">
            <div>
              <div className="premium-kicker">Commercial Model</div>
              <h2 className="mt-4 max-w-3xl text-3xl font-bold text-white sm:text-4xl">
                Let users discover the platform first, then activate aligned economics when the edge is proven.
              </h2>
              <p className="mt-4 max-w-2xl text-base leading-8 text-slate-300">
                This is how a serious product should price itself in this space: reduce friction at the start, build trust quickly, then earn with the operator.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                ['Evaluation runway', 'A clear path to test research quality before monetization begins.'],
                ['Desk partnership', 'Commercial flexibility for teams with more complex operational needs.'],
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

export default PricingPage;
