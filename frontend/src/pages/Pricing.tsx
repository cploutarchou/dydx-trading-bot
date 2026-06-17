import { ArrowRight, CheckCircle2, ShieldCheck } from 'lucide-react';
import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ProfitShareIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import { PublicMarketPulsePanel } from '../components/PublicMarketPulse';
import PublicSiteShell from '../components/PublicSiteShell';
import SEOHead from '../components/SEOHead';

const plans = [
  {
    name: 'Scope Review',
    price: 'Review',
    cadence: 'fit and discovery',
    audience: 'Initial product or automation evaluation',
    activation: 'Starts after onboarding',
    commitment: 'Focused discovery commitment',
    description:
      'Clarify the objective, map constraints, and decide whether the execution path is worth building.',
    features: [
      'Account setup and security onboarding',
      'Scope and constraint review',
      'Technical direction assessment',
      'Execution plan recommendation',
    ],
  },
  {
    name: 'Build Sprint',
    price: 'Quoted',
    cadence: 'project execution',
    audience: 'Teams ready to build',
    activation: 'Starts after scope approval',
    commitment: 'Defined delivery scope',
    description:
      'Move into focused engineering delivery with clear milestones, implementation ownership, and quality gates.',
    features: [
      'Product and frontend implementation',
      'Automation and runtime workflow',
      'Testing and release readiness',
      'Operator handoff documentation',
    ],
    featured: true,
  },
  {
    name: 'Execution Partner',
    price: 'Custom',
    cadence: 'delivery partnership',
    audience: 'Teams and ongoing systems',
    activation: 'Activated after rollout planning',
    commitment: 'Tailored operating terms',
    description:
      'For teams that need ongoing execution, rollout support, automation ownership, or a tailored delivery arrangement.',
    features: [
      'Tailored onboarding and enablement',
      'Multi-workstream delivery planning',
      'System operations and iteration support',
      'Negotiated support model',
    ],
  },
];

const comparisonRows = [
  ['Security onboarding', 'Included', 'Included', 'Included'],
  ['Execution planning', 'Included', 'Advanced', 'Advanced'],
  ['Build implementation', 'Recommendation', 'Included', 'Included'],
  ['Runtime and automation visibility', 'Preview posture', 'Included', 'Included'],
  ['Engagement model', 'Focused review', 'Quoted project', 'Negotiated'],
];

const pricingModelRows = [
  {
    stage: 'Discovery',
    value: 'Review',
    detail: 'Validate fit, constraints, and execution priority before build activation.',
    note: 'Best for first product validation',
  },
  {
    stage: 'Build',
    value: 'Quoted',
    detail: 'Delivery terms follow a defined scope, milestone plan, and quality bar.',
    note: 'Best for focused execution',
  },
  {
    stage: 'Scale',
    value: 'Custom',
    detail:
      'Commercial structure is tailored to team workflow, automation depth, and support needs.',
    note: 'Designed for ongoing systems',
  },
] as const;

const modelScenarios = [
  {
    title: 'Example: product workflow build',
    share: 'Defined milestone plan',
    keep: 'Scope, delivery gates, and acceptance criteria agreed up front',
  },
  {
    title: 'Example: automation rollout',
    share: 'Custom execution model',
    keep: 'Runtime, support, and iteration needs shape the engagement',
  },
] as const;

const personaGuides = [
  {
    id: 'new',
    label: 'I need clarity',
    recommendedPlan: 'Scope Review',
    reason: 'Start with a focused review and validate execution fit before build work begins.',
  },
  {
    id: 'live',
    label: 'I am ready to build',
    recommendedPlan: 'Build Sprint',
    reason: 'Use a defined execution plan when scope, ownership, and quality gates are ready.',
  },
  {
    id: 'team',
    label: 'I need an execution partner',
    recommendedPlan: 'Execution Partner',
    reason:
      'Coordinate ongoing delivery, automation, and rollout with tailored terms and support structure.',
  },
] as const;

const trustSignals = [
  ['Clarity before build', 'Start with product fit, not procurement pressure'],
  ['Execution-aligned terms', 'Commercial shape follows scope, risk, and delivery responsibility'],
  ['Rollout clarity', 'Team workflows can move into tailored execution structure'],
] as const;

const pricingFaqs = [
  [
    'When does build work start?',
    'After scope, constraints, acceptance criteria, and delivery responsibility are clear.',
  ],
  [
    'Can a team evaluate before committing?',
    'Yes. Scope Review exists so operators can inspect workflows, security posture, and execution quality before larger delivery work.',
  ],
  [
    'What changes for an ongoing team?',
    'Execution Partner adds rollout planning, multi-workstream alignment, automation support, and negotiated operating terms.',
  ],
] as const;

const funnelSteps = [
  ['Create review account', 'Access product surfaces with a clear evaluation path.'],
  ['Complete security readiness', 'Validate credentials, environment, and runtime prerequisites.'],
  [
    'Run evidence-first workflow',
    'Review scope, risk context, and operational signals before activation.',
  ],
  ['Activate execution terms when ready', 'Delivery model follows the agreed execution path.'],
] as const;

const riskDisclosures = [
  'No representation is made that every idea will be feasible or worth building.',
  'Prototype or test outcomes are planning evidence, not guarantees of production behavior.',
  'Integration, data, security, and operational constraints can change execution scope.',
  'Users remain responsible for business, legal, security, and regulatory obligations.',
] as const;

