#!/usr/bin/env python3
"""
AoE2 Replay Downloader
Downloads Age of Empires 2 Definitive Edition replay files from aoe2.net
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
from tqdm import tqdm


class AoE2ReplayDownloader:
    """Download AoE2 replays from aoe2.net"""

    def __init__(self, output_dir="replays"):
        self.base_url = "https://aoe2.net/api"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.metadata_file = self.output_dir / "metadata.json"
        self.metadata = self._load_metadata()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AoE2ReplayDownloader/1.0'
        })

    def _load_metadata(self):
        """Load existing metadata file."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {"downloaded_matches": {}}

    def _save_metadata(self):
        """Save metadata to file."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)

    def search_player(self, player_name):
        """
        Search for a player by name.
        Returns list of matching players with their profile IDs.
        """
        print(f"Searching for player: {player_name}")

        url = f"{self.base_url}/leaderboard"
        params = {
            'game': 'aoe2de',
            'leaderboard_id': 3,  # 1v1 Random Map
            'search': player_name,
            'count': 10
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'leaderboard' not in data or not data['leaderboard']:
                print(f"No players found matching '{player_name}'")
                return []

            players = []
            for entry in data['leaderboard']:
                players.append({
                    'name': entry.get('name'),
                    'profile_id': entry.get('profile_id'),
                    'steam_id': entry.get('steam_id'),
                    'rating': entry.get('rating'),
                    'rank': entry.get('rank')
                })

            return players

        except requests.RequestException as e:
            print(f"Error searching for player: {e}")
            return []

    def get_match_history(self, profile_id, start_date=None, count=100):
        """
        Get match history for a player.

        Args:
            profile_id: Player's profile ID
            start_date: Filter matches after this date (datetime object)
            count: Number of matches to fetch

        Returns:
            List of match dictionaries
        """
        print(f"Fetching match history for profile ID: {profile_id}")

        url = f"{self.base_url}/player/matches"
        params = {
            'game': 'aoe2de',
            'profile_id': profile_id,
            'count': count,
            'start': 0
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data:
                print("No matches found")
                return []

            matches = []
            for match in data:
                # Parse match date
                match_date = None
                if 'started' in match:
                    match_date = datetime.fromtimestamp(match['started'])

                # Filter by date if specified
                if start_date and match_date and match_date < start_date:
                    continue

                # Extract match info
                match_info = {
                    'match_id': match.get('match_id'),
                    'match_uuid': match.get('match_uuid'),
                    'started': match_date.isoformat() if match_date else None,
                    'finished': match.get('finished'),
                    'map_type': match.get('map_type'),
                    'leaderboard_id': match.get('leaderboard_id'),
                    'num_players': match.get('num_players'),
                    'players': match.get('players', []),
                    'profile_id': profile_id
                }

                matches.append(match_info)

            print(f"Found {len(matches)} matches")
            return matches

        except requests.RequestException as e:
            print(f"Error fetching match history: {e}")
            return []

    def download_replay(self, match_info, output_dir=None):
        """
        Download a single replay file.

        Args:
            match_info: Match information dictionary
            output_dir: Override output directory

        Returns:
            Path to downloaded file or None if failed
        """
        if output_dir is None:
            output_dir = self.output_dir

        match_id = match_info.get('match_id')
        match_uuid = match_info.get('match_uuid')
        profile_id = match_info.get('profile_id')

        if not match_uuid:
            print(f"No UUID for match {match_id}, skipping")
            return None

        # Check if already downloaded
        if str(match_id) in self.metadata['downloaded_matches']:
            existing_file = self.metadata['downloaded_matches'][str(match_id)]['file_path']
            if Path(existing_file).exists():
                print(f"Already downloaded: {match_id}")
                return Path(existing_file)

        # Construct download URL
        url = f"{self.base_url}/match"
        params = {
            'uuid': match_uuid,
            'profile_id': profile_id
        }

        # Generate filename
        date_str = match_info.get('started', 'unknown')[:10] if match_info.get('started') else 'unknown'
        map_type = match_info.get('map_type', 'unknown')
        filename = f"{date_str}_match_{match_id}_{map_type}.aoe2record"
        filepath = output_dir / filename

        try:
            print(f"Downloading match {match_id}...", end=" ")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            # Check if we got a valid replay file
            content_type = response.headers.get('content-type', '')
            if 'json' in content_type:
                # Might be an error message
                print(f"Failed - replay not available")
                return None

            # Save file
            with open(filepath, 'wb') as f:
                f.write(response.content)

            # Update metadata
            self.metadata['downloaded_matches'][str(match_id)] = {
                'file_path': str(filepath),
                'downloaded_at': datetime.now().isoformat(),
                'match_info': match_info
            }
            self._save_metadata()

            print(f"Success")
            return filepath

        except requests.RequestException as e:
            print(f"Failed - {e}")
            return None

    def bulk_download_replays(self, profile_id, player_name, max_games=None,
                             days_back=90, delay=1.0):
        """
        Download all available replays for a player.

        Args:
            profile_id: Player's profile ID
            player_name: Player's name (for display)
            max_games: Maximum number of games to download
            days_back: Number of days to look back
            delay: Delay between downloads in seconds
        """
        # Calculate start date
        start_date = datetime.now() - timedelta(days=days_back)

        # Get match history
        count = max_games if max_games else 1000
        matches = self.get_match_history(profile_id, start_date, count)

        if not matches:
            print("No matches to download")
            return

        # Limit if max_games specified
        if max_games:
            matches = matches[:max_games]

        print(f"\nDownloading {len(matches)} replays for {player_name}...")
        print("=" * 60)

        # Download with progress bar
        successful = 0
        failed = 0

        for match in tqdm(matches, desc="Downloading replays"):
            result = self.download_replay(match)
            if result:
                successful += 1
            else:
                failed += 1

            # Rate limiting
            time.sleep(delay)

        print("\n" + "=" * 60)
        print(f"Download complete!")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Output directory: {self.output_dir.absolute()}")


def main():
    parser = argparse.ArgumentParser(
        description='Download Age of Empires 2 replay files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for a player
  python download_replays.py --search "playerName"

  # Download replays for a specific player
  python download_replays.py --player "playerName" --count 50

  # Download from last 30 days
  python download_replays.py --player "playerName" --days 30

  # Specify output directory
  python download_replays.py --player "playerName" --output ./my_replays
        """
    )

    parser.add_argument('--search', '-s', type=str,
                       help='Search for players by name')
    parser.add_argument('--player', '-p', type=str,
                       help='Player name to download replays for')
    parser.add_argument('--profile-id', type=int,
                       help='Player profile ID (if known)')
    parser.add_argument('--count', '-c', type=int, default=100,
                       help='Maximum number of replays to download (default: 100)')
    parser.add_argument('--days', '-d', type=int, default=90,
                       help='Number of days to look back (default: 90)')
    parser.add_argument('--output', '-o', type=str, default='replays',
                       help='Output directory for replays (default: replays)')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay between downloads in seconds (default: 1.0)')

    args = parser.parse_args()

    # Create downloader
    downloader = AoE2ReplayDownloader(output_dir=args.output)

    # Search mode
    if args.search:
        players = downloader.search_player(args.search)
        if players:
            print(f"\nFound {len(players)} player(s):")
            print("-" * 80)
            for player in players:
                print(f"Name: {player['name']:20s} | "
                      f"Profile ID: {player['profile_id']:10d} | "
                      f"Rating: {player['rating']:4d} | "
                      f"Rank: {player['rank']}")
            print("\nUse --profile-id with the desired Profile ID to download replays")
        return

    # Download mode
    if args.profile_id:
        # Direct download with profile ID
        downloader.bulk_download_replays(
            profile_id=args.profile_id,
            player_name=f"Player {args.profile_id}",
            max_games=args.count,
            days_back=args.days,
            delay=args.delay
        )
    elif args.player:
        # Search for player first, then download
        players = downloader.search_player(args.player)
        if not players:
            print("Player not found")
            return

        # If multiple matches, ask user to choose
        if len(players) > 1:
            print(f"\nFound {len(players)} players:")
            for i, player in enumerate(players):
                print(f"  {i+1}. {player['name']} (ID: {player['profile_id']}, "
                      f"Rating: {player['rating']})")

            choice = input("\nSelect player number (or press Enter for #1): ").strip()
            if choice == '':
                idx = 0
            else:
                try:
                    idx = int(choice) - 1
                    if idx < 0 or idx >= len(players):
                        print("Invalid choice")
                        return
                except ValueError:
                    print("Invalid input")
                    return
        else:
            idx = 0

        selected_player = players[idx]
        print(f"\nSelected: {selected_player['name']} (ID: {selected_player['profile_id']})")

        # Download replays
        downloader.bulk_download_replays(
            profile_id=selected_player['profile_id'],
            player_name=selected_player['name'],
            max_games=args.count,
            days_back=args.days,
            delay=args.delay
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
