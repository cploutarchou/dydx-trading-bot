import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Eye, EyeOff, Loader2, RefreshCw, ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import apiClient from '../api';
import { queryKeys } from '../api/queryClient';
import { useToastStore } from './ErrorBoundary';
import { ActionDialog, InlineNotice, PlatformPanel, StatusBadge } from './ui/PlatformUI';

const getErrorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : 'Unable to update Coming Soon mode';

export const AdminComingSoonSettings = () => {
  const queryClient = useQueryClient();
  const settingQuery = useQuery({
    queryKey: queryKeys.comingSoonSetting,
    queryFn: async () => {
      const response = await apiClient.getComingSoonSetting();
      if (!response.success || !response.data) {
        throw new Error(response.message || 'Coming Soon setting was not returned');
      }
      return response.data;
    },
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [pendingValue, setPendingValue] = useState<boolean | null>(null);
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const setting = settingQuery.data ?? null;
  const loading = settingQuery.isLoading || settingQuery.isFetching;
  const loadError =
    settingQuery.error instanceof Error ? settingQuery.error.message : null;
  const error = saveError ?? loadError;

  useEffect(() => {
    if (loadError) {
      errorToast('Coming Soon setting unavailable', loadError);
    }
  }, [loadError, errorToast]);

  const enabled = Boolean(setting?.coming_soon_enabled);
  const nextValue = pendingValue ?? !enabled;
  const dialogCopy = useMemo(
    () =>
      nextValue
        ? {
            title: 'Enable Coming Soon mode?',
            description:
              'Anonymous visitors and authenticated client users will see the Coming Soon page. Admin and backoffice access remains available.',
            confirmLabel: 'Enable Coming Soon',
            tone: 'warning' as const,
          }
        : {
            title: 'Disable Coming Soon mode?',
            description:
              'Public and client-portal access will return to normal immediately after this setting is saved.',
            confirmLabel: 'Disable Coming Soon',
            tone: 'accent' as const,
          },
    [nextValue]
  );

  const confirmChange = async () => {
    if (pendingValue === null || saving) return;

    try {
      setSaving(true);
      setSaveError(null);
      const response = await apiClient.updateComingSoonSetting(pendingValue);
      if (!response.success || !response.data) {
        throw new Error(response.message || 'Coming Soon setting was not updated');
      }
      queryClient.setQueryData(queryKeys.comingSoonSetting, response.data);
      successToast(
        pendingValue ? 'Coming Soon enabled' : 'Coming Soon disabled',
        pendingValue
          ? 'Public client access now shows the Coming Soon page.'
          : 'Public client access has been restored.'
      );
      setPendingValue(null);
    } catch (saveErrorCaught) {
      const message = getErrorMessage(saveErrorCaught);
      setSaveError(message);
      errorToast('Failed to update Coming Soon mode', message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PlatformPanel
        title="Coming Soon Mode"
        description="Control public launch access without blocking admin and backoffice operations."
        action={
          <button
            type="button"
            onClick={() => void settingQuery.refetch()}
            disabled={loading || saving}
            className="platform-button platform-button-secondary disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </button>
        }
      >
        <div className="grid gap-4 lg:grid-cols-[1fr,18rem]">
          <div className="rounded-lg border border-slate-700/60 bg-slate-950/45 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-lg border border-cyan-500/25 bg-cyan-500/10 p-2 text-cyan-200">
                <ShieldCheck className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-semibold text-white">Current public access state</p>
                <p className="mt-1 text-sm leading-6 text-slate-400">
                  {enabled
                    ? 'Coming Soon is active for public and client-portal visitors.'
                    : 'Public and client-portal visitors can access the normal application.'}
                </p>
              </div>
              <StatusBadge tone={enabled ? 'warning' : 'success'} className="ml-auto">
                {enabled ? 'Coming Soon enabled' : 'Normal access'}
              </StatusBadge>
            </div>

            {setting?.updated_at && (
              <p className="mt-4 text-xs text-slate-500">
                Last updated: {new Date(setting.updated_at).toLocaleString()}
              </p>
            )}
          </div>

          <div className="rounded-lg border border-slate-700/60 bg-slate-950/45 p-4">
            <p className="text-sm font-semibold text-white">Production control</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              This setting is persisted in backend platform settings and survives refreshes and
              restarts.
            </p>
            <button
              type="button"
              onClick={() => setPendingValue(!enabled)}
              disabled={loading || saving || setting === null}
              className={`mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                enabled
                  ? 'border-cyan-500/30 bg-cyan-500/15 text-cyan-100 hover:bg-cyan-500/20'
                  : 'border-amber-500/30 bg-amber-500/15 text-amber-100 hover:bg-amber-500/20'
              }`}
            >
              {enabled ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              {enabled ? 'Disable Coming Soon' : 'Enable Coming Soon'}
            </button>
          </div>
        </div>

        {error && (
          <InlineNotice
            className="mt-4"
            tone="danger"
            title="Coming Soon control error"
            description={error}
          />
        )}

        <InlineNotice
          className="mt-4"
          tone="muted"
          title="Protected operational paths stay available"
          description="Authentication, public app config, health checks, and admin settings remain exempt so operators can sign in and recover the platform."
        />
      </PlatformPanel>

      <ActionDialog
        open={pendingValue !== null}
        title={dialogCopy.title}
        description={dialogCopy.description}
        confirmLabel={dialogCopy.confirmLabel}
        confirmTone={dialogCopy.tone}
        loading={saving}
        onConfirm={confirmChange}
        onClose={() => {
          if (!saving) setPendingValue(null);
        }}
        details={
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
            <p>
              This is a production-impacting platform setting. The change is written to the backend
              settings store immediately.
            </p>
          </div>
        }
      />
    </>
  );
};

export default AdminComingSoonSettings;
