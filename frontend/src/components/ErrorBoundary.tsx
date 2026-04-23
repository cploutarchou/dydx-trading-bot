// Global Error Boundary and Toast System
// Provides comprehensive error handling and user notifications

import { AlertTriangle, CheckCircle2, Info, RefreshCw, X, XCircle } from 'lucide-react';
import { Component, ErrorInfo, ReactNode } from 'react';
import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

// Toast types and interfaces
export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
  persistent?: boolean;
  timestamp: number;
}

// Toast store interface
interface ToastState {
  toasts: Toast[];
}

interface ToastActions {
  addToast: (toast: Omit<Toast, 'id' | 'timestamp'>) => void;
  removeToast: (id: string) => void;
  clearAllToasts: () => void;

  // Convenience methods
  success: (title: string, message?: string, options?: Partial<Toast>) => void;
  error: (title: string, message?: string, options?: Partial<Toast>) => void;
  warning: (title: string, message?: string, options?: Partial<Toast>) => void;
  info: (title: string, message?: string, options?: Partial<Toast>) => void;
}

type ToastStore = ToastState & ToastActions;

// Create toast store
export const useToastStore = create<ToastStore>()(
  subscribeWithSelector((set, get) => ({
    toasts: [],

    addToast: (toast) => {
      const id = `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      const newToast: Toast = {
        id,
        timestamp: Date.now(),
        duration: 5000, // Default 5 seconds
        ...toast,
      };

      set((state) => ({
        toasts: [...state.toasts, newToast],
      }));

      // Auto-remove after duration (unless persistent)
      if (!newToast.persistent && newToast.duration && newToast.duration > 0) {
        setTimeout(() => {
          get().removeToast(id);
        }, newToast.duration);
      }
    },

    removeToast: (id) => {
      set((state) => ({
        toasts: state.toasts.filter((toast) => toast.id !== id),
      }));
    },

    clearAllToasts: () => {
      set({ toasts: [] });
    },

    success: (title, message, options) => {
      get().addToast({ type: 'success', title, message, ...options });
    },

    error: (title, message, options) => {
      get().addToast({
        type: 'error',
        title,
        message,
        duration: 8000, // Errors stay longer
        ...options,
      });
    },

    warning: (title, message, options) => {
      get().addToast({ type: 'warning', title, message, ...options });
    },

    info: (title, message, options) => {
      get().addToast({ type: 'info', title, message, ...options });
    },
  }))
);

// Error Boundary Props
interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

// React Error Boundary Component
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({
      error,
      errorInfo,
    });

    // Log error
    console.error('Error Boundary caught an error:', error, errorInfo);

    // Call custom error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Show toast notification
    const toastStore = useToastStore.getState();
    toastStore.error(
      'Application Error',
      'An unexpected error occurred. The error has been logged.',
      {
        persistent: true,
        action: {
          label: 'Reload',
          onClick: () => window.location.reload(),
        },
      }
    );

    // Send error to logging service (if configured)
    this.logError(error, errorInfo);
  }

  private logError(_error: Error, _errorInfo: ErrorInfo) {
    // Here you could send errors to services like Sentry, LogRocket, etc.
    // Example: send errorReport to a logging service (Sentry, LogRocket, etc.)
    if (import.meta.env.PROD) {
      // fetch('/api/v1/errors', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ message: error.message, stack: error.stack,
      //     componentStack: errorInfo.componentStack, timestamp: new Date().toISOString(),
      //     userAgent: navigator.userAgent, url: window.location.href }),
      // });
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
          <div className="w-full max-w-xl rounded-lg border border-rose-500/20 bg-slate-900/95 p-6 shadow-[0_40px_120px_rgba(2,6,23,0.6)]">
            <div className="flex items-start gap-3">
              <div className="rounded-lg border border-rose-500/25 bg-rose-500/10 p-2 text-rose-300">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-rose-300">
                  Workspace interruption
                </p>
                <h3 className="mt-2 text-xl font-semibold text-white">
                  The operator workspace hit an unexpected error.
                </h3>
              </div>
            </div>

            <p className="mb-4 mt-4 text-sm leading-6 text-slate-300">
              We kept the failure visible instead of letting the page silently break. Reload the
              workspace to restore session context, or try again if you were in the middle of a
              non-destructive step.
            </p>

            <details className="mb-4">
              <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-200">
                Technical Details
              </summary>
              <div className="mt-3 overflow-auto rounded-lg border border-slate-800 bg-slate-950/80 p-3 text-xs text-slate-400">
                <div>
                  <strong>Error:</strong> {this.state.error?.message}
                </div>
                {this.state.error?.stack && (
                  <div className="mt-2">
                    <strong>Stack:</strong>
                    <pre className="whitespace-pre-wrap text-xs">{this.state.error.stack}</pre>
                  </div>
                )}
              </div>
            </details>

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                onClick={() => window.location.reload()}
                className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-cyan-500/30 bg-cyan-500/15 px-4 py-3 text-sm font-medium text-cyan-50 transition hover:border-cyan-400/40 hover:bg-cyan-500/20"
              >
                <RefreshCw className="h-4 w-4" />
                Reload Workspace
              </button>
              <button
                onClick={() => {
                  this.setState({ hasError: false, error: null, errorInfo: null });
                }}
                className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-slate-700/70 bg-slate-900/70 px-4 py-3 text-sm font-medium text-slate-100 transition hover:border-slate-600 hover:bg-slate-900"
              >
                <RefreshCw className="h-4 w-4" />
                Try Again
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Toast Container Component
export function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed right-4 top-4 z-[80] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
      ))}
    </div>
  );
}

// Individual Toast Component
interface ToastItemProps {
  toast: Toast;
  onRemove: (id: string) => void;
}

function ToastItem({ toast, onRemove }: ToastItemProps) {
  const toneMap = {
    success: {
      wrapper: 'border-emerald-500/25 bg-slate-950/96',
      iconWrap: 'border-emerald-500/25 bg-emerald-500/12 text-emerald-300',
      title: 'text-emerald-200',
      icon: CheckCircle2,
    },
    error: {
      wrapper: 'border-rose-500/25 bg-slate-950/96',
      iconWrap: 'border-rose-500/25 bg-rose-500/12 text-rose-300',
      title: 'text-rose-200',
      icon: XCircle,
    },
    warning: {
      wrapper: 'border-amber-500/25 bg-slate-950/96',
      iconWrap: 'border-amber-500/25 bg-amber-500/12 text-amber-300',
      title: 'text-amber-200',
      icon: AlertTriangle,
    },
    info: {
      wrapper: 'border-cyan-500/25 bg-slate-950/96',
      iconWrap: 'border-cyan-500/25 bg-cyan-500/12 text-cyan-300',
      title: 'text-cyan-200',
      icon: Info,
    },
  }[toast.type];
  const Icon = toneMap.icon;

  return (
    <div className={`rounded-lg border p-4 shadow-[0_24px_80px_rgba(2,6,23,0.45)] ${toneMap.wrapper}`}>
      <div className="flex items-start gap-3">
        <div className={`shrink-0 rounded-lg border p-2 ${toneMap.iconWrap}`}>
          <Icon className="h-4 w-4" />
        </div>

        <div className="min-w-0 flex-1">
          <div className={`text-sm font-semibold ${toneMap.title}`}>{toast.title}</div>
          {toast.message && <div className="mt-1 text-sm leading-6 text-slate-300">{toast.message}</div>}

          {toast.action && (
            <button
              onClick={toast.action.onClick}
              className="mt-2 text-sm font-medium text-white underline underline-offset-4 hover:no-underline"
            >
              {toast.action.label}
            </button>
          )}
        </div>

        <button
          onClick={() => onRemove(toast.id)}
          className="shrink-0 text-slate-500 transition-colors hover:text-slate-200"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// Global error handler for unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);

  const toastStore = useToastStore.getState();
  toastStore.error(
    'Unexpected Error',
    'An error occurred while processing your request. Please try again.',
    { duration: 6000 }
  );

  // Prevent the default handling
  event.preventDefault();
});

// Global error handler for uncaught errors
window.addEventListener('error', (event) => {
  console.error('Uncaught error:', event.error);

  const toastStore = useToastStore.getState();
  toastStore.error(
    'Application Error',
    'An unexpected error occurred. Please refresh the page if problems persist.',
    { duration: 8000 }
  );
});

export default {
  ErrorBoundary,
  ToastContainer,
  useToastStore,
};
