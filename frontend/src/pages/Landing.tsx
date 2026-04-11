import { ArrowRight, CheckCircle2, Radar, ShieldCheck } from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import MotionReveal from '../components/MotionReveal';
import PublicSiteShell from '../components/PublicSiteShell';

const pathItems = [
  ['Research', 'Validate quality, risk, and consistency before exposure'],
  ['Security', 'Complete account readiness with clear onboarding expectations'],
  ['Runtime', 'Enter live control when your operating desk is ready'],
] as const;

const valueItems = [
  [
    'Backtest confidence',
    'Compare strategy quality with risk context before teams spend effort on runtime decisions.',
  ],
  [
    'Secure onboarding',
    'Keep account setup, pricing, and live-access expectations plain and transparent.',
  ],
  [
    'Live clarity',
    'Make runtime state readable the moment your desk transitions from evaluation into operation.',
  ],
] as const;

export const LandingPage: React.FC = () => {
  return (
    <PublicSiteShell>
      <section className="landing-hero public-shell-container">
        <div className="landing-hero-copy">
          <MotionReveal distancePx={18}>
            <div className="surface-label">
              <Radar className="h-3.5 w-3.5" />
              DeFi operator platform
            </div>
            <h1>A calmer front door for evaluating, preparing, and running dYdX strategies.</h1>
          </MotionReveal>

          <MotionReveal delayMs={120} distancePx={18} className="mt-7 max-w-2xl">
            <p>
              dYdX Arbitrage OS guides teams from research conviction to secure onboarding and live
              runtime control—without the noise of a long marketing funnel.
            </p>
            <p className="mt-4 text-sm text-slate-400">
              Start free, validate your process, and move to live operations only when your desk is
              ready.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/register"
                className="premium-button premium-button-primary justify-center px-6 py-3.5 text-sm font-semibold text-white"
              >
                Start free evaluation
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/pricing"
                className="premium-button premium-button-secondary justify-center px-6 py-3.5 text-sm font-medium"
              >
                View pricing
              </Link>
            </div>
          </MotionReveal>
        </div>

        <MotionReveal delayMs={180} distancePx={18} className="landing-product-path">
          <div className="landing-path-heading">
            <span>Evaluation path</span>
            <strong>Clarity first. Runtime second.</strong>
          </div>
          <div className="landing-path-stack">
            {pathItems.map(([title, body], index) => (
              <div key={title} className="landing-path-item">
                <span>{String(index + 1).padStart(2, '0')}</span>
                <div>
                  <strong>{title}</strong>
                  <p>{body}</p>
                </div>
              </div>
            ))}
          </div>
        </MotionReveal>
      </section>

      <section className="landing-value public-shell-container">
        <MotionReveal className="landing-section-head" distancePx={18}>
          <div className="surface-label">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Product promise
          </div>
          <h2>Built for confidence before the first live action.</h2>
          <p>
            The public experience is intentionally short, clear, and operator-friendly. Teams can
            understand product value, risk posture, and onboarding expectations before committing
            account details.
          </p>
        </MotionReveal>

        <div className="landing-value-grid">
          {valueItems.map(([title, body], index) => (
            <MotionReveal
              key={title}
              delayMs={index * 90}
              distancePx={16}
              className="landing-value-item"
            >
              <span>{String(index + 1).padStart(2, '0')}</span>
              <h3>{title}</h3>
              <p>{body}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="landing-cta public-shell-container">
        <MotionReveal className="landing-cta-inner" distancePx={18}>
          <div>
            <div className="surface-label">
              <ShieldCheck className="h-4 w-4" />
              Ready for evaluation
            </div>
            <h2>Start with context. Continue into secure onboarding.</h2>
          </div>
          <div>
            <p>
              Review pricing, align on security expectations, and complete onboarding before any
              live workflow begins.
            </p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/register"
                className="premium-button premium-button-primary justify-center px-6 py-3 text-sm font-semibold text-white"
              >
                Start free evaluation
              </Link>
              <Link
                to="/services/security"
                className="premium-button premium-button-secondary justify-center px-6 py-3 text-sm font-medium"
              >
                Review security
              </Link>
            </div>
          </div>
        </MotionReveal>
      </section>
    </PublicSiteShell>
  );
};

export default LandingPage;
