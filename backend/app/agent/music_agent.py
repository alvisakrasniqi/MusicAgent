import html
import os
from collections import Counter
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.repositories.recommendation_repository import (
    list_recommendation_feedback,
    record_recommendation_feedback,
)
from app.repositories.spotify_repository import get_latest_spotify_snapshot
from app.repositories.user_repository import get_user_mood_context, set_user_mood_context
from app.services.spotify_api import spotify_get, spotify_get_paginated_items

SYSTEM_PROMPT = """\
You are a music recommendation assistant called MusicAgent. You have access to the \
user's Spotify listening data, saved music, playlists, current playback context, \
recent session behavior, stored mood context, and prior recommendation feedback.

A recommendation context bundle is already prefetched and provided in the system prompt. \
Treat that bundle as your baseline source of truth before deciding whether to call any \
extra tools.

Use this data to understand the user's taste and provide personalized music \
recommendations. When recommending songs:
- Explain why each recommendation fits the user's taste or current context
- Consider genre, mood, recent listening session, saved music, playlist themes, and time of day
- Use search_tracks to verify real tracks on Spotify before recommending them
- If the user explicitly says what mood or context they are in today, store it with set_user_mood
- If the user gives explicit feedback about artists, tracks, or recommendation quality, store it with record_feedback
- Use the other context tools only when you need a live refresh or the user asks for details beyond the prefetched bundle
- Do not recommend tracks until you have verified real candidate songs with search_tracks
"""


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _extract_track(item: dict[str, Any]) -> dict[str, Any]:
    track = item.get("track")
    return track if isinstance(track, dict) else item


def _track_display(track: dict[str, Any]) -> str:
    name = track.get("name", "Unknown")
    artists = ", ".join(
        artist.get("name", "")
        for artist in track.get("artists", [])
        if isinstance(artist, dict) and artist.get("name")
    )
    return f"{name} by {artists}" if artists else name


def _format_track_lines(items: list[dict[str, Any]], limit: int = 10) -> list[str]:
    lines: list[str] = []
    for item in items[:limit]:
        track = _extract_track(item)
        if not isinstance(track, dict):
            continue
        lines.append(f"  - {_track_display(track)}")
    return lines


