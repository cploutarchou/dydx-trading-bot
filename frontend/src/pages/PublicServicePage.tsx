import { ArrowRight, CheckCircle2, ShieldCheck, Sparkles } from 'lucide-react';
import React from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import MotionReveal from '../components/MotionReveal';
import PublicSiteShell from '../components/PublicSiteShell';
import { servicePages } from '../content/publicSite';

export const PublicServicePage: React.FC = () => {
  const { slug } = useParams();
  const page = servicePages.find((item) => item.slug === slug);

  if (!page) {
    return <Navigate to="/" replace />;
  }

  return (
    <PublicSiteShell>
      <section className="service-hero public-shell-container">
        <MotionReveal className="service-hero-grid lg:items-end">
          <div>
            <div className="surface-label">
              <Sparkles className="h-3.5 w-3.5" />
              {page.kicker}
            </div>
            <h1 className="mt-6 max-w-4xl text-4xl font-bold leading-[1.06] text-white sm:text-5xl">
              {page.title}
            </h1>
          </div>
          <p className="max-w-2xl text-base leading-8 text-slate-300 lg:pb-1">{page.heroIntro}</p>
        </MotionReveal>

        <MotionReveal delayMs={100} className="service-stats mt-10">
          <div className="service-stats-grid">
            {page.heroStats.map(([label, body]) => (
              <div key={label} className="service-stat-item">
                <p className="text-sm font-semibold text-cyan-300">{label}</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">{body}</p>
              </div>
            ))}
          </div>
        </MotionReveal>
      </section>

      <section className="service-core-shell">
        <div className="public-shell-container service-core-grid">
          {page.corePoints.map((point, index) => (
            <MotionReveal key={point.title} delayMs={index * 70} className="service-core-card">
              <p className="font-mono text-sm text-emerald-300">0{index + 1}</p>
              <h2 className="mt-4 text-2xl font-semibold text-white">{point.title}</h2>
              <p className="mt-4 text-sm leading-7 text-slate-400">{point.body}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="service-outcomes public-shell-container">
        <MotionReveal className="grid gap-8 lg:grid-cols-[minmax(0,0.95fr),minmax(22rem,0.65fr)]">
          <div>
            <div className="surface-label">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Operator outcomes
            </div>
            <h2 className="mt-5 text-3xl font-bold text-white">Decisions operators can make.</h2>
          </div>
          <p className="max-w-2xl text-sm leading-7 text-slate-400 lg:pt-10">
            Clear operating context helps teams decide when a strategy, account, or runtime workflow
            is ready for the next step.
          </p>
        </MotionReveal>

        <div className="service-outcome-list mt-10">
          {page.outcomes.map((outcome, index) => (
            <MotionReveal key={outcome} delayMs={index * 60}>
              <div className="service-outcome-item grid gap-4 py-5 md:grid-cols-[4rem,1fr] md:items-start">
                <span className="font-mono text-sm text-cyan-300">0{index + 1}</span>
                <p className="text-lg leading-8 text-slate-200">{outcome}</p>
              </div>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="service-notes public-shell-container">
        <div className="service-notes-grid grid gap-6 lg:grid-cols-2">
          {page.operatorNotes.map((note, index) => (
            <MotionReveal key={note.label} delayMs={index * 80} className="service-note-card">
              <p className="text-[11px] font-semibold uppercase text-slate-500">{note.label}</p>
              <p className="mt-3 text-lg leading-8 text-slate-200">{note.body}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="service-cta public-shell-container">
        <MotionReveal className="service-cta-inner grid gap-8 lg:grid-cols-[minmax(0,0.95fr),minmax(22rem,0.65fr)] lg:items-center">
          <div>
            <div className="surface-label">
              <ShieldCheck className="h-4 w-4" />
              Continue the journey
            </div>
            <h2 className="mt-5 text-3xl font-bold text-white">
              Continue from {page.navLabel.toLowerCase()} into evaluation.
            </h2>
          </div>
          <div>
            <p className="max-w-2xl text-sm leading-7 text-slate-400">
              Review pricing, create an account, and complete security onboarding before live
              access.
            </p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/pricing"
                className="premium-button premium-button-secondary justify-center px-6 py-3 text-sm font-medium"
              >
                View pricing
              </Link>
              <Link
                to="/register"
                className="premium-button premium-button-primary justify-center px-6 py-3 text-sm font-semibold text-white"
              >
                Start free evaluation
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </MotionReveal>
      </section>
    </PublicSiteShell>
  );
};

export default PublicServicePage;
