import React, { useEffect, useRef, useState } from 'react';

const TURNSTILE_SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
const TURNSTILE_SITE_KEY =
  import.meta.env.VITE_TURNSTILE_SITE_KEY?.trim() || '0x4AAAAAAC-COw-JrfsjGsrp';

type TurnstileStatus = 'loading' | 'ready' | 'verified' | 'expired' | 'error';
type TurnstileWidgetId = string;

interface TurnstileRenderOptions {
  sitekey: string;
  action: string;
  theme: 'auto' | 'dark' | 'light';
  size: 'normal' | 'compact' | 'flexible';
  callback: (token: string) => void;
  'error-callback': (errorCode: string) => boolean;
  'expired-callback': () => void;
  'timeout-callback': () => void;
}

interface TurnstileApi {
  render: (container: HTMLElement | string, options: TurnstileRenderOptions) => TurnstileWidgetId;
  reset: (widgetId: TurnstileWidgetId) => void;
  remove: (widgetId: TurnstileWidgetId) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

interface TurnstileWidgetProps {
  action: 'login' | 'register';
  onTokenChange: (token: string) => void;
  resetSignal?: number;
  className?: string;
}

let turnstileScriptPromise: Promise<void> | null = null;

const loadTurnstileScript = (): Promise<void> => {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Turnstile requires a browser runtime'));
  }

  if (window.turnstile) {
    return Promise.resolve();
  }

  if (turnstileScriptPromise) {
    return turnstileScriptPromise;
  }

  turnstileScriptPromise = new Promise((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[data-turnstile-script="true"]'
    );

    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(), { once: true });
      existingScript.addEventListener(
        'error',
        () => {
          turnstileScriptPromise = null;
          reject(new Error('Failed to load Turnstile'));
        },
        { once: true }
      );
      return;
    }

    const script = document.createElement('script');
    script.src = TURNSTILE_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.dataset.turnstileScript = 'true';
    script.addEventListener('load', () => resolve(), { once: true });
    script.addEventListener(
      'error',
      () => {
        turnstileScriptPromise = null;
        reject(new Error('Failed to load Turnstile'));
      },
      { once: true }
    );

    document.head.appendChild(script);
  });

  return turnstileScriptPromise;
};

const getStatusMessage = (status: TurnstileStatus, errorCode: string | null) => {
  switch (status) {
    case 'verified':
      return 'Verification complete.';
    case 'expired':
      return 'Verification expired. Please run the check again.';
    case 'error':
      return errorCode
        ? `Verification could not complete. Code: ${errorCode}`
        : 'Verification could not complete.';
    case 'ready':
      return 'Complete the browser check to continue.';
    default:
      return 'Loading browser verification.';
  }
};

const getStatusClassName = (status: TurnstileStatus) => {
  if (status === 'verified') return 'text-emerald-300';
  if (status === 'error' || status === 'expired') return 'text-red-300';
  return 'text-slate-500';
};

export const TurnstileWidget: React.FC<TurnstileWidgetProps> = ({
  action,
  onTokenChange,
  resetSignal,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<TurnstileWidgetId | null>(null);
  const lastResetSignalRef = useRef(resetSignal);
  const [status, setStatus] = useState<TurnstileStatus>('loading');
  const [errorCode, setErrorCode] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    setStatus('loading');
    setErrorCode(null);

    loadTurnstileScript()
      .then(() => {
        if (cancelled || !containerRef.current || widgetIdRef.current || !window.turnstile) {
          return;
        }

        widgetIdRef.current = window.turnstile.render(containerRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
          action,
          theme: 'dark',
          size: 'flexible',
          callback: (token: string) => {
            onTokenChange(token);
            setErrorCode(null);
            setStatus('verified');
          },
          'error-callback': (code: string) => {
            onTokenChange('');
            setErrorCode(code);
            setStatus('error');
            return true;
          },
          'expired-callback': () => {
            onTokenChange('');
            setStatus('expired');
          },
          'timeout-callback': () => {
            onTokenChange('');
            setStatus('expired');
          },
        });

        setStatus('ready');
      })
      .catch((error: unknown) => {
        console.error('❌ Turnstile failed to load:', error);
        if (!cancelled) {
          onTokenChange('');
          setStatus('error');
        }
      });

    return () => {
      cancelled = true;
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
    };
  }, [action, onTokenChange]);

  useEffect(() => {
    if (lastResetSignalRef.current === resetSignal) {
      return;
    }

    lastResetSignalRef.current = resetSignal;

    if (widgetIdRef.current && window.turnstile) {
      window.turnstile.reset(widgetIdRef.current);
      onTokenChange('');
      setErrorCode(null);
      setStatus('ready');
    }
  }, [onTokenChange, resetSignal]);

  return (
    <div className={className}>
      <div className="rounded-lg border border-slate-700/70 bg-slate-950/70 p-3">
        <div ref={containerRef} className="min-h-16" />
      </div>
      <p className={`mt-2 text-xs ${getStatusClassName(status)}`} aria-live="polite">
        {getStatusMessage(status, errorCode)}
      </p>
    </div>
  );
};
