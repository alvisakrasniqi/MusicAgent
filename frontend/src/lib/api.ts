import axios from 'axios';

export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL ?? 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
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
