import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { Loader2, Mail, Send, Trash2 } from 'lucide-react';
import { useState } from 'react';
import api from '../api';
import { useToastStore } from './ErrorBoundary';

const getMutationErrorMessage = (error: unknown): string => {
  if (error instanceof AxiosError) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (typeof data?.error === 'string' && data.error.length > 0) return data.error;
    if (typeof data?.message === 'string' && data.message.length > 0) return data.message;
    return error.message;
  }
  return error instanceof Error ? error.message : 'Unknown error';
};

export function MailgunSettings() {
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const [apiKey, setApiKey] = useState('');
  const [label, setLabel] = useState('Primary Mailgun key');
  const [domain, setDomain] = useState('');
  const [fromEmail, setFromEmail] = useState('');
  const [fromName, setFromName] = useState('dYdX Bot');
  const [region, setRegion] = useState<'us' | 'eu'>('us');

  const statusQuery = useQuery({
    queryKey: ['mailgun', 'status'],
    queryFn: async () => {
      const response = await api.getMailgunStatus();
      return response.data;
    },
    staleTime: 30_000,
  });

  // Server status -> editable drafts, adjusted during render when the query
  // data identity changes (sanctioned pattern).
  const [prevStatusData, setPrevStatusData] = useState(statusQuery.data);
  if (statusQuery.data !== prevStatusData) {
    setPrevStatusData(statusQuery.data);
    const status = statusQuery.data;
    if (status) {
      setLabel(status.shared_key_label || 'Primary Mailgun key');
      setDomain(status.domain || '');
      setFromEmail(status.from_email || '');
      setFromName(status.from_name || 'dYdX Bot');
      setRegion(status.region === 'eu' ? 'eu' : 'us');
    }
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const response = await api.saveMailgunConfig({
        api_key: apiKey,
        label,
        domain,
        from_email: fromEmail,
        from_name: fromName,
        region,
      });
      return response.data;
    },
    onSuccess: () => {
      setApiKey('');
      successToast(
        'Mailgun saved',
        'Transactional email delivery is now configured for onboarding notices.'
      );
      void queryClient.invalidateQueries({ queryKey: ['mailgun'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to save Mailgun config', getMutationErrorMessage(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const response = await api.deleteMailgunConfig();
      return response.data;
    },
    onSuccess: () => {
      successToast(
        'Mailgun key removed',
        'Email delivery has been disabled until a new Mailgun key is configured.'
      );
      void queryClient.invalidateQueries({ queryKey: ['mailgun'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to remove Mailgun config', getMutationErrorMessage(error));
    },
  });

  const status = statusQuery.data;

  return (
    <div className="premium-panel">
      <div className="flex items-start gap-3">
        <div className="premium-icon-wrap text-cyan-300">
          <Mail className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-white">Mailgun Delivery</h2>
          <p className="mt-1 text-sm text-slate-400">
            Configure the shared Mailgun account used for onboarding and password-rotation notices.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Send className="h-4 w-4 text-cyan-300" />
            Delivery
          </div>
          <p className="text-lg font-semibold text-white">
            {status?.configured ? 'Configured' : 'Not configured'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Onboarding emails are sent only when domain, sender, and key all exist.
          </p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Mail className="h-4 w-4 text-emerald-300" />
            Sender
          </div>
          <p className="text-lg font-semibold text-white">{status?.from_email || 'Not set'}</p>
          <p className="mt-1 text-xs text-slate-500">
            {status?.from_name || 'Friendly sender name'}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Mail className="h-4 w-4 text-amber-300" />
            Region
          </div>
          <p className="text-lg font-semibold text-white">
            {(status?.region || 'us').toUpperCase()}
          </p>
          <p className="mt-1 text-xs break-all text-slate-500">{status?.base_url}</p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Mail className="h-4 w-4 text-fuchsia-300" />
            Pending rotations
          </div>
          <p className="text-lg font-semibold text-white">
            {status?.pending_password_change_count ?? 0}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Users still required to change their temporary password.
          </p>
        </div>
      </div>

      {!status?.configured && (status?.pending_password_change_count ?? 0) > 0 && (
        <div className="mt-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-4 text-sm text-amber-100">
          Mailgun is not configured while users are still on temporary passwords. Account creation
          still works, but onboarding emails are being skipped.
        </div>
      )}

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5">
          <h3 className="text-lg font-semibold text-white">
            {status?.shared_key_present ? 'Update Mailgun config' : 'Save Mailgun config'}
          </h3>
          {status?.shared_key_present && (
            <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Current shared key
              </p>
              <p className="mt-2 font-mono text-sm text-slate-200">
                {status.shared_key_masked || 'Masked key on file'}
              </p>
            </div>
          )}

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Label"
              className="premium-input md:col-span-2"
            />
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="Mailgun domain"
              className="premium-input"
            />
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value === 'eu' ? 'eu' : 'us')}
              className="premium-input"
            >
              <option value="us">US region</option>
              <option value="eu">EU region</option>
            </select>
            <input
              value={fromEmail}
              onChange={(e) => setFromEmail(e.target.value)}
              placeholder="Sender email"
              className="premium-input"
            />
            <input
              value={fromName}
              onChange={(e) => setFromName(e.target.value)}
              placeholder="Sender name"
              className="premium-input"
            />
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={
                status?.shared_key_present
                  ? 'Paste a new Mailgun API key to rotate credentials'
                  : 'Paste Mailgun API key'
              }
              className="premium-input md:col-span-2"
            />
          </div>

          <button
            type="button"
            disabled={
              saveMutation.isPending || !apiKey.trim() || !domain.trim() || !fromEmail.trim()
            }
            onClick={() => saveMutation.mutate()}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
          >
            {saveMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {status?.shared_key_present ? 'Update Mailgun' : 'Save Mailgun'}
          </button>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5">
          <h3 className="text-lg font-semibold text-white">Operational notes</h3>
          <ul className="mt-4 space-y-3 text-sm text-slate-300">
            <li>
              Mailgun is used only from the backend. The browser never talks to Mailgun directly.
            </li>
            <li>
              New admin-created users still receive a forced password-change flow even if email
              delivery is unavailable.
            </li>
            <li>
              Use a secure out-of-band channel for the temporary password itself. Email notices only
              tell the user to rotate it on first sign-in.
            </li>
          </ul>

          <button
            type="button"
            disabled={deleteMutation.isPending || !status?.shared_key_present}
            onClick={() => deleteMutation.mutate()}
            className="mt-6 inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
          >
            {deleteMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            Remove Mailgun key
          </button>
        </div>
      </div>
    </div>
  );
}
