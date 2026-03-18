import React, { useState } from 'react';
import {
  Disc3,
  ListMusic,
  Loader2,
  LogOut,
  Music,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

import { useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../lib/api';

type AuthMode = 'login' | 'register';

const HomePage: React.FC = () => {
  const { user, isLoading, sessionError, login, logout, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>('register');
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loginForm, setLoginForm] = useState({
    identifier: '',
    password: '',
  });
  const [registerForm, setRegisterForm] = useState({
    username: '',
    first_name: '',
    last_name: '',
    email: '',
    password: '',
  });

  function getErrorMessage(error: unknown) {
    if (typeof error === 'object' && error !== null && 'response' in error) {
      const response = (error as { response?: { data?: { detail?: unknown } } }).response;
      if (typeof response?.data?.detail === 'string') {
        return response.data.detail;
      }
    }

    return 'Something went wrong. Please try again.';
  }

  function handleSpotifyLogin() {
    window.location.assign(`${API_BASE_URL}/api/spotify/login`);
  }

  async function handleLoginSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setIsSubmitting(true);

    try {
      await login(loginForm);
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRegisterSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setIsSubmitting(true);

    try {
      await register(registerForm);
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogout() {
    setFormError(null);
    setIsSubmitting(true);

    try {
      await logout();
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">
        <div className="flex items-center gap-3 rounded-full border border-slate-800 bg-slate-900/80 px-5 py-3 text-sm text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
          Restoring session
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 px-6 py-10 text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.18),transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(236,72,153,0.14),transparent_24%)]" />
      <div className="absolute -left-24 top-24 h-72 w-72 rounded-full bg-indigo-500/10 blur-3xl" />
      <div className="absolute right-0 top-0 h-80 w-80 rounded-full bg-fuchsia-500/10 blur-3xl" />

      <div className="relative mx-auto grid min-h-[calc(100vh-5rem)] max-w-6xl items-center gap-10 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="space-y-8">
          <div className="space-y-5">
            <p className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-emerald-200">
              <ShieldCheck className="h-4 w-4" />
              Real session auth
            </p>
            <div className="space-y-4">
              <h1 className="max-w-3xl text-5xl font-black tracking-tight text-white md:text-7xl">
                Discover your sound with an account that actually persists.
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-slate-300 md:text-xl">
                Create a user, sign back in later, and connect Spotify through a real session instead of a temporary browser id.
              </p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-5 backdrop-blur-xl">
              <Disc3 className="mb-4 h-8 w-8 text-indigo-300" />
              <h2 className="text-lg font-semibold text-slate-100">Persistent account</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Sign up once and keep the same user record for every future Spotify sync.
              </p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-5 backdrop-blur-xl">
              <Music className="mb-4 h-8 w-8 text-rose-300" />
              <h2 className="text-lg font-semibold text-slate-100">Session-backed OAuth</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Spotify login is tied to the logged-in user, not a client-supplied query parameter.
              </p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-5 backdrop-blur-xl">
              <ListMusic className="mb-4 h-8 w-8 text-fuchsia-300" />
              <h2 className="text-lg font-semibold text-slate-100">Ready for recommendations</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Once linked, the app can ingest history and build songs or playlists against the right account.
              </p>
            </div>
          </div>
        </section>

        <section className="rounded-[2rem] border border-slate-800 bg-slate-900/80 p-6 shadow-[0_30px_120px_-40px_rgba(15,23,42,0.95)] backdrop-blur-2xl md:p-8">
          {user ? (
            <div className="space-y-6">
              <div className="space-y-3">
                <p className="inline-flex items-center gap-2 rounded-full border border-indigo-400/20 bg-indigo-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-indigo-200">
                  <Sparkles className="h-4 w-4" />
                  Session active
                </p>
                <div>
                  <h2 className="text-3xl font-bold text-white">
                    {user.first_name} {user.last_name}
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">
                    @{user.username} | {user.email}
                  </p>
                </div>
              </div>

              <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-5">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Spotify</p>
                <p className="mt-3 text-2xl font-semibold text-white">
                  {user.spotify_connected ? 'Connected and ready to sync.' : 'Not connected yet.'}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  {user.spotify_connected
                    ? 'Reconnect any time if you want to refresh access or re-run ingestion.'
                    : 'Connect Spotify now so the backend can finish OAuth using your authenticated session.'}
                </p>
              </div>

              {(sessionError || formError) && (
                <div className="rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                  {sessionError ?? formError}
                </div>
              )}

              <div className="grid gap-3 sm:grid-cols-2">
                {user.spotify_connected && (
                  <button
                    onClick={() => navigate('/recommendations')}
                    className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-500 px-5 py-3 text-sm font-semibold text-white transition hover:scale-[1.01] hover:shadow-[0_18px_50px_-20px_rgba(16,185,129,0.9)] sm:col-span-2"
                    type="button"
                  >
                    <Sparkles className="h-4 w-4" />
                    Get AI Recommendations
                  </button>
                )}
                <button
                  onClick={handleSpotifyLogin}
                  className="inline-flex items-center justify-center rounded-2xl bg-gradient-to-r from-indigo-500 to-fuchsia-500 px-5 py-3 text-sm font-semibold text-white transition hover:scale-[1.01] hover:shadow-[0_18px_50px_-20px_rgba(99,102,241,0.9)]"
                  type="button"
                >
                  {user.spotify_connected ? 'Reconnect Spotify' : 'Connect Spotify'}
                </button>
                <button
                  onClick={handleLogout}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-700 bg-slate-950/70 px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                  disabled={isSubmitting}
                  type="button"
                >
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" />}
                  Log out
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="space-y-3">
                <div className="inline-flex rounded-full border border-slate-800 bg-slate-950 p-1">
                  <button
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${mode === 'register' ? 'bg-white text-slate-950' : 'text-slate-400'}`}
                    onClick={() => {
                      setMode('register');
                      setFormError(null);
                    }}
                    type="button"
                  >
                    Create account
                  </button>
                  <button
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${mode === 'login' ? 'bg-white text-slate-950' : 'text-slate-400'}`}
                    onClick={() => {
                      setMode('login');
                      setFormError(null);
                    }}
                    type="button"
                  >
                    Log in
                  </button>
                </div>
                <div>
                  <h2 className="text-3xl font-bold text-white">
                    {mode === 'register' ? 'Create your MusicAgent account' : 'Sign back in'}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    {mode === 'register'
                      ? 'Once the account exists, Spotify can link directly to your logged-in session.'
                      : 'Use your email or username to continue where you left off.'}
                  </p>
                </div>
              </div>

              {(sessionError || formError) && (
                <div className="rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                  {sessionError ?? formError}
                </div>
              )}

              {mode === 'register' ? (
                <form className="space-y-4" onSubmit={handleRegisterSubmit}>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-400">First name</span>
                      <input
                        className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-white outline-none transition focus:border-indigo-400"
                        onChange={(event) =>
                          setRegisterForm((current) => ({ ...current, first_name: event.target.value }))
                        }
                        required
                        type="text"
                        value={registerForm.first_name}
                      />
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-400">Last name</span>
                      <input
                        className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-white outline-none transition focus:border-indigo-400"
                        onChange={(event) =>
                          setRegisterForm((current) => ({ ...current, last_name: event.target.value }))
                        }
                        required
                        type="text"
                        value={registerForm.last_name}
                      />
                    </label>
                  </div>

                  <label className="space-y-2 text-sm">
                    <span className="text-slate-400">Username</span>
                    <input
                      className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-white outline-none transition focus:border-indigo-400"
                      onChange={(event) =>
                        setRegisterForm((current) => ({ ...current, username: event.target.value }))
                      }
                      required
                      type="text"
                      value={registerForm.username}
                    />
                  </label>

                  <label className="space-y-2 text-sm">
                    <span className="text-slate-400">Email</span>
                    <input
                      className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-white outline-none transition focus:border-indigo-400"
                      onChange={(event) =>
                        setRegisterForm((current) => ({ ...current, email: event.target.value }))
                      }
                      required
                      type="email"
                      value={registerForm.email}
                    />
                  </label>

                  <label className="space-y-2 text-sm">
                    <span className="text-slate-400">Password</span>
                    <input
                      className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-white outline-none transition focus:border-indigo-400"
                      minLength={8}
                      onChange={(event) =>
                        setRegisterForm((current) => ({ ...current, password: event.target.value }))
                      }
                      required
                      type="password"
                      value={registerForm.password}
                    />
                  </label>

                  <button
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-indigo-500 to-fuchsia-500 px-5 py-3 text-sm font-semibold text-white transition hover:scale-[1.01] hover:shadow-[0_18px_50px_-20px_rgba(99,102,241,0.9)] disabled:cursor-not-allowed disabled:opacity-70"
                    disabled={isSubmitting}
                    type="submit"
                  >
                    {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                    Create account and start session
                  </button>
                </form>
              ) : (
                <form className="space-y-4" onSubmit={handleLoginSubmit}>
                  <label className="space-y-2 text-sm">
                    <span className="text-slate-400">Email or username</span>
                    <input
                      className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-white outline-none transition focus:border-indigo-400"
                      onChange={(event) =>
                        setLoginForm((current) => ({ ...current, identifier: event.target.value }))
                      }
                      required
                      type="text"
                      value={loginForm.identifier}
                    />
                  </label>

                  <label className="space-y-2 text-sm">
                    <span className="text-slate-400">Password</span>
                    <input
                      className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-white outline-none transition focus:border-indigo-400"
                      minLength={8}
                      onChange={(event) =>
                        setLoginForm((current) => ({ ...current, password: event.target.value }))
                      }
                      required
                      type="password"
                      value={loginForm.password}
                    />
                  </label>

                  <button
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-indigo-500 to-fuchsia-500 px-5 py-3 text-sm font-semibold text-white transition hover:scale-[1.01] hover:shadow-[0_18px_50px_-20px_rgba(99,102,241,0.9)] disabled:cursor-not-allowed disabled:opacity-70"
                    disabled={isSubmitting}
                    type="submit"
                  >
                    {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                    Log in
                  </button>
                </form>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default HomePage;
