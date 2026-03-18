import React, { useState } from 'react';
import { ArrowLeft, Loader2, Send, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { postChat, postQuickRecommend } from '../lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const RecommendationsPage: React.FC = () => {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    const userMsg: Message = { role: 'user', content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsSending(true);

    try {
      const data = await postChat(trimmed);
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Something went wrong. Please try again.' },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  async function handleQuickRecommend() {
    if (isSending) return;
    setIsSending(true);
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: 'Give me quick recommendations based on my listening history!' },
    ]);

    try {
      const data = await postQuickRecommend();
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Something went wrong. Please try again.' },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">
        <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-white gap-4">
        <p className="text-slate-400">You need to be logged in to get recommendations.</p>
        <button
          onClick={() => navigate('/')}
          className="rounded-2xl border border-slate-700 px-5 py-2 text-sm text-slate-200 hover:bg-slate-900"
        >
          Go to login
        </button>
      </div>
    );
  }

  if (!user.spotify_connected) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-white gap-4">
        <p className="text-slate-400">Connect Spotify first to get personalized recommendations.</p>
        <button
          onClick={() => navigate('/')}
          className="rounded-2xl border border-slate-700 px-5 py-2 text-sm text-slate-200 hover:bg-slate-900"
        >
          Go back and connect Spotify
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-white">
      {/* Header */}
      <header className="flex items-center gap-3 border-b border-slate-800 px-6 py-4">
        <button
          onClick={() => navigate('/')}
          className="rounded-xl p-2 text-slate-400 hover:bg-slate-900 hover:text-white transition"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-lg font-bold">MusicAgent</h1>
          <p className="text-xs text-slate-500">AI-powered music recommendations</p>
        </div>
        <button
          onClick={handleQuickRecommend}
          disabled={isSending}
          className="ml-auto inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-indigo-500 to-fuchsia-500 px-4 py-2 text-sm font-semibold transition hover:scale-[1.01] disabled:opacity-60"
        >
          <Sparkles className="h-4 w-4" />
          Quick recommend
        </button>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 py-20">
            <Sparkles className="h-10 w-10 text-indigo-400" />
            <p className="text-xl font-semibold text-slate-200">What kind of music are you in the mood for?</p>
            <p className="text-sm text-slate-500 max-w-md">
              Ask me anything — "something chill for studying", "energetic workout playlist",
              or "artists similar to my top listens".
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`max-w-2xl ${msg.role === 'user' ? 'ml-auto' : 'mr-auto'}`}
          >
            <div
              className={`rounded-2xl px-5 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-indigo-500/20 border border-indigo-500/30 text-indigo-100'
                  : 'bg-slate-900 border border-slate-800 text-slate-200'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {isSending && (
          <div className="max-w-2xl mr-auto">
            <div className="rounded-2xl bg-slate-900 border border-slate-800 px-5 py-3 text-sm text-slate-400 flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="border-t border-slate-800 px-6 py-4">
        <div className="mx-auto flex max-w-2xl items-center gap-3">
          <input
            className="flex-1 rounded-2xl border border-slate-800 bg-slate-900 px-5 py-3 text-sm text-white outline-none transition focus:border-indigo-400 placeholder:text-slate-600"
            placeholder="Ask for music recommendations..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isSending}
          />
          <button
            type="submit"
            disabled={isSending || !input.trim()}
            className="rounded-2xl bg-indigo-500 p-3 text-white transition hover:bg-indigo-400 disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
};

export default RecommendationsPage;
