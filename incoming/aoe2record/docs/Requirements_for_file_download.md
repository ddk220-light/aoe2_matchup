Instructions for Claude Code Script
Here's a comprehensive guide you can give to Claude Code to create a script that will search for players and download their recorded games:
markdown# AOE2 Record File Downloader Script Requirements

## Overview
Create a Python script that can search for AOE2 players and download their recorded game files from the last 3 months.

## Core Features Needed:
1. Search for players by name
2. Get player profile IDs
3. List available recorded games with metadata (date, map, civilizations)
4. Filter games by date range (last 3 months)
5. Bulk download .aoe2record files for a specific player

## APIs and Endpoints to Use:

### 1. RelicLink API (Primary Source)
- Base URL: https://aoe-api.reliclink.com/
- Get recent match history: 
  `/community/leaderboard/getRecentMatchHistory?title=age2&matchtype_id=8&profile_ids=[profile_id]`
- Note: matchtype_id values:
  - 8: Ranked 1v1
  - Other IDs available in the API

### 2. Official Age of Empires Stats (Backup Source)
- Base URL: https://www.ageofempires.com/stats/ageiide/
- Note: This requires web scraping as there's no official API documentation

### 3. AOE2 Insights (Alternative)
- Website: https://www.aoe2insights.com/
- Can search for players and view match history
- Provides download links for recorded games
- Note: Requires web scraping

## Technical Implementation:

### Required Libraries:
```python
# Install these packages
pip install requests beautifulsoup4 pandas tqdm
Key Functions to Implement:

search_player(player_name)

Search for player by name
Return list of matching players with profile IDs


get_match_history(profile_id, start_date=None)

Fetch match history for a profile ID
Filter by date if provided (last 3 months)
Return list of matches with metadata


download_replay(match_id, output_dir)

Download individual replay file
Save as .aoe2record file


bulk_download_replays(profile_id, output_dir, max_games=None)

Download all available replays for a player
Optional limit on number of games



Data Structure for Match Information:
python{
    "match_id": "123456",
    "date": "2025-01-15",
    "map": "Arabia",
    "players": [
        {"name": "Player1", "civ": "Franks", "rating": 1200},
        {"name": "Player2", "civ": "Britons", "rating": 1180}
    ],
    "duration": "25:30",
    "download_url": "https://..."
}
Error Handling:

Handle rate limiting (implement delays between requests)
Check if replay files are available (some may be private)
Validate downloaded files
Handle network errors gracefully

Output:

Save files with descriptive names: {date}_{player1}_vs_{player2}_{map}.aoe2record
Create a metadata JSON file with match information
Progress bar for bulk downloads

Additional Features (Optional):

Filter by map type
Filter by game mode (1v1, team games)
Search multiple players at once
Resume interrupted downloads
Verify file integrity after download

Important Notes:

Some replays may not be publicly available
Older replays (>3 months) may have been removed
Respect rate limits to avoid being blocked
The script should handle missing or incomplete data gracefully