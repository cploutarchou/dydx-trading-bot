import {
    ArrowRight,
    CheckCircle2,
    Radar,
    ShieldCheck,
    Sparkles,
    TrendingUp,
    Waypoints,
} from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import { DeFiHeroIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import { PublicMarketPulsePanel } from '../components/PublicMarketPulse';
import PublicSiteShell from '../components/PublicSiteShell';

const pathItems = [
  [Waypoints, 'Frame', 'Validate scope, risk, and constraints before build work starts'],
  [ShieldCheck, 'Harden', 'Complete account readiness with clear security expectations'],
  [TrendingUp, 'Execute', 'Move into automation and runtime when the plan is ready'],
] as const;

const valueItems = [
  [
    Radar,
    'Execution confidence',
    'Compare system direction with risk context before teams spend effort on build decisions.',
  ],
  [
    ShieldCheck,
    'Secure onboarding',
    'Keep account setup, pricing, and execution expectations plain and transparent.',
  ],
  [
    Sparkles,
    'Runtime clarity',
    'Make system state readable the moment a workflow transitions from evaluation into operation.',
  ],
] as const;

const proofItems = [
  ['Scope discipline', 'Requirements, constraints, and risk reviewed before execution'],
  ['Operational control', 'Runtime state, health, and action paths kept close together'],
  ['Delivery clarity', 'Product, automation, and admin workflows connected under one workspace'],
] as const;

const trustItems = [
  [
    'Controls-first onboarding',
    'Credential checks, environment confirmation, and operator gating before runtime actions',
  ],
  [
    'Transparent operating model',
    'Evaluation first, then execution terms when the delivery path is measurable',
  ],
  [
    'Audit-ready operations',
    'Traceable API paths, runtime status evidence, and role-based visibility across surfaces',
  ],
] as const;

const riskItems = [
  'Technical delivery carries risk, including scope change, integration uncertainty, and operational complexity.',
  'Prototype and test outcomes are evidence for planning, not guarantees of production behavior.',
  'Execution quality depends on clear requirements, data access, reliable systems, and timely decisions.',
  'Operators remain responsible for business, security, compliance, and jurisdiction requirements.',
] as const;

export const LandingPage: React.FC = () => {
  return (
    <PublicSiteShell>
      <div className="public-modern-page">
        <section className="public-modern-hero public-modern-hero-intelligence">
          <div className="public-modern-container public-modern-hero-grid">
            <MotionReveal className="public-modern-copy" distancePx={18}>
              <div className="surface-label">
                <Radar className="h-3.5 w-3.5" />
                Modern technical execution lab
              </div>
              <h1>
                Build. Test. Execute. Premium technical delivery without the noise.
              </h1>
              <p>
                ExecutionLab turns ideas into shipped systems with disciplined discovery,
                production-minded engineering, automation, and clear runtime visibility.
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
                  to="/pricing"
                  className="premium-button premium-button-secondary justify-center px-6 py-3.5 text-sm font-medium"
                >
                  View engagement model
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
              description="Compare workstreams, watch quality gates, and keep implementation context visible before a system moves toward runtime."
            />
          </MotionReveal>
        </section>

        <section className="public-modern-band">
          <div className="public-modern-container public-modern-split">
            <MotionReveal className="public-modern-section-copy" distancePx={18}>
              <div className="surface-label">Evaluation path</div>
              <h2>Move from signal confidence to shipped system without losing context.</h2>
              <p>
                The experience matches the ExecutionLab promise: research, account readiness,
                pricing, automation, and runtime all sit in one intentional journey.
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
            <h2>Confidence before the first build action. Clarity after every handoff.</h2>
            <p>
              Each surface helps serious operators understand evidence, access, and action priority
              without feeling like they entered a disconnected portal.
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
              <h2>Start with context. Continue into disciplined execution.</h2>
              <p>
                Review engagement options, align on security expectations, and complete onboarding
                before runtime workflows or partner operations begin.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                to="/register"
                className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3 text-sm font-semibold text-white"
              >
                Start execution review
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
              We keep expectations explicit so operators can evaluate delivery quality, risk
              posture, and operational readiness with no hidden assumptions.
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
