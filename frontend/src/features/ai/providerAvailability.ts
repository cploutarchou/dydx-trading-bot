import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import api, { type AIMarketProvider, type AIProviderStatus } from '../../api';

export const AI_PROVIDER_LABELS: Record<AIMarketProvider, string> = {
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  claude: 'Claude',
};

export const AI_PROVIDER_ORDER: AIMarketProvider[] = ['deepseek', 'openai', 'claude'];

export const getAIProviderLabel = (provider: AIMarketProvider): string =>
  AI_PROVIDER_LABELS[provider];

export const getAIProviderDisplayName = (status?: AIProviderStatus): string => {
  if (!status) {
    return 'AI provider';
  }

  const label = getAIProviderLabel(status.provider);
  return status.model ? `${label} (${status.model})` : label;
};

export const getAvailabilityBadge = (
  status?: AIProviderStatus
): { label: string; tone: 'success' | 'warning' | 'muted'; detail?: string } => {
  if (!status) {
    return { label: 'Unknown', tone: 'muted', detail: 'Provider status not loaded yet' };
  }

  if (status.available) {
    return {
      label: 'Available',
      tone: 'success',
      detail: `Key source: ${status.active_key_source}`,
    };
  }

  if (status.availability_status === 'disabled') {
    return {
      label: 'Disabled',
      tone: 'muted',
      detail: status.unavailable_reason || 'Disabled by administrator',
    };
  }

  return {
    label: 'Not configured',
    tone: 'warning',
    detail: status.unavailable_reason || 'No active credentials configured',
  };
};

export function useAIProviderAvailability() {
  const statusQuery = useQuery({
    queryKey: ['ai-market-filters', 'status'],
    queryFn: async () => {
      const response = await api.getAIMarketStatus();
      return response.data;
    },
    staleTime: 30_000,
  });

  // Memoized against the query data so the derived identities are stable
  // across renders — consumers run render-time state adjustment keyed on
  // these identities, and a fresh array each render would loop React.
  const providerStatuses = useMemo(
    () => statusQuery.data?.providers ?? [],
    [statusQuery.data]
  );
  const statusMap = useMemo<Partial<Record<AIMarketProvider, AIProviderStatus>>>(
    () =>
      providerStatuses.reduce<Partial<Record<AIMarketProvider, AIProviderStatus>>>(
        (acc, status) => {
          acc[status.provider] = status;
          return acc;
        },
        {}
      ),
    [providerStatuses]
  );

  const availableProviders = useMemo(
    () => AI_PROVIDER_ORDER.filter((provider) => statusMap[provider]?.available),
    [statusMap]
  );
  const unavailableProviders = useMemo(
    () =>
      AI_PROVIDER_ORDER.filter((provider) => !statusMap[provider]?.available && !!statusMap[provider]),
    [statusMap]
  );

  return {
    ...statusQuery,
    providerStatuses,
    statusMap,
    availableProviders,
    unavailableProviders,
  };
}
