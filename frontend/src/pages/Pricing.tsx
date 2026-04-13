import { ArrowRight, CheckCircle2, ShieldCheck } from 'lucide-react';
import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ProfitShareIllustration } from '../components/DeFiIllustrations';
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

const trustSignals = [
  ['No fixed fee to evaluate', 'Start with product fit, not procurement pressure'],
  ['Performance-aligned live terms', 'Commercial upside follows realized live net profit'],
  ['Desk rollout clarity', 'Team workflows can move into tailored commercial structure'],
] as const;

const pricingFaqs = [
  [
    'When does the performance share apply?',
    'Only after live operation produces realized net profit under the performance plan.',
  ],
  [
    'Can a team evaluate before committing?',
    'Yes. Explorer exists so operators can inspect workflows, security posture, and research quality before live economics.',
  ],
  [
    'What changes for a desk team?',
    'Desk plans add rollout planning, multi-operator workflow alignment, and negotiated support terms.',
  ],
] as const;

const PricingModelPanel: React.FC = () => (
  <div className="pricing-model-panel">
    <div className="pricing-model-header">
      <div>
        <p className="text-[11px] font-semibold uppercase text-slate-400">Commercial model</p>
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
          <p className="mt-2 text-sm leading-6 text-slate-200">{row.detail}</p>
          <p className="mt-3 text-xs text-slate-400">{row.note}</p>
        </div>
      ))}
    </div>

    <div className="mt-6 grid gap-3 md:grid-cols-2">
      {modelScenarios.map((scenario) => (
        <div key={scenario.title} className="pricing-scenario-card">
          <p className="text-sm font-semibold text-white">{scenario.title}</p>
          <p className="mt-2 text-xs text-emerald-200">{scenario.share}</p>
          <p className="mt-1 text-xs text-slate-300">{scenario.keep}</p>
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
      <div className="public-modern-page">
        <section className="public-modern-hero public-modern-hero-runtime">
          <div className="public-modern-container public-modern-hero-grid">
            <MotionReveal className="public-modern-copy" distancePx={18}>
              <div className="surface-label">
                <ShieldCheck className="h-3.5 w-3.5" />
                Pricing
              </div>
              <h1>
                DefiArbitrage pricing built around evidence, live performance, and desk readiness.
              </h1>
              <p>
                Evaluate the workspace first, then move into performance-aligned economics when live
                operation is ready. No flat fee to start. Commercial terms activate when live
                outcomes are real.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  to="/register"
                  className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3.5 text-sm font-semibold text-white"
                >
                  Start free evaluation
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/services/security"
                  className="premium-button premium-button-secondary justify-center px-6 py-3.5 text-sm font-medium"
                >
                  Review onboarding
                </Link>
              </div>
            </MotionReveal>

            <MotionReveal className="public-modern-visual" delayMs={90} distancePx={18}>
              <div className="public-visual-photo" aria-hidden="true" />
              <div className="public-visual-terminal">
                <div className="public-terminal-bar">
                  <span />
                  <span />
                  <span />
                  <strong>COMMERCIAL DESK</strong>
                </div>
                <ProfitShareIllustration />
              </div>
              <div className="public-visual-tags">
                <span>No fixed fee</span>
                <span>12% net profit share</span>
                <span>Desk rollout</span>
              </div>
            </MotionReveal>
          </div>
        </section>

        <section className="public-modern-container public-proof-strip">
          {trustSignals.map(([title, body], index) => (
            <MotionReveal key={title} className="public-proof-item" delayMs={index * 60}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{title}</strong>
              <p>{body}</p>
            </MotionReveal>
          ))}
        </section>

        <section className="public-modern-band">
          <div className="public-modern-container public-modern-split">
            <MotionReveal className="public-modern-section-copy" distancePx={18}>
              <div className="surface-label">Commercial model</div>
              <h2>Evaluation before commitment, live economics after proof.</h2>
              <p>
                Pricing should feel as clear and operational as the product itself: start with
                evidence, activate live terms only when live outcomes are measurable, and move desks
                into tailored rollout when the workflow demands it.
              </p>
            </MotionReveal>

            <MotionReveal className="pricing-modern-model" delayMs={90} distancePx={18}>
              <PricingModelPanel />
            </MotionReveal>
          </div>
        </section>

        <section className="public-modern-container public-outcome-stage pricing-modern-selector">
          <MotionReveal className="public-modern-section-copy" distancePx={18}>
            <div className="surface-label">Plan selector</div>
            <h2>Which model fits your desk?</h2>
            <p>{selectedGuide.reason}</p>
          </MotionReveal>

          <MotionReveal className="pricing-persona-panel" delayMs={80}>
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
                <span className="font-semibold text-white">Recommended:</span>{' '}
                {selectedGuide.recommendedPlan}
              </p>
              <p className="mt-1 text-xs leading-6 text-slate-400">{selectedGuide.reason}</p>
            </div>
          </MotionReveal>
        </section>

        <section className="public-modern-container pricing-modern-plan-section">
          <div className="pricing-modern-plan-grid">
            {plans.map((plan, index) => (
              <MotionReveal key={plan.name} delayMs={index * 70}>
                <div
                  className={`pricing-modern-plan ${
                    plan.name === selectedGuide.recommendedPlan ? 'is-persona-match' : ''
                  }`}
                >
                  <div className="pricing-modern-plan-top">
                    <span>0{index + 1}</span>
                    <div>
                      {plan.featured && <strong>Recommended</strong>}
                      {plan.name === selectedGuide.recommendedPlan && <strong>Best fit</strong>}
                    </div>
                  </div>
                  <h3>{plan.name}</h3>
                  <p className="pricing-modern-audience">{plan.audience}</p>
                  <div className="pricing-modern-price">
                    <strong>{plan.price}</strong>
                    <span>{plan.cadence}</span>
                  </div>
                  <p className="pricing-modern-description">{plan.description}</p>
                  <div className="pricing-modern-meta">
                    <p>
                      <span>Activation</span>
                      {plan.activation}
                    </p>
                    <p>
                      <span>Commitment</span>
                      {plan.commitment}
                    </p>
                  </div>
                  <div className="pricing-modern-features">
                    {plan.features.map((feature) => (
                      <div key={feature}>
                        <CheckCircle2 className="h-4 w-4" />
                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>
                  <Link
                    to="/register"
                    className={`premium-button justify-center px-5 py-3 text-sm font-semibold ${
                      plan.featured ? 'premium-button-primary text-white' : 'premium-button-secondary'
                    }`}
                  >
                    {plan.name === 'Desk' ? 'Discuss rollout' : 'Start free evaluation'}
                  </Link>
                </div>
              </MotionReveal>
            ))}
          </div>
        </section>

        <section className="public-modern-band pricing-modern-compare">
          <div className="public-modern-container public-modern-split">
            <MotionReveal className="public-modern-section-copy" distancePx={18}>
              <div className="surface-label">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Compare access
              </div>
              <h2>Clear access levels for evaluation, live operation, and desk rollout.</h2>
              <p>
                Start with the lowest commitment path, then move to performance or desk terms when
                the workflow is ready.
              </p>
            </MotionReveal>

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

        <section className="public-modern-container public-outcome-stage pricing-modern-faq">
          <MotionReveal className="public-modern-section-copy" distancePx={18}>
            <div className="surface-label">
              <ShieldCheck className="h-3.5 w-3.5" />
              Pricing FAQ
            </div>
            <h2>Straight answers before the first live workflow.</h2>
            <p>
              Evaluation, onboarding, and live commercial activation stay intentionally separate so
              teams always understand the next step.
            </p>
          </MotionReveal>

          <div className="public-outcome-grid">
            {pricingFaqs.map(([question, answer], index) => (
              <MotionReveal key={question} className="public-outcome-modern" delayMs={index * 70}>
                <span>FAQ {String(index + 1).padStart(2, '0')}</span>
                <strong>{question}</strong>
                <p>{answer}</p>
              </MotionReveal>
            ))}
          </div>
        </section>
      </div>
    </PublicSiteShell>
  );
};

export default PricingPage;
