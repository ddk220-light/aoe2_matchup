# AoE2 Replay Download API Notes

## ⚠️ IMPORTANT UPDATE

**aoe2.net has been sunset** (as of October 2025) and is no longer functional. The API and all data are no longer accessible.

## Current Status of APIs

### ❌ aoe2.net API - DEFUNCT
- Base URL: `https://aoe2.net/api`
- **Status**: Shut down permanently
- Previously had endpoints for leaderboard, matches, and downloads

### ❌ RelicLink API - NOT WORKING
- Base URL: `https://aoe-api.reliclink.com/`
- **Status**: SSL certificate issues, appears to be down
- Endpoint from docs: `/community/leaderboard/getRecentMatchHistory`

### ✅ aoe2insights.com - PARTIALLY AVAILABLE
- Base URL: `https://www.aoe2insights.com/api/`
- **Status**: Website is up, limited API endpoints
- Has some API but requires web scraping for full functionality

## Alternative Data Sources

### 1. aoe2.net (Documented but may be outdated)
- Base URL: `https://aoe2.net/api`
- Previously had endpoints for:
  - `/leaderboard` - Search players
  - `/player/matches` - Get match history
  - `/match` - Download replay

### 2. Age of Empires Official Site
- URL: `https://www.ageofempires.com/stats/`
- Requires web scraping (no public API)
- Can view match history and download replays

### 3. aoe2insights.com
- URL: `https://www.aoe2insights.com/`
- Search players: `https://www.aoe2insights.com/user/{profileId}/matches/`
- Download replays directly from match pages
- Requires web scraping

## Recommended Next Steps

1. **Test the current script** - Try searching for a player to see if it works
2. **Check aoe2.net** - Visit https://aoe2.net to see if there's updated API documentation
3. **Use web scraping** - If APIs don't work, implement scraping from aoe2insights.com
4. **Contact aoe2.net** - Ask for current API documentation

## Web Scraping Alternative

If you need to implement web scraping, you would:

```python
import requests
from bs4 import BeautifulSoup

# Example for aoe2insights.com
def scrape_player_matches(profile_id):
    url = f"https://www.aoe2insights.com/user/{profile_id}/matches/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find match links and download buttons
    matches = soup.find_all('div', class_='match-item')
    # Extract match IDs and download links
    ...
```

## Testing the Script

Try these commands to test if the API works:

```bash
# Test search (may fail if API is down)
python3 download_replays.py --search "test"

# If you know a profile ID, try downloading directly
python3 download_replays.py --profile-id 123456 --count 1
```

## Known Working Profile IDs (for testing)

If you know specific player profile IDs, you can test with those directly.
You can find profile IDs by:
1. Visiting aoe2.net and searching for a player
2. Looking at the URL when viewing their profile
3. Using community resources like aoe2 forums

## Updating the Script

If you find working API endpoints, update the `AoE2ReplayDownloader` class in `download_replays.py`:

```python
self.base_url = "https://NEW_API_URL"  # Update this
```

Then update the endpoint paths in the methods:
- `search_player()`
- `get_match_history()`
- `download_replay()`
