#!/usr/bin/env python3
"""Prototype to fetch last 5 AoE2 matches for a player using AoE2 Companion API."""

import json
from datetime import datetime

import requests

# Custom headers to identify our project (required by AoE2 Companion API)
HEADERS = {"User-Agent": "https://github.com/aoe2record-visualizer"}

BASE_URL = "https://data.aoe2companion.com/api"
REPLAY_URL = "https://aoe.ms/replay"


def search_player(search_name: str):
    """Search for a player by name."""
    url = f"{BASE_URL}/profiles"
    params = {"search": search_name}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    data = resp.json()

    profiles = data.get("profiles", [])
    if not profiles:
        return None

    # Return first match (exact match preferred)
    for p in profiles:
        if p.get("name", "").lower() == search_name.lower():
            return p
    return profiles[0]


def get_player_profile(profile_id: int):
    """Get detailed player profile including leaderboard stats."""
    url = f"{BASE_URL}/profiles/{profile_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    return resp.json()


def get_matches(profile_id: int, count: int = 20):
    """Fetch recent matches for a player."""
    url = f"{BASE_URL}/matches"
    params = {
        "profile_ids": profile_id,
        "perPage": count,
    }
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    return resp.json()


def get_replay_url(match_id: int, profile_id: int) -> str:
    """Generate the replay download URL for a match from a player's perspective."""
    return f"{REPLAY_URL}/?gameId={match_id}&profileId={profile_id}"


def format_duration(started: str, finished: str) -> str:
    """Calculate and format match duration."""
    try:
        start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
        duration = end_dt - start_dt
        total_seconds = int(duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"
    except Exception:
        return "Unknown"


def print_match(match: dict, target_profile_id: int):
    """Print a match summary."""
    match_id = match.get("matchId", "Unknown")
    started = match.get("started", "")
    finished = match.get("finished", "")
    map_name = match.get("mapName", "Unknown Map")
    leaderboard = match.get("leaderboardName", "Unknown")

    # Format date
    try:
        date_str = datetime.fromisoformat(started.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M"
        )
    except Exception:
        date_str = started

    print(f"\n{'=' * 60}")
    print(f"Match ID: {match_id}")
    print(f"Date: {date_str}")
    print(f"Duration: {format_duration(started, finished)}")
    print(f"Map: {map_name}")
    print(f"Mode: {leaderboard}")

    print("\nTeams:")
    for team in match.get("teams", []):
        team_id = team.get("teamId", "?")
        print(f"  Team {team_id}:")
        for player in team.get("players", []):
            name = player.get("name", "Unknown")
            civ = player.get("civName", "Unknown")
            rating = player.get("rating", "?")
            won = player.get("won")

            # Mark the target player
            marker = " <<<" if player.get("profileId") == target_profile_id else ""
            result = ""
            if won is True:
                result = " [WIN]"
            elif won is False:
                result = " [LOSS]"

            print(f"    - {name} ({civ}) Rating: {rating}{result}{marker}")

    # Print download link for target player's perspective
    print(f"\nReplay Download: {get_replay_url(match_id, target_profile_id)}")


def main():
    player_name = "ddk220"
    print(f"Searching for player: {player_name}")

    # First, find the player
    player = search_player(player_name)

    if not player:
        print(f"Player '{player_name}' not found.")
        return

    profile_id = player.get("profileId")
    print(f"\nFound player: {player.get('name')}")
    print(f"Profile ID: {profile_id}")
    print(f"Platform: {player.get('platformName', 'Unknown')}")
    print(f"Country: {player.get('country', 'Unknown')}")
    print(f"Total Games: {player.get('games', 'N/A')}")

    # Get detailed profile with leaderboard stats
    print("\nFetching profile details...")
    profile = get_player_profile(profile_id)

    print("\nLeaderboard Rankings:")
    for lb in profile.get("leaderboards", []):
        lb_name = lb.get("leaderboardName", "Unknown")
        rating = lb.get("rating", "?")
        rank = lb.get("rank", "?")
        wins = lb.get("wins", 0)
        losses = lb.get("losses", 0)
        print(f"  {lb_name}: Rating {rating} (Rank #{rank}) - {wins}W/{losses}L")

    # Get recent matches
    print("\n\nFetching recent matches...")
    match_data = get_matches(profile_id, count=10)

    matches = match_data.get("matches", [])
    print(f"\nShowing last 5 of {len(matches)} matches:")

    for match in matches[:5]:
        print_match(match, profile_id)

    # Save raw data for inspection
    with open("match_data_raw.json", "w") as f:
        json.dump(match_data, f, indent=2)
    print(f"\n\nRaw match data saved to match_data_raw.json")


if __name__ == "__main__":
    main()
