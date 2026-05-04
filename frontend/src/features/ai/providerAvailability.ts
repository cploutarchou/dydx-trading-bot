import { useQuery } from '@tanstack/react-query';
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

  const providerStatuses = statusQuery.data?.providers || [];
  const statusMap: Partial<Record<AIMarketProvider, AIProviderStatus>> = providerStatuses.reduce(
    (acc, status) => {
      acc[status.provider] = status;
      return acc;
    },
    {} as Partial<Record<AIMarketProvider, AIProviderStatus>>
  );

  const availableProviders = AI_PROVIDER_ORDER.filter((provider) => statusMap[provider]?.available);
  const unavailableProviders = AI_PROVIDER_ORDER.filter(
    (provider) => !statusMap[provider]?.available && !!statusMap[provider]
  );

  return {
    ...statusQuery,
    providerStatuses,
    statusMap,
    availableProviders,
    unavailableProviders,
  };
}
