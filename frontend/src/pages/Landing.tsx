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
  [Waypoints, 'Research', 'Validate quality, risk, and consistency before exposure'],
  [ShieldCheck, 'Security', 'Complete account readiness with clear onboarding expectations'],
  [TrendingUp, 'Runtime', 'Enter live control when your operating desk is ready'],
] as const;

const valueItems = [
  [
    Radar,
    'Backtest confidence',
    'Compare strategy quality with risk context before teams spend effort on runtime decisions.',
  ],
  [
    ShieldCheck,
    'Secure onboarding',
    'Keep account setup, pricing, and live-access expectations plain and transparent.',
  ],
  [
    Sparkles,
    'Live clarity',
    'Make runtime state readable the moment your desk transitions from evaluation into operation.',
  ],
] as const;

const proofItems = [
  ['Signal discipline', 'Backtests, drawdown, win rate, and Sharpe reviewed before exposure'],
  ['Operational control', 'Live bot state, stream health, and action paths kept close together'],
  ['Commercial clarity', 'Client, IB, CRM, and admin workflows connected under one platform'],
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
                DeFi operator platform
              </div>
              <h1>
                Arbitrage intelligence, client operations, and live control in one premium crypto desk.
              </h1>
              <p>
                DefiArbitrage brings research evidence, secure onboarding, partner operations, and
                runtime visibility into a clean operating system for serious DeFi teams.
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
                  to="/pricing"
                  className="premium-button premium-button-secondary justify-center px-6 py-3.5 text-sm font-medium"
                >
                  View pricing
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
                  <strong>ARBITRAGE DESK</strong>
                </div>
                <DeFiHeroIllustration />
              </div>
              <div className="public-visual-tags">
                <span>Research evidence</span>
                <span>Runtime control</span>
                <span>Secure onboarding</span>
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

        <section className="public-modern-container public-market-section">
          <MotionReveal distancePx={18}>
            <PublicMarketPulsePanel
              eyebrow="Market intelligence"
              title="Route quality, spread, and depth stay close to every arbitrage decision."
              description="Compare active pairs, watch spread discipline, and keep liquidity context visible before a strategy moves toward runtime."
            />
          </MotionReveal>
        </section>

        <section className="public-modern-band">
          <div className="public-modern-container public-modern-split">
            <MotionReveal className="public-modern-section-copy" distancePx={18}>
              <div className="surface-label">Evaluation path</div>
              <h2>Move from signal confidence to live operation without losing context.</h2>
              <p>
                The public experience now matches the platform promise: research, account readiness,
                pricing, and runtime all sit in one intentional journey.
              </p>
            </MotionReveal>

            <div className="public-capability-grid">
              {pathItems.map(([Icon, title, body], index) => (
                <MotionReveal key={title} className="public-capability-card landing-modern-card" delayMs={index * 70}>
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
            <h2>Confidence before the first live action. Clarity after every handoff.</h2>
            <p>
              Each surface should help a serious operator understand evidence, access, and action
              priority without feeling like they entered a disconnected portal.
            </p>
          </MotionReveal>

          <div className="public-outcome-grid">
            {valueItems.map(([Icon, title, body], index) => (
              <MotionReveal key={title} className="public-outcome-modern landing-modern-card" delayMs={index * 70}>
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
                Ready for evaluation
              </div>
              <h2>Start with context. Continue into secure onboarding.</h2>
              <p>
                Review pricing, align on security expectations, and complete onboarding before live
                workflows or partner operations begin.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                to="/register"
                className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3 text-sm font-semibold text-white"
              >
                Start free evaluation
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
      </div>
    </PublicSiteShell>
  );
};

export default LandingPage;
