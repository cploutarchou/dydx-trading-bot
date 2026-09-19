import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { Loader2, Mail, Send, Trash2 } from 'lucide-react';
import { useState } from 'react';
import api from '../api';
import { useToastStore } from './ErrorBoundary';

const DEFAULT_KEY_LABEL = 'Primary email key';
const DEFAULT_SENDER_NAME = 'ExecutionLab';

const getMutationErrorMessage = (error: unknown): string => {
  if (error instanceof AxiosError) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (typeof data?.error === 'string' && data.error.length > 0) return data.error;
    if (typeof data?.message === 'string' && data.message.length > 0) return data.message;
    return error.message;
  }
  return error instanceof Error ? error.message : 'Unknown error';
};

export function EmailSettings() {
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const [apiKey, setApiKey] = useState('');
  const [label, setLabel] = useState(DEFAULT_KEY_LABEL);
  const [apiUrl, setApiUrl] = useState('');
  const [fromEmail, setFromEmail] = useState('');
  const [fromName, setFromName] = useState(DEFAULT_SENDER_NAME);
  const [replyTo, setReplyTo] = useState('');
  const [testRecipient, setTestRecipient] = useState('');

  const statusQuery = useQuery({
    queryKey: ['email', 'status'],
    queryFn: async () => {
      const response = await api.getEmailStatus();
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
      setLabel(status.shared_key_label || DEFAULT_KEY_LABEL);
      setApiUrl(status.api_url || '');
      setFromEmail(status.from_email || '');
      setFromName(status.from_name || DEFAULT_SENDER_NAME);
      setReplyTo(status.reply_to || '');
    }
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const response = await api.saveEmailConfig({
        api_key: apiKey,
        label,
        api_url: apiUrl,
        from_email: fromEmail,
        from_name: fromName,
        reply_to: replyTo,
      });
      return response.data;
    },
    onSuccess: () => {
      setApiKey('');
      successToast('Email delivery saved', 'Send a test message to confirm it works end to end.');
      void queryClient.invalidateQueries({ queryKey: ['email'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to save email config', getMutationErrorMessage(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const response = await api.deleteEmailConfig();
      return response.data;
    },
    onSuccess: () => {
      successToast(
        'Email API key removed',
        'Email delivery is disabled until a new secret key is saved.'
      );
      void queryClient.invalidateQueries({ queryKey: ['email'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to remove email key', getMutationErrorMessage(error));
    },
  });

  const testMutation = useMutation({
    mutationFn: async () => {
      const response = await api.sendEmailTest(testRecipient.trim());
      return response.data;
    },
    onSuccess: () => {
      successToast(
        'Test email sent',
        testRecipient.trim()
          ? `Check the inbox of ${testRecipient.trim()}.`
          : 'Check the inbox of your own account email.'
      );
    },
    onError: (error: unknown) => {
      errorToast('Test email failed', getMutationErrorMessage(error));
    },
  });

  const status = statusQuery.data;
  const keyOnFile = Boolean(status?.shared_key_present);
  const canSave =
    !saveMutation.isPending &&
    apiUrl.trim().length > 0 &&
    fromEmail.trim().length > 0 &&
    (keyOnFile || apiKey.trim().length > 0);

  return (
    <div className="premium-panel">
      <div className="flex items-start gap-3">
        <div className="premium-icon-wrap text-cyan-300">
          <Mail className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-white">Email Delivery</h2>
          <p className="mt-1 text-sm text-slate-400">
            Configure the Plunk project used for onboarding notices, password resets, and whitelist
            emails.
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
            Emails are sent only when the API URL, sender, and secret key all exist.
          </p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Mail className="h-4 w-4 text-emerald-300" />
            Sender
          </div>
          <p className="text-lg font-semibold break-all text-white">
            {status?.from_email || 'Not set'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {status?.from_name || 'Friendly sender name'}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Mail className="h-4 w-4 text-amber-300" />
            API
          </div>
          <p className="text-lg font-semibold text-white">Plunk</p>
          <p className="mt-1 text-xs break-all text-slate-500">{status?.api_url || 'Not set'}</p>
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
          Email delivery is not configured while users are still on temporary passwords. Account
          creation still works, but onboarding emails are being skipped.
        </div>
      )}

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5">
          <h3 className="text-lg font-semibold text-white">
            {keyOnFile ? 'Update email config' : 'Save email config'}
          </h3>
          {keyOnFile && (
            <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Current secret key
              </p>
              <p className="mt-2 font-mono text-sm text-slate-200">
                {status?.shared_key_masked || 'Masked key on file'}
              </p>
            </div>
          )}

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="block text-xs text-slate-400 md:col-span-2">
              Label
              <input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Label"
                className="premium-input mt-1"
              />
            </label>
            <label className="block text-xs text-slate-400 md:col-span-2">
              API base URL
              <input
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="https://api.cpdevlab.com"
                inputMode="url"
                autoComplete="off"
                className="premium-input mt-1"
              />
            </label>
            <label className="block text-xs text-slate-400">
              Sender email
              <input
                value={fromEmail}
                onChange={(e) => setFromEmail(e.target.value)}
                placeholder="no-reply@executionlab.io"
                inputMode="email"
                autoComplete="off"
                className="premium-input mt-1"
              />
            </label>
            <label className="block text-xs text-slate-400">
              Sender name
              <input
                value={fromName}
                onChange={(e) => setFromName(e.target.value)}
                placeholder="Sender name"
                className="premium-input mt-1"
              />
            </label>
            <label className="block text-xs text-slate-400 md:col-span-2">
              Reply-to email (optional)
              <input
                value={replyTo}
                onChange={(e) => setReplyTo(e.target.value)}
                placeholder="support@executionlab.io"
                inputMode="email"
                autoComplete="off"
                className="premium-input mt-1"
              />
            </label>
            <label className="block text-xs text-slate-400 md:col-span-2">
              Secret key
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  keyOnFile
                    ? 'Leave blank to keep the current key, or paste a new sk_ key to rotate'
                    : 'Paste the project secret key (sk_...)'
                }
                autoComplete="off"
                className="premium-input mt-1"
              />
            </label>
          </div>

          <button
            type="button"
            disabled={!canSave}
            onClick={() => saveMutation.mutate()}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
          >
            {saveMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {keyOnFile ? 'Update email config' : 'Save email config'}
          </button>
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5">
            <h3 className="text-lg font-semibold text-white">Send a test email</h3>
            <p className="mt-2 text-sm text-slate-400">
              Uses the saved configuration. Leave the recipient blank to send to your own account
              email.
            </p>
            <label className="mt-4 block text-xs text-slate-400">
              Recipient (optional)
              <input
                value={testRecipient}
                onChange={(e) => setTestRecipient(e.target.value)}
                placeholder="you@example.com"
                inputMode="email"
                autoComplete="off"
                className="premium-input mt-1"
              />
            </label>
            <button
              type="button"
              disabled={testMutation.isPending || !status?.configured}
              onClick={() => testMutation.mutate()}
              className="mt-4 inline-flex items-center gap-2 rounded-xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-2.5 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
            >
              {testMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              Send test email
            </button>
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5">
            <h3 className="text-lg font-semibold text-white">Operational notes</h3>
            <ul className="mt-4 space-y-3 text-sm text-slate-300">
              <li>
                Use the project <span className="font-mono">sk_</span> secret key. The{' '}
                <span className="font-mono">pk_</span> public key cannot send email.
              </li>
              <li>The sender address must belong to a domain verified in the Plunk project.</li>
              <li>
                Email is sent only from the backend. The browser never talks to Plunk directly.
              </li>
              <li>
                New admin-created users still receive a forced password-change flow even if email
                delivery is unavailable.
              </li>
              <li>
                Use a secure out-of-band channel for the temporary password itself. Email notices
                only tell the user to rotate it on first sign-in.
              </li>
            </ul>

            <button
              type="button"
              disabled={deleteMutation.isPending || !keyOnFile}
              onClick={() => deleteMutation.mutate()}
              className="mt-6 inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Remove email key
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
