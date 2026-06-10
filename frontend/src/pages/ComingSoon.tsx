import { ArrowRight, LockKeyhole, Radar, ShieldCheck, WalletCards } from 'lucide-react';
import { Link } from 'react-router-dom';
import BrandMark from '../components/BrandMark';

const readinessItems = [
  [
    'DeFi research',
    'Market intelligence, pair context, and strategy framing before capital moves.',
  ],
  ['Backtest validation', 'Evidence-first promotion from hypothesis to controlled runtime.'],
  [
    'Operator access',
    'Role-based entry, MFA posture, and credential controls before live workflows.',
  ],
] as const;

interface ComingSoonPageProps {
  message?: string;
}

export const ComingSoonPage = ({ message }: ComingSoonPageProps) => {
  const description =
    message?.trim() ||
    'Public access is paused while the platform is prepared for launch. Existing operators can still sign in, but the workspace remains hidden until launch.';

  return (
    <main className="premium-shell light-dark-surface coming-soon-surface min-h-screen overflow-hidden text-white">
      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex items-center justify-between gap-4">
          <BrandMark subtitle="DeFi execution platform" />
          <Link
            to="/login"
            className="coming-soon-signin-link inline-flex items-center gap-2 rounded-lg border border-slate-700/70 bg-slate-950/70 px-4 py-2.5 text-sm font-semibold transition hover:border-cyan-500/40"
          >
            Existing credentials sign in
            <ArrowRight className="h-4 w-4" />
          </Link>
        </header>

        <section className="grid flex-1 items-center gap-10 py-12 lg:grid-cols-[1.05fr,0.95fr] lg:py-16">
          <div>
            <div className="surface-label">
              <Radar className="h-3.5 w-3.5" />
              Controlled launch in progress
            </div>
            <h1 className="mt-5 max-w-4xl text-4xl font-semibold leading-tight text-white sm:text-5xl lg:text-6xl">
              ExecutionLab is coming soon.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">
              {description}
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/login"
                className="premium-button premium-button-primary justify-center px-6 py-3 text-sm text-white"
              >
                Use existing credentials
                <ArrowRight className="h-4 w-4" />
              </Link>
              <span className="coming-soon-status-pill inline-flex items-center justify-center rounded-lg border border-slate-700/70 bg-slate-950/60 px-5 py-3 text-sm font-medium text-slate-300">
                Public access currently paused
              </span>
            </div>
          </div>

          <div className="platform-panel light-dark-surface coming-soon-surface p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-white">Launch readiness</p>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  The public site is in controlled-release mode. Only sign-in and required account
                  recovery pages remain available while launch is paused.
                </p>
              </div>
              <span className="rounded-lg border border-cyan-500/25 bg-cyan-500/10 p-2 text-cyan-200">
                <ShieldCheck className="h-5 w-5" />
              </span>
            </div>

            <div className="mt-6 grid gap-3">
              {readinessItems.map(([title, body], index) => (
                <div
                  key={title}
                  className="rounded-lg border border-slate-700/60 bg-slate-950/55 p-4"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-xs font-semibold text-cyan-200">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-white">{title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-400">{body}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <div className="coming-soon-positive-card rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-4">
                <LockKeyhole className="coming-soon-positive-icon h-5 w-5 text-emerald-200" />
                <p className="coming-soon-positive-title mt-3 text-sm font-semibold text-emerald-100">
                  Access controlled
                </p>
                <p className="coming-soon-positive-copy mt-1 text-xs leading-5 text-emerald-100/70">
                  Existing operators can continue through sign-in.
                </p>
              </div>
              <div className="coming-soon-violet-card rounded-lg border border-violet-500/25 bg-violet-500/10 p-4">
                <WalletCards className="coming-soon-violet-icon h-5 w-5 text-violet-200" />
                <p className="coming-soon-violet-title mt-3 text-sm font-semibold text-violet-100">
                  Credentials protected
                </p>
                <p className="coming-soon-violet-copy mt-1 text-xs leading-5 text-violet-100/70">
                  Runtime access remains behind authenticated controls.
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
};

export default ComingSoonPage;
