# MusicAgent

MusicAgent is a full-stack web app for Spotify-based music recommendations.

It lets a user:
- create an account and keep a persistent session
- connect Spotify through OAuth
- ingest listening data into MongoDB
- chat with an AI recommendation agent
- improve future recommendations with saved tracks, playlists, current listening context, mood, time context, and explicit feedback

## Stack

- Frontend: React, TypeScript, React Router, Axios, Tailwind
- Backend: FastAPI, Motor/MongoDB, custom JWT-backed session cookie middleware
- AI: LangGraph + LangChain tools + Gemini
- Integrations: Spotify Web API

## Project Structure

```text
MusicAgent/
├── backend/
│   ├── app/
│   │   ├── agent/             # AI recommendation agent and tool definitions
│   │   ├── api/routes/        # FastAPI routes for auth, Spotify, recommendations, users
│   │   ├── core/              # config, DB connection, session middleware, security
│   │   ├── repositories/      # MongoDB persistence layer
│   │   └── services/          # shared Spotify API helpers
│   └── requirements.txt
├── frontend/
│   ├── src/pages/             # Home, auth callback, recommendations UI
│   ├── src/context/           # auth/session state
│   └── src/lib/api.ts         # API client
└── README.md
```

## How The App Works

### Frontend logic

- `HomePage` handles sign up, login, logout, and the `Connect Spotify` action.
- `AuthContext` restores the current session on app load by calling `/api/auth/me`.
- `AuthCallbackPage` is the frontend landing page after Spotify OAuth. It immediately calls `/api/spotify/ingest`.
- `RecommendationsPage` is the AI chat UI. It sends either free-form prompts or a quick-recommend request to the backend.

Key frontend files:
- [frontend/src/pages/HomePage.tsx](frontend/src/pages/HomePage.tsx)
- [frontend/src/pages/AuthCallbackPage.tsx](frontend/src/pages/AuthCallbackPage.tsx)
- [frontend/src/pages/RecommendationsPage.tsx](frontend/src/pages/RecommendationsPage.tsx)
- [frontend/src/context/AuthContext.tsx](frontend/src/context/AuthContext.tsx)
- [frontend/src/lib/api.ts](frontend/src/lib/api.ts)

### Backend logic

- `auth.py` handles registration, login, logout, and session restoration.
- `spotify.py` starts Spotify OAuth, handles the callback, refreshes tokens when needed, and ingests Spotify data into MongoDB.
- `recommendations.py` validates the user session, gets a valid Spotify access token, and calls the AI agent.
- `music_agent.py` builds the recommendation agent, loads the user music profile, and exposes tools to the model.

Key backend files:
- [backend/app/api/routes/auth.py](backend/app/api/routes/auth.py)
- [backend/app/api/routes/spotify.py](backend/app/api/routes/spotify.py)
- [backend/app/api/routes/recommendations.py](backend/app/api/routes/recommendations.py)
- [backend/app/agent/music_agent.py](backend/app/agent/music_agent.py)
- [backend/app/core/session.py](backend/app/core/session.py)

### End-to-end flow

1. The user opens the frontend and either registers or logs in.
2. The backend creates a signed JWT-backed session cookie.
3. The user clicks `Connect Spotify`.
4. Spotify redirects back to the backend callback.
5. The backend stores Spotify tokens on the user record.
6. The frontend callback page calls `/api/spotify/ingest`.
7. The backend stores a snapshot of Spotify data in MongoDB.
8. The user opens the recommendations page and chats with the AI agent.
9. The agent uses the stored profile plus live Spotify tools to make recommendations.

## Current Agent Logic

The recommendation agent lives in [backend/app/agent/music_agent.py](backend/app/agent/music_agent.py).

It currently has tools for:
- `get_music_profile`
- `search_tracks`
- `get_saved_tracks`
- `get_user_playlists`
- `get_currently_playing`
- `get_recent_session_summary`
- `get_feedback_profile`
- `record_feedback`
- `set_user_mood`
- `get_user_mood`
- `get_time_context`

The agent uses these signals to improve recommendations:
- top artists
- top tracks
- recently played tracks
- saved tracks
- playlist themes
- currently playing track
- recent listening session patterns
- explicit user feedback
- short-lived mood/context
- local time context

## Prerequisites

- Python 3.11+ recommended
- Node.js 18+ recommended
- MongoDB database
- Spotify developer app
- Google API key for Gemini if you want AI recommendations to work

## Backend Setup

From the repo root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If `pip` is missing in the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create `backend/.env` from `backend/.env.example` and set real values.

Recommended local dev values:

```env
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/<db_name>?retryWrites=true&w=majority
MONGODB_DB_NAME=deepbeats

SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/auth/spotify/callback
FRONTEND_URL=http://127.0.0.1:3000

SESSION_SECRET_KEY=change-me-in-production
SESSION_COOKIE_NAME=music_agent_session
SESSION_MAX_AGE_SECONDS=604800
SESSION_HTTPS_ONLY=false

GOOGLE_API_KEY=your_google_api_key
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=music-agent
```

Run the backend:

```powershell
uvicorn app.main:app --reload
```

Backend health check:

```text
GET http://127.0.0.1:8000/health
```

## Frontend Setup

From the repo root:

```powershell
cd frontend
npm install
npm start
```

Open:

```text
http://127.0.0.1:3000
```

Optional frontend env override:

```env
REACT_APP_API_BASE_URL=http://127.0.0.1:8000
```

## Spotify OAuth Setup

In the Spotify developer dashboard, add this exact redirect URI:

```text
http://127.0.0.1:8000/auth/spotify/callback
```

Important:
- Use `127.0.0.1` consistently in local development.
- Do not mix `localhost` and `127.0.0.1` for frontend/backend session flows.
- Spotify rejects insecure `localhost` redirect URI setups for this flow.

## What Gets Stored

### User record

Stored in MongoDB `users` collection:
- account info
- hashed password
- Spotify OAuth tokens
- short-lived mood/context state

### Spotify snapshot

Stored in `spotify_snapshots`:
- top tracks
- top artists
- recently played tracks
- saved tracks
- user playlists
- currently playing
- audio features when Spotify allows them

### Recommendation feedback

Stored in `recommendation_feedback`:
- liked/disliked items
- notes about recommendation quality
- preference corrections like `too_mellow` or `want_more_like_this`

## Main API Routes

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

### Spotify

- `GET /api/spotify/login`
- `GET /auth/spotify/callback`
- `POST /api/spotify/ingest`

### Recommendations

- `POST /api/recommendations/chat`
- `POST /api/recommendations/quick`

## Development Notes

- If you change Spotify scopes, reconnect Spotify and re-run ingest.
- Some Spotify endpoints, especially `audio-features`, may be restricted for newer or development-mode apps. The app now degrades gracefully when that happens.
- The frontend chat UI does not yet have explicit feedback buttons, but the agent can still store feedback when the user says it clearly in chat.

## Known Improvement Areas

- add UI controls for like/dislike/save feedback
- persist chat history server-side
- add playlist creation from recommendations
- add richer frontend state around mood and listening intent
