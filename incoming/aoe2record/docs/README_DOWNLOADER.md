# AoE2 Replay Downloader

Download Age of Empires 2 Definitive Edition replay files for analysis.

## Installation

```bash
pip install requests tqdm
```

## Usage

### Search for a Player

```bash
python download_replays.py --search "playerName"
```

This will show matching players with their profile IDs and ratings.

### Download Replays

#### By Player Name (Interactive)
```bash
python download_replays.py --player "playerName" --count 50
```

If multiple players match, you'll be prompted to select one.

#### By Profile ID (Direct)
```bash
python download_replays.py --profile-id 123456 --count 50
```

### Options

- `--count`, `-c`: Maximum number of replays to download (default: 100)
- `--days`, `-d`: Number of days to look back (default: 90)
- `--output`, `-o`: Output directory (default: replays)
- `--delay`: Delay between downloads in seconds (default: 1.0)

### Examples

```bash
# Search for players named "TheViper"
python download_replays.py --search "TheViper"

# Download last 30 days of replays
python download_replays.py --player "playerName" --days 30

# Download 25 replays to custom directory
python download_replays.py --player "playerName" --count 25 --output ./my_replays

# Download with faster rate (be careful with rate limiting)
python download_replays.py --profile-id 123456 --delay 0.5
```

## Output

Replays are saved with descriptive filenames:
```
2024-10-09_match_123456_arabia.aoe2record
2024-10-08_match_123457_arena.aoe2record
```

A `metadata.json` file is created tracking all downloaded matches to avoid duplicates.

## Features

- ✅ Search players by name
- ✅ Download replays from last 3 months (configurable)
- ✅ Avoid duplicate downloads
- ✅ Progress bars for batch downloads
- ✅ Rate limiting to respect API limits
- ✅ Metadata tracking
- ✅ Error handling and retry logic

## Integration with Analyzer

After downloading replays, analyze them:

```bash
# Analyze a single replay
python aoe2_analyzer.py replays/2024-10-09_match_123456_arabia.aoe2record -v -s

# Analyze all downloaded replays
for file in replays/*.aoe2record; do
    python aoe2_analyzer.py "$file" --strategy
done
```

## Data Source

This script uses the [aoe2.net API](https://aoe2.net/#api) to search for players and download replay files.

## Troubleshooting

**No replays found:**
- Some players may not have publicly available replays
- Try expanding the date range with `--days 180`

**Download fails:**
- Check your internet connection
- The replay might not be available anymore
- Try increasing the delay with `--delay 2.0`

**Rate limiting:**
- If you get blocked, increase the delay between requests
- Default delay is 1 second, try `--delay 2.0` or higher