def _summarize_recent_session(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No recent listening session data is available."

    tracks = [_extract_track(item) for item in items if isinstance(_extract_track(item), dict)]
    if not tracks:
        return "No recent listening session data is available."

    artist_counter: Counter[str] = Counter()
    for track in tracks:
        for artist in track.get("artists", []):
            if isinstance(artist, dict) and artist.get("name"):
                artist_counter[artist["name"]] += 1

    parts = [
        "Most recent session tracks:",
        *_format_track_lines(items, limit=8),
    ]
    if artist_counter:
        top_artists = ", ".join(f"{name} ({count})" for name, count in artist_counter.most_common(5))
        parts.append(f"Repeated artists in the recent session: {top_artists}")

    return "\n".join(parts)


def _summarize_feedback(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "No recommendation feedback has been recorded yet."

    feedback_counter: Counter[str] = Counter()
    liked_subjects: list[str] = []
    disliked_subjects: list[str] = []
    noted_preferences: list[str] = []

    for entry in entries:
        feedback_type = str(entry.get("feedback_type", "unknown")).strip().lower()
        feedback_counter[feedback_type] += 1
        item_name = str(entry.get("item_name", "")).strip()
        artist_name = str(entry.get("artist_name", "")).strip()
        subject = item_name if not artist_name else f"{item_name} by {artist_name}"
        if feedback_type in {"like", "love", "save", "want_more_like_this"} and subject:
            liked_subjects.append(subject)
        elif feedback_type in {"dislike", "skip", "too_mellow", "too_heavy"} and subject:
            disliked_subjects.append(subject)

        notes = str(entry.get("notes", "")).strip()
        if notes:
            noted_preferences.append(notes)

    parts = [f"Feedback counts: {dict(feedback_counter)}"]
    if liked_subjects:
        parts.append(f"Positive feedback examples: {', '.join(liked_subjects[:8])}")
    if disliked_subjects:
        parts.append(f"Negative feedback examples: {', '.join(disliked_subjects[:8])}")
    if noted_preferences:
        parts.append(f"Preference notes: {' | '.join(noted_preferences[:5])}")

    return "\n".join(parts)


def _summarize_snapshot(snapshot: dict[str, Any]) -> str:
    parts: list[str] = []

    current_item = snapshot.get("currently_playing")
    if isinstance(current_item, dict) and current_item.get("item"):
        current_track = current_item.get("item")
        if isinstance(current_track, dict):
            parts.append(f"Currently playing: {_track_display(current_track)}")

    top_artists = snapshot.get("top_artists", [])
    if top_artists:
        artist_names = [a.get("name", "Unknown") for a in top_artists[:15] if isinstance(a, dict)]
        genres: set[str] = set()
        for artist in top_artists[:15]:
            if isinstance(artist, dict):
                genres.update(artist.get("genres", []))
        parts.append(f"Top artists: {', '.join(artist_names)}")
        if genres:
            parts.append(f"Genres from top artists: {', '.join(sorted(genres)[:20])}")

    top_tracks = snapshot.get("top_tracks", [])
    if top_tracks:
        parts.append("Top tracks:\n" + "\n".join(_format_track_lines(top_tracks, limit=15)))

    recently_played = snapshot.get("recently_played", [])
    if recently_played:
        parts.append(_summarize_recent_session(recently_played[:15]))

    saved_tracks = snapshot.get("saved_tracks", [])
    if saved_tracks:
        parts.append("Recently saved tracks:\n" + "\n".join(_format_track_lines(saved_tracks, limit=10)))

    user_playlists = snapshot.get("user_playlists", [])
    if user_playlists:
        playlist_lines = []
        for playlist in user_playlists[:8]:
            if not isinstance(playlist, dict):
                continue
            name = playlist.get("name", "Untitled playlist")
            description = html.unescape(str(playlist.get("description") or ""))
            description = _normalize_whitespace(description)
            tracks_total = ((playlist.get("tracks") or {}).get("total")) if isinstance(playlist.get("tracks"), dict) else None
            if description:
                playlist_lines.append(f"  - {name} ({tracks_total or 0} tracks): {description}")
            else:
                playlist_lines.append(f"  - {name} ({tracks_total or 0} tracks)")
        if playlist_lines:
            parts.append("Playlist themes:\n" + "\n".join(playlist_lines))

    audio_features = snapshot.get("audio_features", [])
    if audio_features:
        avg: dict[str, float] = {}
        keys = ["danceability", "energy", "valence", "tempo", "acousticness", "instrumentalness"]
        for key in keys:
            vals = [feature[key] for feature in audio_features if isinstance(feature, dict) and key in feature and feature[key] is not None]
            if vals:
                avg[key] = round(sum(vals) / len(vals), 3)
        if avg:
            avg_str = ", ".join(f"{k}: {v}" for k, v in avg.items())
            parts.append(f"Average audio features across top tracks: {avg_str}")

    warnings = snapshot.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        parts.append(f"Spotify data gaps: {' | '.join(str(w) for w in warnings[:3])}")

    return "\n\n".join(parts) if parts else "No listening data available."


def _access_token_message() -> str:
    return "Spotify access token not available. Cannot use this Spotify tool."


def _get_time_context_text() -> str:
    now = datetime.now().astimezone()
    hour = now.hour
    if 5 <= hour < 11:
        day_part = "morning"
    elif 11 <= hour < 15:
        day_part = "midday"
    elif 15 <= hour < 19:
        day_part = "afternoon"
    elif 19 <= hour < 23:
        day_part = "evening"
    else:
        day_part = "late night"

    weekday = now.strftime("%A")
    is_weekend = weekday in {"Saturday", "Sunday"}
    weekend_label = "weekend" if is_weekend else "workweek"
    return (
        f"It is currently {now.isoformat()} local time. "
        f"Context: {day_part}, {weekday}, {weekend_label}."
    )


def _fetch_saved_tracks_text(access_token: str | None, limit: int = 12) -> str:
    if not access_token:
        return _access_token_message()

    safe_limit = max(1, min(limit, 50))
    try:
        items = spotify_get_paginated_items(
            "/me/tracks",
            access_token,
            params={"limit": safe_limit},
            max_pages=1,
        )
    except HTTPException as exc:
        return str(exc.detail)

    if not items:
        return "No saved tracks were found or the user has not granted saved-track access."

    lines = []
    for item in items[:safe_limit]:
        if not isinstance(item, dict):
            continue
        added_at = item.get("added_at")
        track = _extract_track(item)
        if not isinstance(track, dict):
            continue
        prefix = f"[saved {added_at}] " if isinstance(added_at, str) and added_at else ""
        lines.append(f"- {prefix}{_track_display(track)}")
    return "\n".join(lines)


def _fetch_user_playlists_text(access_token: str | None, limit: int = 8) -> str:
    if not access_token:
        return _access_token_message()

    safe_limit = max(1, min(limit, 20))
    try:
        playlists = spotify_get_paginated_items(
            "/me/playlists",
            access_token,
            params={"limit": safe_limit},
            max_pages=1,
        )
    except HTTPException as exc:
        return str(exc.detail)

    if not playlists:
        return "No playlists were found or playlist read access is unavailable."

    lines: list[str] = []
    for index, playlist in enumerate(playlists[:safe_limit]):
        if not isinstance(playlist, dict):
            continue

        name = playlist.get("name", "Untitled playlist")
        description = html.unescape(str(playlist.get("description") or ""))
        description = _normalize_whitespace(description)
        track_total = ((playlist.get("tracks") or {}).get("total")) if isinstance(playlist.get("tracks"), dict) else None
        base_line = f"- {name} ({track_total or 0} tracks)"
        if description:
            base_line += f": {description}"
        lines.append(base_line)

        playlist_id = playlist.get("id")
        if index < 3 and isinstance(playlist_id, str) and playlist_id:
            try:
                sample_payload = spotify_get(
                    f"/playlists/{playlist_id}/tracks",
                    access_token,
                    params={"limit": 3},
                )
                sample_items = sample_payload.get("items", [])
                if isinstance(sample_items, list) and sample_items:
                    sample_text = ", ".join(
                        _track_display(_extract_track(item))
                        for item in sample_items
                        if isinstance(_extract_track(item), dict)
                    )
                    if sample_text:
                        lines.append(f"  sample tracks: {sample_text}")
            except HTTPException:
                lines.append("  sample tracks unavailable")

    return "\n".join(lines)


def _fetch_currently_playing_text(access_token: str | None) -> str:
    if not access_token:
        return _access_token_message()

    try:
        payload = spotify_get("/me/player/currently-playing", access_token)
    except HTTPException as exc:
        return str(exc.detail)

    current_item = payload.get("item")
    if not isinstance(current_item, dict):
        return "Nothing is currently playing on Spotify."

    context_type = ((payload.get("context") or {}).get("type")) if isinstance(payload.get("context"), dict) else None
    return (
        f"Currently playing: {_track_display(current_item)}"
        + (f" | context: {context_type}" if isinstance(context_type, str) and context_type else "")
    )


def _fetch_recent_session_text(access_token: str | None, limit: int = 15) -> str:
    if not access_token:
        return _access_token_message()

    safe_limit = max(1, min(limit, 50))
    try:
        payload = spotify_get(
            "/me/player/recently-played",
            access_token,
            params={"limit": safe_limit},
        )
    except HTTPException as exc:
        return str(exc.detail)

    items = payload.get("items", [])
    if not isinstance(items, list) or not items:
        return "No recent listening session data is available."
    return _summarize_recent_session(items[:safe_limit])


async def _get_feedback_profile_text(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> str:
    entries = await list_recommendation_feedback(db, user_id, limit=40)
    return _summarize_feedback(entries)


async def _get_user_mood_text(
    db: AsyncIOMotorDatabase,
    user_id: str,
    preferred_context: str = "",
) -> str:
    mood_context = await get_user_mood_context(db, user_id)
    if not mood_context:
        return "No active stored mood context."

    mood_value = str(mood_context.get("value", "")).strip()
    context_value = str(mood_context.get("preferred_context", "")).strip()
    expires_at = mood_context.get("expires_at")
    response = f"Active mood: {mood_value or 'unknown'}"
    if context_value:
        response += f" | preferred context: {context_value}"
    if isinstance(expires_at, datetime):
        response += f" | expires at: {expires_at.isoformat()}"

    requested_context = _normalize_whitespace(preferred_context.strip()) if preferred_context.strip() else ""
    if requested_context and context_value and requested_context.lower() != context_value.lower():
        response += f" | note: requested context '{requested_context}' differs from stored context."

    return response


async def _build_recommendation_context_bundle(
    db: AsyncIOMotorDatabase,
    user_id: str,
    music_profile: str,
    access_token: str | None,
) -> str:
    sections = [
        ("Stored music profile", music_profile),
        ("Feedback profile", await _get_feedback_profile_text(db, user_id)),
        ("Mood context", await _get_user_mood_text(db, user_id)),
        ("Time context", _get_time_context_text()),
    ]

    if access_token:
        sections.extend(
            [
                ("Saved tracks sample", _fetch_saved_tracks_text(access_token, limit=12)),
                ("Playlist sample", _fetch_user_playlists_text(access_token, limit=8)),
                ("Currently playing", _fetch_currently_playing_text(access_token)),
                ("Recent session summary", _fetch_recent_session_text(access_token, limit=15)),
            ]
        )

    formatted_sections = [
        f"{title}:\n{content}"
        for title, content in sections
        if isinstance(content, str) and content.strip()
    ]
    return "\n\n".join(formatted_sections)


def _build_tools(
    db: AsyncIOMotorDatabase,
    user_id: str,
    music_profile: str,
    access_token: str | None,
):
    @tool
    def get_music_profile() -> str:
        """Get the user's stored music taste profile based on their Spotify listening history and latest ingest snapshot."""
        return music_profile

    @tool
    def search_tracks(query: str) -> str:
        """Search Spotify for tracks matching a query. Use this to verify real songs before recommending them."""
        if not access_token:
            return _access_token_message()

        try:
            payload = spotify_get(
                "/search",
                access_token,
                params={"q": query, "type": "track", "limit": 10},
            )
        except HTTPException as exc:
            return str(exc.detail)
        tracks = ((payload.get("tracks") or {}).get("items")) if isinstance(payload.get("tracks"), dict) else []
        if not isinstance(tracks, list) or not tracks:
            return "No tracks found for that query."

        lines = []
        for track in tracks:
            if not isinstance(track, dict):
                continue
            uri = track.get("uri", "")
            lines.append(f"- {_track_display(track)} ({uri})")
        return "\n".join(lines) if lines else "No tracks found for that query."

    @tool
    def get_saved_tracks(limit: int = 25) -> str:
        """Get a sample of the user's recently saved Spotify tracks to understand what they intentionally keep."""
        return _fetch_saved_tracks_text(access_token, limit=limit)

    @tool
    def get_user_playlists(limit: int = 10) -> str:
        """Get the user's playlist themes and a few sample tracks. Use this to infer intent like workout, focus, late-night, or party music."""
        return _fetch_user_playlists_text(access_token, limit=limit)

    @tool
    def get_currently_playing() -> str:
        """Get the track the user is playing right now, if any."""
        return _fetch_currently_playing_text(access_token)

    @tool
    def get_recent_session_summary(limit: int = 15) -> str:
        """Summarize the user's most recent listening session from Spotify recently played data."""
        return _fetch_recent_session_text(access_token, limit=limit)

    @tool
    async def record_feedback(
        item_name: str,
        feedback_type: str,
        artist_name: str = "",
        notes: str = "",
    ) -> str:
        """Record explicit feedback the user gives about songs, artists, or recommendation quality. Use values like like, dislike, save, skip, want_more_like_this, too_mellow, or too_heavy."""
        normalized_feedback = feedback_type.strip().lower().replace(" ", "_")
        created = await record_recommendation_feedback(
            db,
            user_id,
            {
                "item_name": item_name.strip(),
                "artist_name": artist_name.strip() or None,
                "feedback_type": normalized_feedback,
                "notes": notes.strip() or None,
                "source": "agent_tool",
            },
        )
        if not created:
            return "Unable to record feedback."
        return f"Recorded feedback: {normalized_feedback} for {item_name.strip()}."

    @tool
    async def get_feedback_profile() -> str:
        """Get a summary of the user's prior recommendation feedback so new suggestions can adapt to it."""
        return await _get_feedback_profile_text(db, user_id)

    @tool
    async def set_user_mood(
        mood: str,
        preferred_context: str = "",
        duration_hours: int = 8,
    ) -> str:
        """Store an explicit short-lived mood or situational context the user states, such as focus, workout, party, melancholy, commute, or late-night."""
        normalized_mood = _normalize_whitespace(mood.strip().lower())
        if not normalized_mood:
            return "Cannot store an empty mood."

        safe_duration = max(1, min(duration_hours, 72))
        stored = await set_user_mood_context(
            db,
            user_id,
            normalized_mood,
            preferred_context=_normalize_whitespace(preferred_context.strip()) or None,
            duration_hours=safe_duration,
        )
        if stored is None:
            return "Unable to store the user's mood context."

        if preferred_context.strip():
            return f"Stored mood '{normalized_mood}' for context '{_normalize_whitespace(preferred_context.strip())}' for the next {safe_duration} hours."
        return f"Stored mood '{normalized_mood}' for the next {safe_duration} hours."

    @tool
    async def get_user_mood(preferred_context: str = "") -> str:
        """Get the user's active short-lived mood or situational context, optionally filtered for a preferred context like study, commute, or workout."""
        return await _get_user_mood_text(db, user_id, preferred_context=preferred_context)

    @tool
    def get_time_context() -> str:
        """Get the current local time context to adapt recommendations to the moment, such as morning, late night, weekday, or weekend."""
        return _get_time_context_text()

    return [
        get_music_profile,
        get_saved_tracks,
        get_user_playlists,
        get_currently_playing,
        get_recent_session_summary,
        get_feedback_profile,
        record_feedback,
        set_user_mood,
        get_user_mood,
        get_time_context,
        search_tracks,
    ]


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

    baseline_context = await _build_recommendation_context_bundle(
        db,
        user_id,
        music_profile,
        access_token,
    )
    tools = _build_tools(db, user_id, music_profile, access_token)

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
    agent = create_react_agent(llm, tools)

    result = await agent.ainvoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            SystemMessage(content=f"Prefetched recommendation context bundle:\n{baseline_context}"),
            HumanMessage(content=user_message),
        ],
    })

    messages = result.get("messages", [])
    # The last message from the agent is the final response
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and msg.type != "human":
            return msg.content
    return "I wasn't able to generate recommendations. Please try again."
