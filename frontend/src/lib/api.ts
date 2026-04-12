import axios from 'axios';

function getApiBaseUrl() {
  const configuredBaseUrl = process.env.REACT_APP_API_BASE_URL?.trim();
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/+$/, '');
  }

  if (process.env.NODE_ENV === 'development') {
    return 'http://127.0.0.1:8000';
  }

  return '';
}

export const API_BASE_URL = getApiBaseUrl();

export const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  withCredentials: true,
});

export async function postChat(message: string) {
  const res = await api.post('/api/recommendations/chat', { message });
  return res.data as { reply: string; timestamp: string };
}

export async function postQuickRecommend() {
  const res = await api.post('/api/recommendations/quick');
  return res.data as { reply: string; timestamp: string };
}

export async function postDiscoverMusic(message?: string) {
  const res = await api.post('/api/recommendations/discover', {
    message: message?.trim() ? message.trim() : undefined,
  });
  return res.data as { reply: string; timestamp: string };
}