const PricingModelPanel: React.FC = () => (
  <div className="pricing-model-panel">
    <div className="pricing-model-header">
      <div>
        <p className="text-[11px] font-semibold uppercase text-slate-400">Engagement model</p>
        <p className="mt-2 text-2xl font-semibold text-white">Clarity before commitment</p>
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
    <>
      <SEOHead
        title="Pricing | ExecutionLab"
        description="Flexible execution partnerships designed around discovery, delivery, and ongoing operations for dYdX trading automation."
        image="/og-images/pricing.png"
        imageAlt="ExecutionLab pricing plans - Scope Review, Build Sprint, Execution Partner"
        url="/pricing"
      />
      <PublicSiteShell>
        <div className="public-modern-page">
          <section className="public-modern-hero public-modern-hero-runtime">
            <div className="public-modern-container public-modern-hero-grid">
              <MotionReveal className="public-modern-copy" distancePx={18}>
                <div className="surface-label">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Engagement
                </div>
                <h1>
                  ExecutionLab engagements built around evidence, speed, and delivery discipline.
                </h1>
                <p>
                  Start with fit and scope clarity, then move into focused technical execution when
                  the plan is ready. Terms follow the work, risk, and delivery responsibility.
                </p>

                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <Link
                    to="/register"
                    className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3.5 text-sm font-semibold text-white"
                  >
                    Start execution review
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
                    <strong>ENGAGEMENT MODEL</strong>
                  </div>
                  <ProfitShareIllustration />
                </div>
                <div className="public-visual-tags">
                  <span>Scope review</span>
                  <span>Build sprint</span>
                  <span>Execution partner</span>
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

          <section className="public-modern-container public-market-section">
            <MotionReveal distancePx={18}>
              <PublicMarketPulsePanel
                eyebrow="Engagement signal"
                title="Engagement shape stays tied to scope, risk, and execution context."
                description="Use the execution view to evaluate where readiness, ownership, and quality gates support the right delivery model."
              />
            </MotionReveal>
          </section>

          <section className="public-modern-band">
            <div className="public-modern-container public-modern-split">
              <MotionReveal className="public-modern-section-copy" distancePx={18}>
                <div className="surface-label">Engagement model</div>
                <h2>Evaluation before commitment, execution terms after proof.</h2>
                <p>
                  Pricing should feel as clear and operational as the product itself: start with
                  evidence, activate delivery terms when the path is measurable, and move teams into
                  tailored rollout when the workflow demands it.
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
              <h2>Which model fits your execution path?</h2>
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
                        plan.featured
                          ? 'premium-button-primary text-white'
                          : 'premium-button-secondary'
                      }`}
                    >
                      {plan.name === 'Execution Partner'
                        ? 'Discuss rollout'
                        : 'Start execution review'}
                    </Link>
                  </div>
                </MotionReveal>
              ))}
            </div>
          </section>

          <section className="public-modern-container public-outcome-stage">
            <MotionReveal className="public-modern-section-copy" distancePx={18}>
              <div className="surface-label">How it works</div>
              <h2>Simple engagement path from review to execution.</h2>
              <p>
                The engagement path is explicit at each step so teams can adopt ExecutionLab
                progressively without hidden transitions.
              </p>
            </MotionReveal>

            <div className="public-outcome-grid">
              {funnelSteps.map(([title, body], index) => (
                <MotionReveal key={title} className="public-outcome-modern" delayMs={index * 70}>
                  <span>Step {String(index + 1).padStart(2, '0')}</span>
                  <strong>{title}</strong>
                  <p>{body}</p>
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
                <h2>Clear access levels for review, build, and rollout.</h2>
                <p>
                  Start with the lowest commitment path, then move to build or partner terms when
                  the workflow is ready.
                </p>
              </MotionReveal>

              <MotionReveal delayMs={100} className="pricing-compare-table-wrap overflow-x-auto">
                <table className="min-w-190 w-full text-sm">
                  <thead>
                    <tr className="text-left">
                      <th className="px-4 py-4 text-[11px] uppercase text-slate-500">Capability</th>
                      <th className="px-4 py-4 text-[11px] uppercase text-slate-500">
                        Scope Review
                      </th>
                      <th className="px-4 py-4 text-[11px] uppercase text-slate-500">
                        Build Sprint
                      </th>
                      <th className="px-4 py-4 text-[11px] uppercase text-slate-500">Partner</th>
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
              <h2>Straight answers before the first execution workflow.</h2>
              <p>
                Evaluation, onboarding, and delivery activation stay intentionally separate so teams
                always understand the next step.
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

          <section className="public-modern-container public-outcome-stage">
            <MotionReveal className="public-modern-section-copy" distancePx={18}>
              <div className="surface-label">Risk disclosure</div>
              <h2>Risk and compliance expectations are stated up front.</h2>
              <p>
                Commercial clarity also means operational realism: technical delivery includes risk,
                and users should evaluate suitability, controls, and obligations before activation.
              </p>
            </MotionReveal>

            <div className="public-outcome-grid">
              {riskDisclosures.map((item, index) => (
                <MotionReveal key={item} className="public-outcome-modern" delayMs={index * 70}>
                  <span>Disclosure {String(index + 1).padStart(2, '0')}</span>
                  <p>{item}</p>
                </MotionReveal>
              ))}
            </div>
          </section>
        </div>
      </PublicSiteShell>
    </>
  );
};

export default PricingPage;
