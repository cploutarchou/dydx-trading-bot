import { ArrowRight, CheckCircle2, ShieldCheck, TimerReset, Waves } from 'lucide-react';
import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import MotionReveal from '../components/MotionReveal';
import PublicSiteShell from '../components/PublicSiteShell';

const plans = [
  {
    name: 'Explorer',
    price: '$0',
    cadence: 'evaluation access',
    audience: 'Initial product evaluation',
    activation: 'Starts immediately after signup',
    commitment: 'No commercial commitment',
    description:
      'Inspect the platform, understand the workflows, and validate whether the operator experience is right for your desk.',
    features: [
      'Account setup and security onboarding',
      'Historical backtest workspace',
      'Foundational market intelligence',
      'Single-operator evaluation posture',
    ],
  },
  {
    name: 'Performance',
    price: '12%',
    cadence: 'of net profit',
    audience: 'Active operators',
    activation: 'Applies only when live net profit is realized',
    commitment: 'No fixed platform fee',
    description:
      'Move into live operating mode with commercial terms tied to realized upside instead of flat software rent.',
    features: [
      'Live bot control and runtime workflow',
      'Realtime stream and sync-health monitoring',
      'Signal-rich research views',
      'No recurring platform fee',
    ],
    featured: true,
  },
  {
    name: 'Desk',
    price: 'Custom',
    cadence: 'commercial structure',
    audience: 'Teams and partnerships',
    activation: 'Activated after desk rollout planning',
    commitment: 'Negotiated operating terms',
    description:
      'For desks that need multiple operators, rollout support, workflow alignment, or a tailored commercial arrangement.',
    features: [
      'Tailored onboarding and enablement',
      'Multi-operator workflow planning',
      'Desk-level commercial discussion',
      'Negotiated support model',
    ],
  },
];

const principles = [
  {
    icon: TimerReset,
    title: 'Evaluation first',
    body: 'Users can understand the product before live economics are active.',
  },
  {
    icon: Waves,
    title: 'Outcome aligned',
    body: 'Profit share maps the commercial model to realized trading upside.',
  },
  {
    icon: ShieldCheck,
    title: 'Clear progression',
    body: 'Pricing, onboarding, and runtime access move in a clear order.',
  },
];

const comparisonRows = [
  ['Security onboarding', 'Included', 'Included', 'Included'],
  ['Backtest intelligence workspace', 'Included', 'Advanced', 'Advanced'],
  ['Live runtime operations', 'Preview posture', 'Included', 'Included'],
  ['Realtime stream monitoring', 'Preview posture', 'Included', 'Included'],
  ['Commercial model', 'No fee', '12% net profit share', 'Negotiated'],
];

const pricingModelRows = [
  {
    stage: 'Evaluation',
    value: '$0',
    detail: 'Access the platform and validate fit before any commercial activation.',
    note: 'Best for first product validation',
  },
  {
    stage: 'Live access',
    value: '12%',
    detail: 'Profit share applies only to realized net profit from live operation.',
    note: 'No fixed platform fee',
  },
  {
    stage: 'Desk rollout',
    value: 'Custom',
    detail: 'Commercial structure is tailored to team workflow and support needs.',
    note: 'Designed for multi-operator teams',
  },
] as const;

const modelScenarios = [
  {
    title: 'Example: $10,000 net-profit month',
    share: '$1,200 performance share',
    keep: '$8,800 retained by your desk',
  },
  {
    title: 'Example: $0 net-profit month',
    share: '$0 performance share',
    keep: 'No fee charged for that period',
  },
] as const;

const personaGuides = [
  {
    id: 'new',
    label: 'I am just exploring',
    recommendedPlan: 'Explorer',
    reason: 'Start with zero commitment and validate workflow fit before any live economics.',
  },
  {
    id: 'live',
    label: 'I plan to trade live',
    recommendedPlan: 'Performance',
    reason: 'Use performance-aligned terms that activate only when realized live profit exists.',
  },
  {
    id: 'team',
    label: 'I run a desk team',
    recommendedPlan: 'Desk',
    reason: 'Coordinate multi-operator rollout with tailored terms and support structure.',
  },
] as const;

