import { ArrowRight, CheckCircle2, ShieldCheck, Sparkles } from 'lucide-react';
import React from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ServicePulseIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import { PublicMarketPulsePanel } from '../components/PublicMarketPulse';
import PublicSiteShell from '../components/PublicSiteShell';
import { servicePages } from '../content/publicSite';

export const PublicServicePage: React.FC = () => {
  const { slug } = useParams();
  const page = servicePages.find((item) => item.slug === slug);
  const isSecurityPage = page?.slug === 'security';

  const securityReadinessSteps = [
    {
      title: 'Account verification',
      body: 'Keep invitation state, registration mode, and access posture explicit before users move forward.',
    },
    {
      title: 'Security setup',
      body: 'Guide users through password quality, 2FA readiness, and account hardening before workspace access.',
    },
    {
      title: 'Evaluation handoff',
      body: 'Return users to pricing and evaluation routes with context, not dead-end auth pages.',
    },
  ] as const;

  const securityOutcomeFlow = [
    {
      stage: 'Trust entry',
      detail: 'Increase trust before users even create an account.',
      note: 'First impression establishes confidence',
    },
    {
      stage: 'Keep context',
      detail: 'Keep authentication connected to pricing, product context, and onboarding.',
      note: 'No disconnected auth dead-ends',
    },
    {
      stage: 'Next-step clarity',
      detail: 'Reduce confusion about what happens after registration or sign-in.',
      note: 'Operators always know what comes next',
    },
  ] as const;

  const serviceOutcomeFlow = (page?.outcomes ?? []).map((outcome, index) => ({
    stage: `Step ${index + 1}`,
    detail: outcome,
    note:
      page?.slug === 'runtime'
        ? ([
            'Reduce response lag in live operations.',
            'Spot degraded systems early.',
            'Keep controls close to state.',
          ][index] ?? 'Keep operational decisions clear.')
        : ([
            'Improve research with system context.',
            'Support execution decisions with narrative context.',
            'Increase trust through complete operator visibility.',
          ][index] ?? 'Support higher-confidence operator decisions.'),
  }));

  const outcomesHeadline = isSecurityPage
    ? 'Security outcomes for operators.'
    : page?.slug === 'runtime'
      ? 'Runtime outcomes for live operators.'
      : page?.slug === 'intelligence'
        ? 'Intelligence outcomes for operator decisions.'
        : 'Decisions operators can make.';

  const outcomesIntro = isSecurityPage
    ? 'Keep entry trust high by making account state, onboarding flow, and next-step clarity obvious at every stage.'
    : page?.slug === 'runtime'
      ? 'Keep live execution clear with visible state, explicit system health, and faster action paths during runtime pressure.'
      : page?.slug === 'intelligence'
        ? 'Translate technical context into operator decisions by connecting research framing, narrative signals, and timing clarity.'
        : 'Clear operating context helps teams decide when a strategy, account, or runtime workflow is ready for the next step.';

  const serviceVariant =
    page?.slug === 'runtime'
      ? 'runtime'
      : page?.slug === 'intelligence'
        ? 'intelligence'
        : page?.slug === 'security'
          ? 'security'
          : 'research';

  const serviceVisualTags =
    page?.slug === 'runtime'
        ? ['System health', 'Action priority', 'Runtime continuity']
      : page?.slug === 'intelligence'
        ? ['Technical context', 'Timing clarity', 'Conviction support']
        : page?.slug === 'security'
          ? ['Access trust', '2FA readiness', 'Onboarding clarity']
          : ['Backtest ranking', 'Risk framing', 'Promotion standard'];

  if (!page) {
    return <Navigate to="/" replace />;
  }

  const outcomeCards = isSecurityPage ? securityOutcomeFlow : serviceOutcomeFlow;

  return (
    <PublicSiteShell>
      <div className="public-modern-page">
        <section className={`public-modern-hero public-modern-hero-${serviceVariant}`}>
          <div className="public-modern-container public-modern-hero-grid">
            <MotionReveal className="public-modern-copy" distancePx={18}>
              <div className="surface-label">
                <Sparkles className="h-3.5 w-3.5" />
                {page.kicker}
              </div>
              <h1>{page.title}</h1>
              <p>{page.heroIntro}</p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link to="/register" className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3 text-sm font-semibold text-white">
                  Start execution review
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link to="/pricing" className="premium-button premium-button-secondary justify-center px-6 py-3 text-sm font-medium">
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
                  <strong>{page.navLabel.toUpperCase()} DESK</strong>
                </div>
                <ServicePulseIllustration variant={serviceVariant} />
              </div>
              <div className="public-visual-tags">
                {serviceVisualTags.map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
            </MotionReveal>
          </div>
        </section>

        <section className="public-modern-container public-proof-strip">
          {page.heroStats.slice(0, 3).map(([label, body], index) => (
            <MotionReveal key={label} delayMs={index * 50} className="public-proof-item">
              <span>0{index + 1}</span>
              <strong>{label}</strong>
              <p>{body}</p>
            </MotionReveal>
          ))}
        </section>

        <section className="public-modern-container public-market-section">
          <MotionReveal distancePx={18}>
            <PublicMarketPulsePanel
              eyebrow={`${page.navLabel} execution context`}
              title="Workflow readiness, ownership, and execution quality stay visible beside the work."
              description={`Use execution context to connect ${page.navLabel.toLowerCase()} decisions with delivery quality, risk, and operator timing.`}
            />
          </MotionReveal>
        </section>

        <section className="public-modern-band">
          <div className="public-modern-container public-modern-split">
            <MotionReveal className="public-modern-section-copy" distancePx={18}>
              <div className="surface-label">Capability layer</div>
              <h2>Built to make the next operating decision obvious.</h2>
              <p>
                The public page should explain the platform quickly, then move the user toward
                execution review with confidence. This layer turns {page.navLabel.toLowerCase()} into a
                clear operational promise instead of a generic feature list.
              </p>
            </MotionReveal>

            <div className="public-capability-grid">
              {page.corePoints.map((point, index) => (
                <MotionReveal key={point.title} delayMs={index * 70} className="public-capability-card">
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <h3>{point.title}</h3>
                  <p>{point.body}</p>
                </MotionReveal>
              ))}
            </div>
          </div>
        </section>

        {isSecurityPage && (
          <section className="public-modern-container public-readiness-rail">
            {securityReadinessSteps.map((step, index) => (
              <MotionReveal key={step.title} delayMs={index * 60} className="public-readiness-step">
                <span>Readiness 0{index + 1}</span>
                <strong>{step.title}</strong>
                <p>{step.body}</p>
              </MotionReveal>
            ))}
          </section>
        )}

        <section className="public-modern-container public-outcome-stage">
          <MotionReveal className="public-modern-section-copy" distancePx={18}>
            <div className="surface-label">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Operator outcomes
            </div>
            <h2>{outcomesHeadline}</h2>
            <p>{outcomesIntro}</p>
          </MotionReveal>

          <div className="public-outcome-grid">
            {outcomeCards.map((item, index) => (
              <MotionReveal key={item.stage + item.detail} delayMs={index * 70} className="public-outcome-modern">
                <span>{item.stage}</span>
                <strong>{item.detail}</strong>
                <p>{item.note}</p>
              </MotionReveal>
            ))}
          </div>
        </section>

        <section className="public-modern-container public-note-row">
          {page.operatorNotes.map((note, index) => (
            <MotionReveal key={note.label} delayMs={index * 70} className="public-note-modern">
              <span>{note.label}</span>
              <p>{note.body}</p>
            </MotionReveal>
          ))}
        </section>

        <section className="public-modern-container public-modern-cta">
          <MotionReveal className="public-modern-cta-inner" distancePx={18}>
            <div>
              <div className="surface-label">
                <ShieldCheck className="h-4 w-4" />
                Continue the journey
              </div>
              <h2>Continue from {page.navLabel.toLowerCase()} into execution review.</h2>
              <p>Review engagement options, create an account, and complete security onboarding before execution access.</p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link to="/pricing" className="premium-button premium-button-secondary justify-center px-6 py-3 text-sm font-medium">
                View engagement model
              </Link>
              <Link to="/register" className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3 text-sm font-semibold text-white">
                Start execution review
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </MotionReveal>
        </section>
      </div>
    </PublicSiteShell>
  );
};

export default PublicServicePage;
