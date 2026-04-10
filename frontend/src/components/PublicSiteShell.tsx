import {
  Activity,
  ArrowRight,
  Command,
  Menu,
  ShieldCheck,
  Waypoints,
  X,
} from 'lucide-react';
import React, { useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

interface PublicSiteShellProps {
  children: React.ReactNode;
}

const navItems = [
  { label: 'Platform', href: '/#platform' },
  { label: 'Workflow', href: '/#workflow' },
  { label: 'Pricing', href: '/pricing' },
  { label: 'Security', href: '/#security' },
  { label: 'FAQ', href: '/#faq' },
];

const trustIndicators = [
  { icon: Activity, label: 'Realtime operator telemetry' },
  { icon: ShieldCheck, label: 'Security-first onboarding' },
  { icon: Waypoints, label: 'Research-to-runtime workflow' },
];

export const PublicSiteShell: React.FC<PublicSiteShellProps> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const isPricingPage = location.pathname === '/pricing';
  const primaryCta = useMemo(
    () => (location.pathname === '/pricing' ? { href: '/register', label: 'Start evaluation' } : { href: '/pricing', label: 'Review plans' }),
    [location.pathname]
  );

  const closeMobile = () => setMobileOpen(false);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.14),_transparent_18%),radial-gradient(circle_at_84%_8%,_rgba(59,130,246,0.16),_transparent_22%),linear-gradient(180deg,#06101d_0%,#091221_48%,#050a14_100%)] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(rgba(148,163,184,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.03)_1px,transparent_1px)] bg-[size:68px_68px] [mask-image:linear-gradient(180deg,rgba(255,255,255,0.52),rgba(255,255,255,0.04))]" />

      <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/78 backdrop-blur-xl">
        <div className="public-shell-container flex items-center justify-between gap-4 py-4">
          <Link to="/" className="group flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-emerald-400 text-lg font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition duration-300 group-hover:scale-[1.03]">
              ∿
            </div>
            <div>
              <p className="text-sm font-semibold text-white">dYdX Arbitrage OS</p>
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                Fintech-grade DeFi operator platform
              </p>
            </div>
          </Link>

          <nav className="hidden items-center gap-1 xl:flex">
            {navItems.map((item) =>
              item.href.startsWith('/#') && isPricingPage ? (
                <Link
                  key={item.href}
                  to="/"
                  className="nav-link-premium rounded-xl px-4 py-2 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white"
                >
                  {item.label}
                </Link>
              ) : item.href.startsWith('/#') ? (
                <a
                  key={item.href}
                  href={item.href}
                  className="nav-link-premium rounded-xl px-4 py-2 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white"
                >
                  {item.label}
                </a>
              ) : (
                <Link
                  key={item.href}
                  to={item.href}
                  className="nav-link-premium rounded-xl px-4 py-2 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white"
                >
                  {item.label}
                </Link>
              )
            )}
          </nav>

          <div className="hidden items-center gap-3 lg:flex">
            <div className="workspace-chip border-emerald-400/20 text-emerald-200">
              <span className="pulse-ring relative flex h-2.5 w-2.5 items-center justify-center">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </span>
              Operator workflow active
            </div>
            <Link
              to="/login"
              className="premium-button premium-button-secondary rounded-xl px-4 py-2 text-sm"
            >
              Sign in
            </Link>
            <Link
              to={primaryCta.href}
              className="premium-button premium-button-primary rounded-xl px-4 py-2 text-sm font-semibold text-white"
            >
              {primaryCta.label}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <button
            type="button"
            onClick={() => setMobileOpen((current) => !current)}
            className="inline-flex rounded-2xl border border-slate-800 bg-slate-900/80 p-2.5 text-slate-300 lg:hidden"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {mobileOpen && (
          <div className="mobile-shell-panel border-t border-slate-800 bg-slate-950/95 px-4 py-4 lg:hidden">
            <div className="space-y-3">
              {trustIndicators.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.label}
                    className="flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm text-slate-300"
                  >
                    <Icon className="h-4 w-4 text-cyan-300" />
                    <span>{item.label}</span>
                  </div>
                );
              })}

              <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-2">
                {navItems.map((item) =>
                  item.href.startsWith('/#') && isPricingPage ? (
                    <Link
                      key={item.href}
                      to="/"
                      onClick={closeMobile}
                      className="block rounded-xl px-4 py-3 text-sm text-slate-300 transition hover:bg-slate-800/80"
                    >
                      {item.label}
                    </Link>
                  ) : item.href.startsWith('/#') ? (
                    <a
                      key={item.href}
                      href={item.href}
                      onClick={closeMobile}
                      className="block rounded-xl px-4 py-3 text-sm text-slate-300 transition hover:bg-slate-800/80"
                    >
                      {item.label}
                    </a>
                  ) : (
                    <Link
                      key={item.href}
                      to={item.href}
                      onClick={closeMobile}
                      className="block rounded-xl px-4 py-3 text-sm text-slate-300 transition hover:bg-slate-800/80"
                    >
                      {item.label}
                    </Link>
                  )
                )}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Link
                  to="/login"
                  onClick={closeMobile}
                  className="rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-center text-sm text-slate-200"
                >
                  Sign in
                </Link>
                <Link
                  to={primaryCta.href}
                  onClick={closeMobile}
                  className="premium-button premium-button-primary rounded-xl px-4 py-3 text-center text-sm font-semibold text-white"
                >
                  {primaryCta.label}
                </Link>
              </div>
            </div>
          </div>
        )}
      </header>

      <main className="relative z-10">{children}</main>

      <footer className="border-t border-slate-800/80 bg-slate-950/72">
        <div className="public-shell-container py-10">
          <div className="signal-card signal-card-strong rounded-[1.9rem] px-6 py-6 sm:px-8">
            <div className="grid gap-8 lg:grid-cols-[1.2fr,0.8fr] lg:items-end">
              <div>
                <div className="surface-label">
                  <Command className="h-3.5 w-3.5" />
                  Product direction
                </div>
                <h2 className="mt-4 max-w-2xl text-2xl font-semibold text-white sm:text-3xl">
                  Built to feel trustworthy before the first trade and fast once the desk is live.
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
                  dYdX Arbitrage OS brings public-site clarity, premium onboarding, and operator-first
                  workspace design into one coherent product surface.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                {trustIndicators.map((item) => {
                  const Icon = item.icon;
                  return (
                    <div key={item.label} className="metric-tile px-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className="rounded-xl bg-cyan-500/10 p-2 text-cyan-300">
                          <Icon className="h-4 w-4" />
                        </div>
                        <p className="text-sm font-medium text-slate-100">{item.label}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="mt-10 grid gap-8 lg:grid-cols-[1.2fr,0.8fr,0.8fr]">
            <div>
              <p className="text-sm font-semibold text-white">dYdX Arbitrage OS</p>
              <p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">
                Premium DeFi product design for research, live execution, and runtime confidence.
              </p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Navigate</p>
              <div className="mt-3 space-y-2 text-sm text-slate-400">
                <Link to="/" className="block transition hover:text-white">
                  Overview
                </Link>
                <Link to="/pricing" className="block transition hover:text-white">
                  Pricing
                </Link>
                <Link to="/login" className="block transition hover:text-white">
                  Sign in
                </Link>
              </div>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Design stance</p>
              <div className="mt-3 space-y-2 text-sm text-slate-400">
                <p>Dense where operators need signal</p>
                <p>Clear onboarding before auth</p>
                <p>Fintech-first trust semantics</p>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default PublicSiteShell;
