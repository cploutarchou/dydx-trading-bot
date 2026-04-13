import { Activity, ArrowRight, Menu, Moon, ShieldCheck, Sun, Waypoints, X } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { getPrimaryCta, publicNavItems } from '../content/publicSite';
import { useUIPreferencesStore } from '../store/uiPreferences';

interface PublicSiteShellProps {
  children: React.ReactNode;
  hideFooter?: boolean;
}

const trustIndicators = [
  { icon: Activity, label: 'Realtime operator telemetry' },
  { icon: ShieldCheck, label: 'Security-first onboarding' },
  { icon: Waypoints, label: 'Research-to-runtime workflow' },
];

const conversionTrustRows = [
  ['Free start', 'Evaluate the workflow before any live commercial step'],
  ['Secure onboarding', 'Account readiness and 2FA posture before runtime controls'],
  ['Operator clarity', 'Research, pricing, and runtime path explained in one flow'],
] as const;

const PUBLIC_THEME_KEY = 'ui.publicTheme';

export const PublicSiteShell: React.FC<PublicSiteShellProps> = ({
  children,
  hideFooter = false,
}) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const theme = useUIPreferencesStore((state) => state.theme);
  const setTheme = useUIPreferencesStore((state) => state.setTheme);
  const toggleTheme = useUIPreferencesStore((state) => state.toggleTheme);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const storedPublicTheme = window.localStorage.getItem(PUBLIC_THEME_KEY);
    if (storedPublicTheme !== 'dark' && storedPublicTheme !== 'light') {
      setTheme('dark');
      window.localStorage.setItem(PUBLIC_THEME_KEY, 'dark');
      return;
    }
    if (storedPublicTheme !== theme) {
      setTheme(storedPublicTheme);
    }
  }, [setTheme, theme]);

  const handleToggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(PUBLIC_THEME_KEY, nextTheme);
    }
    toggleTheme();
  };

  const primaryCta = useMemo(() => getPrimaryCta(location.pathname), [location.pathname]);

  const closeMobile = () => setMobileOpen(false);
  const footerItems = publicNavItems.filter((item) => item.path !== '/pricing');

  return (
    <div className="public-site-shell min-h-screen overflow-x-hidden text-white">
      <header className="sticky top-0 z-50 border-b border-stone-800/90 bg-[#070807]/92 backdrop-blur-xl">
        <div className="public-shell-container flex min-h-14 items-center justify-between gap-2.5 py-2 sm:min-h-16 sm:gap-3 sm:py-2.5">
          <Link to="/" className="group flex items-center gap-2.5 sm:gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-teal-300/30 bg-teal-400/12 text-sm font-semibold text-teal-100 transition duration-300 group-hover:border-teal-200/50 sm:h-10 sm:w-10">
              dY
            </div>
            <div>
              <p className="text-[13px] font-semibold text-white sm:text-sm">dYdX Arbitrage OS</p>
              <p className="text-[10px] uppercase text-slate-500 sm:text-[11px]">
                DeFi operator platform
              </p>
            </div>
          </Link>

          <nav className="hidden items-center gap-0.5 xl:flex">
            {publicNavItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`public-nav-link rounded-lg px-3 py-2 text-sm transition ${
                    isActive
                      ? 'is-active bg-teal-500/12 text-teal-100'
                      : 'text-slate-400 hover:bg-stone-900 hover:text-white'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="hidden items-center gap-2.5 lg:flex">
            <button
              type="button"
              onClick={handleToggleTheme}
              className="premium-button premium-button-secondary px-3 py-2 text-sm"
              title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            >
              {theme === 'dark' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
              {theme === 'dark' ? 'Dark' : 'Light'}
            </button>
            <div className="workspace-chip border-emerald-400/20 text-emerald-200">
              <span className="pulse-ring relative flex h-2.5 w-2.5 items-center justify-center">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </span>
              Evaluation open
            </div>
            <Link
              to="/login"
              className="premium-button premium-button-secondary px-3.5 py-2 text-sm"
            >
              Sign in
            </Link>
            <Link
              to={primaryCta.href}
              className="premium-button premium-button-primary px-3.5 py-2 text-sm font-semibold text-white"
            >
              {primaryCta.label}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <button
            type="button"
            onClick={() => setMobileOpen((current) => !current)}
            className="inline-flex rounded-lg border border-stone-800 bg-stone-950/80 p-2 text-slate-300 lg:hidden"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {mobileOpen && (
          <div className="mobile-shell-panel border-t border-stone-800 bg-[#080a0b]/98 px-4 py-4 lg:hidden">
            <div className="space-y-3">
              {trustIndicators.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.label}
                    className="flex items-center gap-3 rounded-lg border border-stone-800 bg-stone-950/60 px-4 py-3 text-sm text-slate-300"
                  >
                    <Icon className="h-4 w-4 text-cyan-300" />
                    <span>{item.label}</span>
                  </div>
                );
              })}

              <div className="rounded-lg border border-stone-800 bg-stone-950/60 p-2">
                {publicNavItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={closeMobile}
                    className="block rounded-lg px-4 py-3 text-sm text-slate-300 transition hover:bg-stone-900/80"
                  >
                    {item.label}
                  </Link>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={handleToggleTheme}
                  className="rounded-lg border border-stone-800 bg-stone-950 px-4 py-3 text-center text-sm text-slate-200"
                >
                  {theme === 'dark' ? 'Dark mode' : 'Light mode'}
                </button>
                <Link
                  to="/login"
                  onClick={closeMobile}
                  className="rounded-lg border border-stone-800 bg-stone-950 px-4 py-3 text-center text-sm text-slate-200"
                >
                  Sign in
                </Link>
                <Link
                  to={primaryCta.href}
                  onClick={closeMobile}
                  className="premium-button premium-button-primary col-span-2 px-4 py-3 text-center text-sm font-semibold text-white"
                >
                  {primaryCta.label}
                </Link>
              </div>
            </div>
          </div>
        )}
      </header>

      <main className="relative z-10">{children}</main>

      {!hideFooter && (
        <section className="public-shell-container py-8">
          <div className="public-trust-strip">
            <div>
              <p className="text-[11px] font-semibold uppercase text-slate-500">
                Why teams convert
              </p>
              <p className="mt-2 text-xl font-semibold text-white">
                Trust first. Live access later.
              </p>
            </div>

            <div className="public-trust-grid">
              {conversionTrustRows.map(([title, body]) => (
                <div key={title} className="public-trust-item">
                  <p className="text-sm font-semibold text-white">{title}</p>
                  <p className="mt-1 text-xs leading-6 text-slate-400">{body}</p>
                </div>
              ))}
            </div>

            <Link
              to="/register"
              className="premium-button premium-button-primary justify-center px-5 py-3 text-sm font-semibold text-white lg:self-center"
            >
              Start free evaluation
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      )}

      {!hideFooter && (
        <footer className="relative z-10 border-t border-stone-800/80 bg-[#060706]/96">
          <div className="public-shell-container py-6">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-teal-300/25 bg-teal-400/10 text-xs font-semibold text-teal-100">
                  dY
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">dYdX Arbitrage OS</p>
                  <p className="text-xs text-slate-500">
                    Research, runtime, market intel, and onboarding.
                  </p>
                </div>
              </div>

              <nav className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-400">
                {footerItems.map((item) => (
                  <Link key={item.path} to={item.path} className="transition hover:text-white">
                    {item.label}
                  </Link>
                ))}
              </nav>

              <div className="flex flex-wrap items-center gap-3">
                <Link
                  to="/pricing"
                  className="text-sm font-medium text-slate-300 transition hover:text-white"
                >
                  Pricing
                </Link>
                <Link
                  to="/login"
                  className="text-sm font-medium text-slate-300 transition hover:text-white"
                >
                  Sign in
                </Link>
                <Link
                  to="/register"
                  className="rounded-lg border border-teal-400/25 bg-teal-500/10 px-3.5 py-2 text-sm font-semibold text-teal-100 transition hover:border-teal-300/50"
                >
                  Start free evaluation
                </Link>
              </div>
            </div>

            <div className="mt-5 flex flex-col gap-3 border-t border-stone-800 pt-4 text-xs text-slate-500 md:flex-row md:items-center md:justify-between">
              <p>Start free. Prove fit. Move to live access with confidence.</p>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <Link to="/services/security" className="transition hover:text-slate-300">
                  Security onboarding
                </Link>
                <span>Account readiness</span>
                <span>Runtime visibility</span>
              </div>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
};

export default PublicSiteShell;
