import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.repositories.spotify_repository import get_latest_spotify_snapshot

SYSTEM_PROMPT = """\
You are a music recommendation assistant called MusicAgent. You have access to the \
user's Spotify listening data including their top tracks, top artists, recently played \
tracks, and audio features (danceability, energy, valence, tempo, etc.).

Use this data to understand the user's taste and provide personalized music \
recommendations. When recommending songs:
- Explain WHY you think they'd enjoy each recommendation based on their listening patterns
- Consider genre, mood, energy level, and similar artists
- Be conversational and enthusiastic about music
- If the user asks for something specific (e.g. "workout music", "chill vibes"), \
tailor recommendations to that context while still drawing on their taste profile

You can reference specific tracks and artists from their history to explain your reasoning.

You have tools available:
- get_music_profile: retrieves the user's full listening profile summary
- search_tracks: searches Spotify for tracks matching a query

Always call get_music_profile first to understand the user's taste before making recommendations. \
Then use search_tracks to find real tracks on Spotify that match what you want to recommend.\
"""


def _summarize_snapshot(snapshot: dict[str, Any]) -> str:
    parts: list[str] = []

    top_artists = snapshot.get("top_artists", [])
    if top_artists:
        artist_names = [a.get("name", "Unknown") for a in top_artists[:15]]
        genres: set[str] = set()
        for a in top_artists[:15]:
            genres.update(a.get("genres", []))
        parts.append(f"Top artists: {', '.join(artist_names)}")
        if genres:
            parts.append(f"Genres from top artists: {', '.join(sorted(genres)[:20])}")

    top_tracks = snapshot.get("top_tracks", [])
    if top_tracks:
        track_lines = []
        for t in top_tracks[:20]:
            name = t.get("name", "Unknown")
            artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
            track_lines.append(f"  - {name} by {artists}")
        parts.append("Top tracks:\n" + "\n".join(track_lines))

    recently_played = snapshot.get("recently_played", [])
    if recently_played:
        recent_lines = []
        for item in recently_played[:10]:
            t = item.get("track", item)
            name = t.get("name", "Unknown")
            artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
            recent_lines.append(f"  - {name} by {artists}")
        parts.append("Recently played:\n" + "\n".join(recent_lines))

    audio_features = snapshot.get("audio_features", [])
    if audio_features:
        avg = {}
        keys = ["danceability", "energy", "valence", "tempo", "acousticness", "instrumentalness"]
        for key in keys:
            vals = [f[key] for f in audio_features if key in f and f[key] is not None]
            if vals:
                avg[key] = round(sum(vals) / len(vals), 3)
        if avg:
            avg_str = ", ".join(f"{k}: {v}" for k, v in avg.items())
            parts.append(f"Average audio features across top tracks: {avg_str}")

    return "\n\n".join(parts) if parts else "No listening data available."


def _build_tools(music_profile: str, access_token: str | None):
    @tool
    def get_music_profile() -> str:
        """Get the user's music taste profile based on their Spotify listening history."""
        return music_profile

    @tool
    def search_tracks(query: str) -> str:
        """Search Spotify for tracks matching a query. Use this to find specific songs or discover tracks by genre/mood/artist."""
        if not access_token:
            return "Spotify access token not available. Cannot search tracks."
        import requests
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"q": query, "type": "track", "limit": 10}
        resp = requests.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params=params,
            timeout=15,
        )
        if resp.status_code >= 400:
            return f"Spotify search failed with status {resp.status_code}"
        tracks = resp.json().get("tracks", {}).get("items", [])
        if not tracks:
            return "No tracks found for that query."
        lines = []
        for t in tracks:
            name = t.get("name", "Unknown")
            artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
            uri = t.get("uri", "")
            lines.append(f"- {name} by {artists} ({uri})")
        return "\n".join(lines)

    return [get_music_profile, search_tracks]


async def run_agent(
    db: AsyncIOMotorDatabase,
    user_id: str,
    user_message: str,
    access_token: str | None = None,
) -> str:
    os.environ.setdefault("GOOGLE_API_KEY", settings.GOOGLE_API_KEY)
    os.environ.setdefault("LANGSMITH_API_KEY", settings.LANGSMITH_API_KEY)
    if settings.LANGSMITH_TRACING:
        os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", settings.LANGSMITH_PROJECT)

    snapshot = await get_latest_spotify_snapshot(db, user_id)
    if not snapshot:
        music_profile = "No Spotify data found. The user hasn't ingested their listening history yet."
    else:
        music_profile = _summarize_snapshot(snapshot)

    tools = _build_tools(music_profile, access_token)

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
    agent = create_react_agent(llm, tools)

    result = await agent.ainvoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            SystemMessage(content=f"Here is the user's current music profile:\n{music_profile}"),
            HumanMessage(content=user_message),
        ],
    })

    messages = result.get("messages", [])
    # The last message from the agent is the final response
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and msg.type != "human":
            return msg.content
    return "I wasn't able to generate recommendations. Please try again."