const PricingModelPanel: React.FC = () => (
  <div className="pricing-model-panel">
    <div className="pricing-model-header">
      <div>
        <p className="text-[11px] font-semibold uppercase text-slate-500">Commercial model</p>
        <p className="mt-2 text-2xl font-semibold text-white">Evaluation before commitment</p>
      </div>
      <p className="pricing-model-open">
        <span className="h-2 w-2 rounded-full bg-emerald-400" />
        Open
      </p>
    </div>

    <div className="pricing-model-flow mt-6">
      {pricingModelRows.map((row, index) => (
        <div key={row.stage} className="pricing-model-card">
          <p className="pricing-model-step">Step {index + 1}</p>
          <p className="mt-2 text-base font-semibold text-white">{row.stage}</p>
          <p className="mt-1 text-2xl font-semibold text-emerald-300">{row.value}</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">{row.detail}</p>
          <p className="mt-3 text-xs text-slate-500">{row.note}</p>
        </div>
      ))}
    </div>

    <div className="mt-6 grid gap-3 md:grid-cols-2">
      {modelScenarios.map((scenario) => (
        <div key={scenario.title} className="pricing-scenario-card">
          <p className="text-sm font-semibold text-white">{scenario.title}</p>
          <p className="mt-2 text-xs text-emerald-300">{scenario.share}</p>
          <p className="mt-1 text-xs text-slate-400">{scenario.keep}</p>
        </div>
      ))}
    </div>
  </div>
);

