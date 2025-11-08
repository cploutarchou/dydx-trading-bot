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
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Show React Query DevTools in development */}
      {import.meta.env.DEV && (
        <ReactQueryDevtools 
          initialIsOpen={false} 
          position="bottom"
        />
      )}
    </QueryClientProvider>
  );
}