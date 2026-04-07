import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, Loader2, XCircle } from 'lucide-react';

const AuthCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Finalizing your Spotify connection...');

  useEffect(() => {
    const spotifyStatus = searchParams.get('status');
    const error = searchParams.get('error');
    const errorDetail = searchParams.get('error_detail');
    const ingestionStatus = searchParams.get('ingestion');
    const ingestionError = searchParams.get('ingestion_error');

    if (error) {
      setStatus('error');
      setMessage(
        errorDetail
          ? `Spotify authorization failed: ${errorDetail}`
          : `Spotify authorization failed: ${error}`
      );
      return;
    }

    if (spotifyStatus !== 'linked') {
      setStatus('error');
      setMessage('Spotify did not return a successful authorization state.');
      return;
    }

    let redirectTimer: number | undefined;
    setStatus('success');
    if (ingestionStatus === 'failed' && ingestionError) {
      setMessage(`Spotify connected, but the first library sync hit an issue: ${ingestionError}`);
    } else if (ingestionStatus === 'completed') {
      setMessage('Spotify connected and your listening history was synced. Redirecting back to your account...');
    } else {
      setMessage('Spotify connected. Redirecting back to your account...');
    }
    redirectTimer = window.setTimeout(() => {
      window.location.replace('/');
    }, 1800);

    return () => {
      if (redirectTimer) {
        window.clearTimeout(redirectTimer);
      }
    };
  }, [searchParams]);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 p-6 text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.18),transparent_30%),radial-gradient(circle_at_bottom,_rgba(236,72,153,0.12),transparent_25%)]" />
      <div className="relative z-10 w-full max-w-md rounded-[2rem] border border-slate-800 bg-slate-900/70 p-8 text-center shadow-2xl backdrop-blur-2xl">
        {status === 'loading' && (
          <>
            <Loader2 className="mx-auto h-16 w-16 animate-spin text-indigo-400" />
            <h1 className="mt-6 text-3xl font-bold text-white">Syncing Spotify</h1>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle2 className="mx-auto h-16 w-16 text-emerald-400" />
            <h1 className="mt-6 text-3xl font-bold text-emerald-300">Connected</h1>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle className="mx-auto h-16 w-16 text-rose-400" />
            <h1 className="mt-6 text-3xl font-bold text-rose-300">Connection failed</h1>
          </>
        )}

        <p className="mt-4 text-sm leading-7 text-slate-300">{message}</p>

        {status === 'error' && (
          <button
            onClick={() => navigate('/')}
            className="mt-6 rounded-2xl border border-slate-700 bg-slate-950/80 px-5 py-3 text-sm font-semibold text-white transition hover:border-slate-500 hover:bg-slate-900"
            type="button"
          >
            Return home
          </button>
        )}
      </div>
    </div>
  );
};

export default AuthCallbackPage;
