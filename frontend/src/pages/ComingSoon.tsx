import { ArrowRight, LockKeyhole, Radar, ShieldCheck, WalletCards } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import BrandMark from '../components/BrandMark';

type PreviewMode = 'operator' | 'strategy' | 'security';

const readinessItems = [
  {
    title: 'DeFi research',
    body: 'Market intelligence, pair context, and strategy framing before capital moves.',
    progress: 86,
    status: 'Active',
  },
  {
    title: 'Backtest validation',
    body: 'Evidence-first promotion from hypothesis to controlled runtime.',
    progress: 91,
    status: 'Reviewing',
  },
  {
    title: 'Operator access',
    body: 'Role-based entry, MFA posture, and credential controls before live workflows.',
    progress: 78,
    status: 'Hardening',
  },
] as const;

const previewModes: Array<{ id: PreviewMode; label: string }> = [
  { id: 'operator', label: 'Operator cockpit' },
  { id: 'strategy', label: 'Strategy lab' },
  { id: 'security', label: 'Security controls' },
];

const previewModeContent: Record<
  PreviewMode,
  {
    headline: string;
    description: string;
    metrics: Array<{ label: string; value: string }>;
  }
> = {
  operator: {
    headline: 'Live command center',
    description:
      'Track strategy state, health, and execution confidence from one operator-first surface.',
    metrics: [
      { label: 'Live runtimes', value: '24/7' },
      { label: 'Status visibility', value: 'Sub-second' },
      { label: 'Signal density', value: 'High' },
    ],
  },
  strategy: {
    headline: 'Research to runtime',
    description:
      'Move from hypothesis to validated execution using a guided backtest and promotion flow.',
    metrics: [
      { label: 'Backtest coverage', value: 'Multi-market' },
      { label: 'Promotion flow', value: 'Structured' },
      { label: 'Risk checks', value: 'Built-in' },
    ],
  },
  security: {
    headline: 'Access with safeguards',
    description:
      'Layered auth, role controls, and credential boundaries keep operations protected by design.',
    metrics: [
      { label: 'MFA posture', value: 'Required' },
      { label: 'Role scoping', value: 'Granular' },
      { label: 'Credential flow', value: 'Backend-only' },
    ],
  },
};

interface ComingSoonPageProps {
  message?: string;
}

export const ComingSoonPage = ({ message }: ComingSoonPageProps) => {
  const [previewMode, setPreviewMode] = useState<PreviewMode>('operator');

  const description =
    message?.trim() ||
    'Public access is paused while the platform is prepared for launch. Existing operators can still sign in, but the workspace remains hidden until launch.';

  const activePreview = useMemo(() => previewModeContent[previewMode], [previewMode]);

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

            <div className="mt-7">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                Product preview
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {previewModes.map((mode) => {
                  const isActive = mode.id === previewMode;
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => setPreviewMode(mode.id)}
                      className={`rounded-lg border px-3 py-2 text-xs font-semibold transition sm:text-sm ${
                        isActive
                          ? 'border-cyan-400/60 bg-cyan-500/10 text-cyan-200'
                          : 'border-slate-700/70 bg-slate-950/60 text-slate-300 hover:border-slate-500/80 hover:text-white'
                      }`}
                    >
                      {mode.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-slate-700/70 bg-slate-950/55 p-4 sm:p-5">
              <p className="text-sm font-semibold text-white">{activePreview.headline}</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">{activePreview.description}</p>
              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                {activePreview.metrics.map((metric) => (
                  <div
                    key={metric.label}
                    className="rounded-lg border border-slate-700/70 bg-slate-900/70 p-3"
                  >
                    <p className="text-xs uppercase tracking-wide text-slate-400">{metric.label}</p>
                    <p className="mt-1 text-sm font-semibold text-cyan-200">{metric.value}</p>
                  </div>
                ))}
              </div>
            </div>

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

          <div className="platform-panel light-dark-surface coming-soon-surface coming-soon-panel-card p-5 sm:p-6">
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
              {readinessItems.map((item, index) => (
                <div
                  key={item.title}
                  className="rounded-lg border border-slate-700/60 bg-slate-950/55 p-4"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-xs font-semibold text-cyan-200">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-white">{item.title}</p>
                        <span className="rounded-md border border-slate-700/70 bg-slate-900/70 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-slate-300">
                          {item.status}
                        </span>
                      </div>
                      <p className="mt-1 text-sm leading-6 text-slate-400">{item.body}</p>
                      <div className="mt-3 h-1.5 w-full rounded-full bg-slate-800">
                        <div
                          className="h-1.5 rounded-full bg-gradient-to-r from-cyan-400/85 to-violet-400/80"
                          style={{ width: `${item.progress}%` }}
                        />
                      </div>
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
