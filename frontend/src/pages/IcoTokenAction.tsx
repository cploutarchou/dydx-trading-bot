import { CheckCircle2, Loader, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import apiClient from '../api';
import {
  PrimaryButton,
  PublicLaunchShell,
  PublicStatusPill,
  SecondaryButton,
} from '../components/PublicPagePrimitives';

type ActionKind = 'confirm' | 'unsubscribe' | 'withdraw';
type ActionState = 'loading' | 'success' | 'error';

const actionCopy: Record<ActionKind, { title: string; loading: string; successTone: string }> = {
  confirm: {
    title: 'Whitelist email confirmation',
    loading: 'Confirming whitelist email...',
    successTone: 'Confirmed',
  },
  unsubscribe: {
    title: 'ICO update unsubscribe',
    loading: 'Processing unsubscribe...',
    successTone: 'Updated',
  },
  withdraw: {
    title: 'Whitelist request withdrawal',
    loading: 'Processing withdrawal...',
    successTone: 'Updated',
  },
};

export const IcoTokenActionPage = ({ action }: { action: ActionKind }) => {
  const location = useLocation();
  const [state, setState] = useState<ActionState>('loading');
  const [message, setMessage] = useState(actionCopy[action].loading);

  const token = useMemo(() => new URLSearchParams(location.search).get('token') ?? '', [location.search]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!token.trim()) {
        setState('error');
        setMessage('This link is invalid or expired.');
        return;
      }

      try {
        const response =
          action === 'confirm'
            ? await apiClient.confirmICOWhitelist(token)
            : action === 'unsubscribe'
              ? await apiClient.unsubscribeICOWhitelist(token)
              : await apiClient.withdrawICOWhitelist(token);
        if (cancelled) return;
        const responseMessage = response.data?.message || 'The request has been processed.';
        setMessage(responseMessage);
        setState(response.success ? 'success' : 'error');
      } catch {
        if (cancelled) return;
        setState('error');
        setMessage('The link could not be processed. Request a new link or contact support.');
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [action, token]);

  const isSuccess = state === 'success';

  return (
    <PublicLaunchShell logoSubtitle="ICO whitelist">
      <section className="grid min-h-[70vh] place-items-center py-12">
        <div className="public-simple-panel max-w-[560px] text-center">
          <PublicStatusPill tone={isSuccess ? 'success' : state === 'loading' ? 'info' : 'warning'} icon={isSuccess ? CheckCircle2 : state === 'loading' ? Loader : XCircle}>
            {state === 'loading' ? 'Processing' : isSuccess ? actionCopy[action].successTone : 'Needs attention'}
          </PublicStatusPill>
          <h1 className="mt-5 text-[clamp(2rem,4vw,3rem)] font-semibold leading-tight text-white">
            {actionCopy[action].title}
          </h1>
          <p className="mt-4 text-base leading-7 text-slate-300">{message}</p>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <PrimaryButton to="/ico">ICO briefing</PrimaryButton>
            <SecondaryButton to="/">Launch page</SecondaryButton>
          </div>
        </div>
      </section>
    </PublicLaunchShell>
  );
};

export default IcoTokenActionPage;
