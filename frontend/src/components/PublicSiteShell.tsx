import { ArrowRight, Menu, Radio, X } from 'lucide-react';
import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

interface PublicSiteShellProps {
  children: React.ReactNode;
}

const navItems = [
  { label: 'Platform', href: '/#platform' },
  { label: 'Subscriptions', href: '/pricing' },
  { label: 'Why Us', href: '/#why' },
  { label: 'FAQ', href: '/#faq' },
];

export const PublicSiteShell: React.FC<PublicSiteShellProps> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const closeMobile = () => setMobileOpen(false);
  const isPricingPage = location.pathname === '/pricing';

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.12),_transparent_20%),radial-gradient(circle_at_top_right,_rgba(59,130,246,0.14),_transparent_22%),linear-gradient(180deg,#07111f_0%,#08111d_46%,#050c16_100%)] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(rgba(148,163,184,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.03)_1px,transparent_1px)] bg-[size:72px_72px] [mask-image:linear-gradient(180deg,rgba(255,255,255,0.5),rgba(255,255,255,0.04))]" />

      <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-xl">
        <div className="public-shell-container flex items-center justify-between gap-3 py-4 sm:gap-4">
          <Link to="/" className="group flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 via-blue-500 to-emerald-400 text-lg shadow-lg shadow-cyan-500/20 transition duration-300 group-hover:scale-[1.04] group-hover:shadow-cyan-400/30 sm:h-11 sm:w-11">
              ∿
            </div>
            <div>
              <p className="text-sm font-semibold text-white">dYdX Arbitrage OS</p>
              <p className="hidden text-[11px] uppercase tracking-[0.16em] text-slate-500 sm:block">
                Institutional DeFi Platform
              </p>
            </div>
          </Link>

          <nav className="hidden items-center gap-1 lg:flex">
            {navItems.map((item) =>
              item.href.startsWith('/#') && isPricingPage ? (
                <Link
                  key={item.href}
                  to="/"
                  className="rounded-xl px-4 py-2 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white"
                >
                  {item.label}
                </Link>
              ) : (
                <a
                  key={item.href}
                  href={item.href}
                  className="nav-link-premium rounded-xl px-4 py-2 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white"
                >
                  {item.label}
                </a>
              )
            )}
          </nav>

          <div className="hidden items-center gap-3 lg:flex">
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1.5 text-[11px] uppercase tracking-[0.16em] text-slate-500">
              <span className="pulse-ring relative flex h-2.5 w-2.5 items-center justify-center">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </span>
              Live-ready DeFi Ops
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-800/80 bg-slate-950/80 px-3 py-1.5 text-[11px] uppercase tracking-[0.16em] text-slate-500">
              <Radio className="h-3.5 w-3.5 text-cyan-300" />
              Websocket-native control plane
            </div>
            <Link
              to="/login"
              className="premium-button premium-button-secondary rounded-xl px-4 py-2 text-sm"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="premium-button premium-button-primary rounded-xl px-4 py-2 text-sm font-semibold text-white"
            >
              Start Evaluation
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <button
            type="button"
            onClick={() => setMobileOpen((current) => !current)}
            className="inline-flex rounded-2xl border border-slate-800 bg-slate-900/80 p-2.5 text-slate-300 lg:hidden"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {mobileOpen && (
          <div className="mobile-shell-panel border-t border-slate-800 bg-slate-950/95 px-4 py-4 lg:hidden">
            <div className="space-y-2">
              {navItems.map((item) =>
                item.href.startsWith('/#') && isPricingPage ? (
                  <Link
                    key={item.href}
                    to="/"
                    onClick={closeMobile}
                    className="block rounded-xl px-4 py-3 text-sm text-slate-300 transition hover:bg-slate-900"
                  >
                    {item.label}
                  </Link>
                ) : (
                  <a
                    key={item.href}
                    href={item.href}
                    onClick={closeMobile}
                    className="block rounded-xl px-4 py-3 text-sm text-slate-300 transition hover:bg-slate-900"
                  >
                    {item.label}
                  </a>
                )
              )}
              <div className="grid grid-cols-2 gap-2 pt-2">
                <Link
                  to="/login"
                  onClick={closeMobile}
                  className="rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-center text-sm text-slate-200"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  onClick={closeMobile}
                  className="premium-button premium-button-primary rounded-xl px-4 py-3 text-center text-sm font-semibold text-white"
                >
                  Start Evaluation
                </Link>
              </div>
            </div>
          </div>
        )}
      </header>

      <main className="relative z-10">{children}</main>

      <footer className="border-t border-slate-800/80 bg-slate-950/70">
        <div className="public-shell-container grid gap-8 py-10 lg:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <p className="text-lg font-semibold text-white">dYdX Arbitrage OS</p>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">
              A production-grade platform for quantitative DeFi teams running arbitrage, research,
              live execution, and runtime operations from one cockpit.
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Platform</p>
            <div className="mt-3 space-y-2 text-sm text-slate-400">
              <Link to="/" className="block transition hover:text-white">
                Overview
              </Link>
              <Link to="/pricing" className="block transition hover:text-white">
                Pricing
              </Link>
              <Link to="/login" className="block transition hover:text-white">
                Sign In
              </Link>
            </div>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Operating Model</p>
            <div className="mt-3 space-y-2 text-sm text-slate-400">
              <p>Live trading telemetry</p>
              <p>Backtest intelligence</p>
              <p>Institutional-grade operator UX</p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default PublicSiteShell;