export const PricingPage: React.FC = () => {
  const [activePersona, setActivePersona] = useState<(typeof personaGuides)[number]['id']>('new');
  const selectedGuide = useMemo(
    () => personaGuides.find((guide) => guide.id === activePersona) ?? personaGuides[0],
    [activePersona]
  );

  return (
    <PublicSiteShell>
      <section className="pricing-hero public-shell-container">
        <MotionReveal className="pricing-hero-grid">
          <div>
            <div className="surface-label">
              <ShieldCheck className="h-3.5 w-3.5" />
              Pricing
            </div>
            <h1 className="mt-6 max-w-4xl text-4xl font-bold leading-[1.06] text-white sm:text-5xl">
              Commercial terms designed to feel as clear as the product itself.
            </h1>
          </div>
          <div className="lg:pb-1">
            <p className="max-w-2xl text-base leading-8 text-slate-300">
              Evaluate the workspace first, then move into performance-aligned economics when live
              operation is ready.
            </p>
            <p className="mt-3 text-sm text-slate-400">
              No flat fee to start. Commercial terms activate when live outcomes are real.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/register"
                className="premium-button premium-button-primary justify-center px-6 py-3.5 text-sm font-semibold text-white"
              >
                Create free account
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/services/security"
                className="premium-button premium-button-secondary justify-center px-6 py-3.5 text-sm font-medium"
              >
                Review onboarding
              </Link>
            </div>
          </div>
        </MotionReveal>

        <MotionReveal delayMs={100} className="mt-12">
          <PricingModelPanel />
          <div className="pricing-principles-grid mt-6">
            {principles.map((item, index) => {
              const Icon = item.icon;
              return (
                <div key={item.title} className="pricing-principle-item">
                  <Icon className="h-5 w-5 text-cyan-300" />
                  <p className="mt-3 text-sm font-semibold text-white">{item.title}</p>
                  <p className="mt-2 max-w-xs text-xs leading-5 text-slate-400">{item.body}</p>
                  <p className="mt-3 font-mono text-xs text-slate-600">0{index + 1}</p>
                </div>
              );
            })}
          </div>
        </MotionReveal>
      </section>

      <section className="public-shell-container pt-2 pb-8">
        <MotionReveal className="pricing-persona-panel">
          <div>
            <p className="text-[11px] font-semibold uppercase text-slate-500">Plan selector</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Which model fits your desk?</h2>
          </div>

          <div className="pricing-persona-buttons">
            {personaGuides.map((guide) => (
              <button
                key={guide.id}
                type="button"
                onClick={() => setActivePersona(guide.id)}
                className={`pricing-persona-button ${activePersona === guide.id ? 'is-active' : ''}`}
              >
                {guide.label}
              </button>
            ))}
          </div>

          <div className="pricing-persona-recommendation">
            <p className="text-sm text-slate-300">
              <span className="font-semibold text-white">Recommended:</span> {selectedGuide.recommendedPlan}
            </p>
            <p className="mt-1 text-xs leading-6 text-slate-400">{selectedGuide.reason}</p>
          </div>
        </MotionReveal>
      </section>

      <section className="pricing-plans-shell">
        <div className="public-shell-container pricing-plans-list">
          {plans.map((plan, index) => (
            <MotionReveal key={plan.name} delayMs={index * 70}>
              <div
                className={`pricing-plan-row ${
                  plan.name === selectedGuide.recommendedPlan ? 'is-persona-match' : ''
                }`}
              >
                <div>
                  <p className="font-mono text-sm text-cyan-300">0{index + 1}</p>
                  {plan.featured && (
                    <p className="mt-3 inline-flex rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-200">
                      Recommended
                    </p>
                  )}
                  {plan.name === selectedGuide.recommendedPlan && (
                    <p className="mt-2 inline-flex rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-200">
                      Best fit for your selection
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-2xl font-semibold text-white">{plan.name}</p>
                  <p className="mt-2 text-sm text-slate-400">{plan.audience}</p>
                  <div className="mt-4 grid gap-2">
                    <p className="text-xs text-slate-300">
                      <span className="font-semibold text-slate-100">Activation:</span> {plan.activation}
                    </p>
                    <p className="text-xs text-slate-300">
                      <span className="font-semibold text-slate-100">Commitment:</span> {plan.commitment}
                    </p>
                  </div>
                </div>
                <div>
                  <div className="flex items-end gap-2">
                    <p className="text-4xl font-semibold text-white">{plan.price}</p>
                    <p className="pb-1 text-sm text-slate-400">{plan.cadence}</p>
                  </div>
                  <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-400">
                    {plan.description}
                  </p>
                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    {plan.features.map((feature) => (
                      <div key={feature} className="flex items-start gap-3 text-sm text-slate-300">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <Link
                  to="/register"
                  className={`premium-button justify-center px-5 py-3 text-sm font-semibold lg:self-center ${
                    plan.featured ? 'premium-button-primary text-white' : 'premium-button-secondary'
                  }`}
                >
                  {plan.name === 'Desk' ? 'Discuss rollout' : 'Start evaluation'}
                </Link>
              </div>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="pricing-compare public-shell-container">
        <MotionReveal className="grid gap-8 lg:grid-cols-[minmax(0,0.95fr),minmax(22rem,0.65fr)]">
          <div>
            <div className="surface-label">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Compare access
            </div>
            <h2 className="mt-5 text-3xl font-bold text-white">
              Clear access levels for evaluation, live operation, and desk rollout.
            </h2>
          </div>
          <p className="max-w-2xl text-sm leading-7 text-slate-400 lg:pt-10">
            Start with the lowest commitment path, then move to performance or desk terms when the
            workflow is ready.
          </p>
        </MotionReveal>

        <div className="mt-10">
          <MotionReveal delayMs={100} className="pricing-compare-table-wrap overflow-x-auto">
            <table className="min-w-190 w-full text-sm">
              <thead>
                <tr className="text-left">
                  <th className="px-4 py-4 text-[11px] uppercase text-slate-500">Capability</th>
                  <th className="px-4 py-4 text-[11px] uppercase text-slate-500">Explorer</th>
                  <th className="px-4 py-4 text-[11px] uppercase text-slate-500">Performance</th>
                  <th className="px-4 py-4 text-[11px] uppercase text-slate-500">Desk</th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row[0]} className="border-t border-stone-800">
                    {row.map((cell, cellIndex) => (
                      <td
                        key={`${row[0]}-${cellIndex}`}
                        className={`px-4 py-4 ${
                          cellIndex === 0 ? 'font-medium text-slate-100' : 'text-slate-300'
                        }`}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </MotionReveal>
        </div>
      </section>
    </PublicSiteShell>
  );
};

export default PricingPage;
