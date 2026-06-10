// React Query Provider Component
// Wraps the app with QueryClient and DevTools

import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { ReactNode } from 'react';
import { queryClient } from './queryClient';

interface QueryProviderProps {
  children: ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const isAutomatedBrowser = typeof navigator !== 'undefined' && navigator.webdriver;
  const isScreenshotCaptureMode =
    typeof window !== 'undefined' &&
    new URLSearchParams(window.location.search).has('qa_screenshots');
  const shouldShowDevtools = import.meta.env.DEV && !isAutomatedBrowser && !isScreenshotCaptureMode;

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Show React Query DevTools in development */}
      {shouldShowDevtools && <ReactQueryDevtools initialIsOpen={false} position="bottom" />}
    </QueryClientProvider>
  );
}
