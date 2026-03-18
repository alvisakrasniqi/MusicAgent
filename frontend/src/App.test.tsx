import React from 'react';
import { render, screen } from '@testing-library/react';

import { AuthProvider } from './context/AuthContext';
import { api } from './lib/api';
import HomePage from './pages/HomePage';

jest.mock('./lib/api', () => ({
  API_BASE_URL: 'http://localhost:8000',
  api: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

test('renders the signed-out landing page when there is no active session', async () => {
  (api.get as jest.Mock).mockRejectedValue({ response: { status: 401 } });

  render(
    <AuthProvider>
      <HomePage />
    </AuthProvider>,
  );

  expect(
    await screen.findByText(/Discover your sound with an account that actually persists/i),
  ).toBeInTheDocument();
});
