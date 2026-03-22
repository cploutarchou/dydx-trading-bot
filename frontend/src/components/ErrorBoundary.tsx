// Global Error Boundary and Toast System
// Provides comprehensive error handling and user notifications

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
        <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4">
          <div className="max-w-md w-full bg-slate-800 rounded-lg shadow-xl p-6">
            <div className="flex items-center mb-4">
              <div className="flex-shrink-0">
                <svg
                  className="h-8 w-8 text-red-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"
                  />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-white">Something went wrong</h3>
              </div>
            </div>

            <div className="text-sm text-slate-300 mb-4">
              An unexpected error occurred in the application. This has been logged and will be
              investigated.
            </div>

            <details className="mb-4">
              <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-300">
                Technical Details
              </summary>
              <div className="mt-2 text-xs text-slate-500 bg-slate-900 rounded p-2 overflow-auto">
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

            <div className="flex space-x-3">
              <button
                onClick={() => window.location.reload()}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
              >
                Reload Page
              </button>
              <button
                onClick={() => {
                  this.setState({ hasError: false, error: null, errorInfo: null });
                }}
                className="flex-1 bg-slate-600 hover:bg-slate-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
              >
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
    <div className="fixed top-4 right-4 z-50 space-y-2 max-w-sm w-full">
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
  const bgColor = {
    success: 'bg-green-600',
    error: 'bg-red-600',
    warning: 'bg-yellow-600',
    info: 'bg-blue-600',
  }[toast.type];

  const icon = {
    success: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
          clipRule="evenodd"
        />
      </svg>
    ),
    error: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
          clipRule="evenodd"
        />
      </svg>
    ),
    warning: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
          clipRule="evenodd"
        />
      </svg>
    ),
    info: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
          clipRule="evenodd"
        />
      </svg>
    ),
  }[toast.type];

  return (
    <div
      className={`${bgColor} text-white p-4 rounded-lg shadow-lg animate-in slide-in-from-right duration-200`}
    >
      <div className="flex items-start">
        <div className="flex-shrink-0">{icon}</div>

        <div className="ml-3 flex-1">
          <div className="font-medium text-sm">{toast.title}</div>
          {toast.message && <div className="text-sm opacity-90 mt-1">{toast.message}</div>}

          {toast.action && (
            <button
              onClick={toast.action.onClick}
              className="mt-2 text-sm underline hover:no-underline"
            >
              {toast.action.label}
            </button>
          )}
        </div>

        <button
          onClick={() => onRemove(toast.id)}
          className="ml-2 flex-shrink-0 text-white/70 hover:text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
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
