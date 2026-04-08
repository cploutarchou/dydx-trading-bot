import { ArrowRight, CheckCircle2, ShieldCheck, Sparkles, Waves } from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import PublicSiteShell from '../components/PublicSiteShell';

const plans = [
  {
    name: 'Explorer',
    price: '$0',
    cadence: 'evaluation access',
    description: 'A guided way to evaluate the platform before you activate capital-linked fees.',
    features: [
      'Landing-to-login premium onboarding',
      'Backtest browsing and historical analytics',
      'Delayed market intelligence context',
      'Single user workspace',
    ],
  },
  {
    name: 'Performance',
    price: '12%',
    cadence: 'of net profit',
    description: 'For serious solo traders and small teams that want aligned economics and no flat platform fee.',
    features: [
      'Live bot runtime control',
      'Realtime backtest and trade streaming',
      'Advanced positions and trade tables',
      'Premium strategy intelligence and research views',
      'No monthly platform fee',
    ],
    featured: true,
  },
  {
    name: 'Desk',
    price: 'Custom',
    cadence: 'profit-share mandate',
    description: 'For capital-intensive teams that want a negotiated success-fee model and dedicated rollout.',
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
  ['Fee model', 'No fee', '12% of net profit', 'Negotiated'],
];

export const PricingPage: React.FC = () => {
  return (
    <PublicSiteShell>
      <section className="mx-auto max-w-7xl px-4 pb-16 pt-16 sm:px-6 lg:px-8 lg:pb-24 lg:pt-20">
        <div className="rounded-[2rem] border border-slate-800 bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.12),_transparent_24%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] px-6 py-10 sm:px-10">
          <div className="mx-auto max-w-3xl text-center">
            <div className="premium-kicker justify-center">
              <Sparkles className="h-3.5 w-3.5" />
              Aligned Fee Model
            </div>
            <h1 className="mt-5 text-4xl font-bold text-white sm:text-5xl">
              Packages designed around profit alignment, not flat SaaS rent.
            </h1>
            <p className="mt-4 text-base leading-8 text-slate-300">
              Start with an evaluation workspace, then move into a profit-share model where fees
              are earned only when the platform helps produce real trading upside.
            </p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
        <div className="grid gap-5 lg:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`rounded-[2rem] border p-7 ${
                plan.featured
                  ? 'border-cyan-500/35 bg-[linear-gradient(180deg,rgba(8,145,178,0.18),rgba(10,15,28,0.95))]'
                  : 'border-slate-800 bg-slate-900/70'
              }`}
            >
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{plan.name}</p>
              <div className="mt-4 flex items-end gap-2">
                <p className="text-4xl font-semibold text-white">{plan.price}</p>
                <p className="pb-1 text-sm text-slate-400">{plan.cadence}</p>
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
                  to={plan.name === 'Desk' ? '/register' : '/register'}
                  className={`inline-flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold transition ${
                    plan.featured
                      ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20 hover:brightness-105'
                      : 'border border-slate-800 bg-slate-950 text-slate-200 hover:border-slate-700 hover:text-white'
                  }`}
                >
                  {plan.name === 'Desk' ? 'Talk to us' : 'Start now'}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[1fr_0.9fr]">
          <div className="rounded-[2rem] border border-slate-800 bg-slate-900/70 p-8">
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Package Comparison</p>
            <div className="mt-6 overflow-hidden rounded-[1.5rem] border border-slate-800">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-slate-950/90 text-left">
                    <th className="px-5 py-4 text-[11px] uppercase tracking-[0.16em] text-slate-500">Capability</th>
                    <th className="px-5 py-4 text-[11px] uppercase tracking-[0.16em] text-slate-500">Explorer</th>
                    <th className="px-5 py-4 text-[11px] uppercase tracking-[0.16em] text-slate-500">Performance</th>
                    <th className="px-5 py-4 text-[11px] uppercase tracking-[0.16em] text-slate-500">Desk</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.map((row) => (
                    <tr key={row[0]} className="border-t border-slate-800 bg-slate-900/65">
                      {row.map((cell, index) => (
                        <td
                          key={`${row[0]}-${index}`}
                          className={`px-5 py-4 ${index === 0 ? 'font-medium text-slate-100' : 'text-slate-300'}`}
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-5">
            <div className="rounded-[2rem] border border-slate-800 bg-slate-950/75 p-8">
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
                Your preference makes sense. Profit-only pricing aligns the platform with real
                performance, lowers friction to start, and feels much more credible for DeFi
                arbitrage than charging a fixed monthly fee before users see results.
              </p>
            </div>

            <div className="rounded-[2rem] border border-slate-800 bg-slate-900/70 p-8">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-emerald-500/10 p-3 text-emerald-300">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-white">Trust and onboarding</p>
                  <p className="text-sm text-slate-500">Make sign-up feel worthy of the product behind it.</p>
                </div>
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-400">
                The website now carries that aligned story from landing to pricing to
                authentication, so the commercial model feels consistent with the premium product
                experience.
              </p>
              <Link
                to="/register"
                className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-cyan-300 hover:text-cyan-200"
              >
                Create an account
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </PublicSiteShell>
  );
};

export default PricingPage;
