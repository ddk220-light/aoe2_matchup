#!/usr/bin/env python3
"""
AoE2 Record Analyzer
Analyzes Age of Empires 2 recorded game files (.aoe2record) using the mgz library.
"""

import sys
import os
import argparse
from datetime import timedelta
from pathlib import Path
import mgz.summary
import mgz


def format_duration(seconds):
    """Convert seconds to readable time format."""
    return str(timedelta(seconds=int(seconds)))


def format_timestamp(time_value):
    """Convert time value to readable timestamp."""
    # If it's already a timedelta, just return it as string
    if isinstance(time_value, timedelta):
        return str(time_value)
    # Otherwise treat as milliseconds
    seconds = time_value / 1000
    return str(timedelta(seconds=int(seconds)))


def get_victory_condition(match):
    """Determine the victory condition."""
    try:
        if hasattr(match, 'postgame') and match.postgame:
            # Try to get victory condition from postgame data
            return "Conquest"  # Default for now
        return "Unknown"
    except Exception:
        return "Unknown"


def analyze_villager_production(file_path):
    """Analyze villager production and economy milestones by player over time."""

    print("\n" + "=" * 80)
    print("ECONOMY ANALYSIS - VILLAGERS & MILESTONES (First 15 Minutes)")
    print("=" * 80)
    print()

    try:
        with open(file_path, 'rb') as f:
            match = mgz.model.parse_match(f)

            # Get all players
            players = match.players
            player_names = [p.name for p in players]

            # Initialize data structures
            villager_by_minute = {}
            tc_by_minute = {}

            # Track milestone times (technology research and age ups)
            milestones = {
                'loom': {},
                'wheelbarrow': {},
                'feudal': {},
                'castle': {}
            }

            # Parse all actions
            for action in match.actions:
                minute = int(action.timestamp.total_seconds() // 60)
                player_idx = players.index(action.player) if action.player in players else -1

                if player_idx < 0:
                    continue

                # Count villagers
                if action.payload and 'villager' in str(action.payload).lower():
                    if minute not in villager_by_minute:
                        villager_by_minute[minute] = [0] * len(players)
                    amount = action.payload.get('amount', 1)
                    villager_by_minute[minute][player_idx] += amount

                # Count Town Centers (only first 15 minutes)
                if minute <= 15 and action.payload and 'building' in action.payload:
                    building = str(action.payload.get('building', '')).lower()
                    if 'town center' in building:
                        if minute not in tc_by_minute:
                            tc_by_minute[minute] = [0] * len(players)
                        tc_by_minute[minute][player_idx] += 1

                # Track technology research
                if action.payload and 'technology' in action.payload:
                    tech = str(action.payload.get('technology', '')).lower()
                    timestamp = action.timestamp

                    if 'loom' in tech and player_idx not in milestones['loom']:
                        milestones['loom'][player_idx] = timestamp
                    elif 'wheelbarrow' in tech and player_idx not in milestones['wheelbarrow']:
                        milestones['wheelbarrow'][player_idx] = timestamp
                    elif 'feudal' in tech and player_idx not in milestones['feudal']:
                        milestones['feudal'][player_idx] = timestamp
                    elif 'castle' in tech and player_idx not in milestones['castle']:
                        milestones['castle'][player_idx] = timestamp

            # Calculate cumulative totals (limit to 15 minutes)
            max_minute = min(15, max(villager_by_minute.keys()) if villager_by_minute else 15)
            cumulative_villagers = [[0] * len(players) for _ in range(max_minute + 1)]
            cumulative_tcs = [[1] * len(players) for _ in range(max_minute + 1)]  # Start with 1 TC

            for minute in range(max_minute + 1):
                for player_idx in range(len(players)):
                    # Villagers
                    prev_vils = cumulative_villagers[minute - 1][player_idx] if minute > 0 else 0
                    this_minute_vils = villager_by_minute.get(minute, [0] * len(players))[player_idx]
                    cumulative_villagers[minute][player_idx] = prev_vils + this_minute_vils

                    # Town Centers
                    prev_tcs = cumulative_tcs[minute - 1][player_idx] if minute > 0 else 1
                    this_minute_tcs = tc_by_minute.get(minute, [0] * len(players))[player_idx]
                    cumulative_tcs[minute][player_idx] = prev_tcs + this_minute_tcs

            # Print table header
            header = "Time |"
            for name in player_names:
                header += f" {name[:10]:^10} |"
            print(header)
            print("-" * len(header))

            # Print each minute row with villager count and TC count
            for minute in range(max_minute + 1):
                # Villager row
                row = f"{minute:2d}:00 |"
                for player_idx in range(len(players)):
                    vils = cumulative_villagers[minute][player_idx]
                    tcs = cumulative_tcs[minute][player_idx]
                    row += f" {vils:3d}v/{tcs}tc |"
                print(row)

            # Print milestones
            print("\n" + "=" * 80)
            print("MILESTONES")
            print("=" * 80)
            print()

            milestone_names = {
                'loom': 'Loom',
                'wheelbarrow': 'Wheelbarrow',
                'feudal': 'Feudal Age',
                'castle': 'Castle Age'
            }

            for milestone_key, milestone_name in milestone_names.items():
                print(f"{milestone_name}:")
                milestone_data = milestones[milestone_key]
                if milestone_data:
                    for player_idx in sorted(milestone_data.keys()):
                        timestamp = milestone_data[player_idx]
                        print(f"  {player_names[player_idx]:20s} - {str(timestamp)}")
                else:
                    print(f"  No data recorded")
                print()

    except Exception as e:
        print(f"ERROR: Failed to analyze villager production: {e}")
        import traceback
        traceback.print_exc()


def analyze_strategy(file_path):
    """Analyze opening strategy for each player."""

    print("\n" + "=" * 80)
    print("STRATEGY ANALYSIS (First 20 Minutes)")
    print("=" * 80)
    print()

    try:
        with open(file_path, 'rb') as f:
            match = mgz.model.parse_match(f)

            players = match.players
            player_names = [p.name for p in players]

            # Track key events for each player
            player_data = {}
            for idx, player in enumerate(players):
                player_data[idx] = {
                    'name': player.name,
                    'feudal_time': None,
                    'castle_time': None,
                    'first_military_unit': None,
                    'military_units_before_castle': [],
                    'tcs_built_after_castle': [],
                    'military_units_after_castle': []
                }

            # Parse actions (first 20 minutes only)
            for action in match.actions:
                minute = action.timestamp.total_seconds() / 60
                if minute > 20:
                    break

                player_idx = players.index(action.player) if action.player in players else -1
                if player_idx < 0 or not action.payload:
                    continue

                data = player_data[player_idx]

                # Track age research
                if 'technology' in action.payload:
                    tech = str(action.payload.get('technology', '')).lower()
                    if 'feudal' in tech and not data['feudal_time']:
                        data['feudal_time'] = action.timestamp
                    elif 'castle' in tech and not data['castle_time']:
                        data['castle_time'] = action.timestamp

                # Track military unit production
                if 'unit' in action.payload:
                    unit = str(action.payload.get('unit', '')).lower()
                    # Filter out villagers and fishing ships (non-military)
                    if 'villager' not in unit and 'fishing' not in unit and 'trade' not in unit:
                        # Track first military unit
                        if not data['first_military_unit']:
                            data['first_military_unit'] = (action.timestamp, unit)

                        # Track military before castle
                        if data['castle_time'] is None:
                            data['military_units_before_castle'].append((action.timestamp, unit))
                        # Track military after castle (within 5 minutes of castle age)
                        elif data['castle_time'] and (action.timestamp - data['castle_time']).total_seconds() < 300:
                            data['military_units_after_castle'].append((action.timestamp, unit))

                # Track Town Centers built after castle age
                if 'building' in action.payload:
                    building = str(action.payload.get('building', '')).lower()
                    if 'town center' in building:
                        # Only count TCs built after castle age research started
                        if data['castle_time'] and action.timestamp > data['castle_time']:
                            data['tcs_built_after_castle'].append(action.timestamp)

            # Analyze strategy for each player
            print("PLAYER STRATEGIES:\n")
            for idx, data in player_data.items():
                name = data['name']
                print(f"{name}:")

                strategy = []

                # Determine feudal strategy
                if data['feudal_time']:
                    feudal_mins = int(data['feudal_time'].total_seconds() / 60)

                    if data['military_units_before_castle']:
                        # Feudal aggression
                        unit_types = set([u[1] for u in data['military_units_before_castle']])
                        strategy.append(f"Executed a Feudal Age rush at {feudal_mins} minutes, producing {', '.join(unit_types)} before advancing to Castle Age")
                    elif data['castle_time']:
                        castle_mins = int(data['castle_time'].total_seconds() / 60)
                        strategy.append(f"Went for a fast Castle Age at {castle_mins} minutes with minimal military production in Feudal Age")
                    else:
                        strategy.append(f"Advanced to Feudal Age at {feudal_mins} minutes with limited military production")
                else:
                    strategy.append("Strategy unclear - no Feudal Age advancement detected in first 20 minutes")

                # Determine castle age strategy
                if data['castle_time']:
                    tcs_after = len(data['tcs_built_after_castle'])
                    military_after = len(data['military_units_after_castle'])

                    if tcs_after >= 2:
                        strategy.append(f"In Castle Age, focused on booming by building {tcs_after} additional Town Centers")
                    elif military_after >= 3:
                        unit_types = set([u[1] for u in data['military_units_after_castle']])
                        strategy.append(f"Played aggressively in Castle Age, quickly producing {', '.join(unit_types)}")
                    elif tcs_after == 1 and military_after > 0:
                        strategy.append(f"In Castle Age, balanced economy (built {tcs_after} TC) with military production")
                    elif military_after == 0 and tcs_after == 0:
                        strategy.append("In Castle Age, maintained a conservative approach with minimal expansion or military")
                    else:
                        strategy.append("Castle Age strategy unclear from available data")
                elif data['feudal_time']:
                    # Stayed in feudal for first 20 minutes
                    strategy.append("Remained in Feudal Age focusing on early aggression or economy")

                # Print strategy summary (2 sentences)
                print(f"  {strategy[0]}. ", end="")
                if len(strategy) > 1:
                    print(f"{strategy[1]}.")
                else:
                    print()
                print()

    except Exception as e:
        print(f"ERROR: Failed to analyze strategy: {e}")
        import traceback
        traceback.print_exc()


def analyze_detailed_actions(file_path, max_actions=None, filter_term=None):
    """Parse and display detailed game actions."""

    print("\n" + "=" * 80)
    print("DETAILED ACTION ANALYSIS")
    print("=" * 80)

    if filter_term:
        print(f"(Filter: {filter_term})")
    if max_actions:
        print(f"(Showing first {max_actions} actions)\n")
    else:
        print("(Showing all actions - this may take a while)\n")

    try:
        with open(file_path, 'rb') as f:
            # Parse the match
            match = mgz.model.parse_match(f)

            print(f"Match duration: {match.duration}")
            print(f"Total actions in match: {len(match.actions)}")
            print(f"Chat messages: {len(match.chat)}\n")

            # First, show any chat messages
            if match.chat:
                print("=== CHAT MESSAGES ===")
                for msg in match.chat[:10 if max_actions else None]:  # Limit chat display
                    timestamp = format_timestamp(msg.timestamp)
                    player_name = msg.player.name if hasattr(msg, 'player') and msg.player else 'Unknown'
                    print(f"[{timestamp}] {player_name}: {msg.message}")
                print()

            # Now show player actions
            print("=== PLAYER ACTIONS ===")
            action_count = 0

            # When filtering, we need to go through all actions, not just the first max_actions
            actions_to_iterate = match.actions

            for action in actions_to_iterate:
                try:
                    timestamp = format_timestamp(action.timestamp)
                    player_name = action.player.name if hasattr(action, 'player') and action.player else 'Unknown'
                    action_type = action.type if hasattr(action, 'type') else 'Unknown'

                    # Apply filter if specified
                    if filter_term:
                        filter_lower = filter_term.lower()

                        # Check if filter matches the action
                        match_found = False

                        # Check action type
                        if filter_lower in str(action_type).lower():
                            match_found = True

                        # Check payload for relevant data
                        if hasattr(action, 'payload') and action.payload:
                            payload_str = str(action.payload).lower()
                            if filter_lower in payload_str:
                                match_found = True

                        # Skip if no match
                        if not match_found:
                            continue

                    print(f"[{timestamp}] {player_name}: {action_type}")

                    # Show payload details
                    if hasattr(action, 'payload') and action.payload:
                        for key, value in action.payload.items():
                            if key not in ['sequence', 'object_ids']:  # Skip technical fields
                                print(f"              {key}: {value}")

                    # Show position if available
                    if hasattr(action, 'position') and action.position:
                        print(f"              Position: {action.position}")

                    action_count += 1

                    # Check if we've reached max_actions for displayed items
                    if max_actions and action_count >= max_actions:
                        break

                except Exception as e:
                    # Skip errors and continue
                    if action_count < 10:
                        print(f"Error processing action {action_count}: {e}")
                    continue

            if max_actions and len(match.actions) > max_actions:
                print(f"\n... ({len(match.actions) - max_actions} more actions not shown)")

            print(f"\nTotal actions displayed: {action_count}")

    except Exception as e:
        print(f"ERROR: Failed to parse detailed actions: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()


def analyze_record(file_path):
    """Analyze an AoE2 record file and display relevant information."""

    print("=" * 80)
    print("AoE2 RECORD ANALYZER")
    print("=" * 80)
    print(f"\nFile: {file_path}\n")

    try:
        # Parse the record file
        with open(file_path, 'rb') as f:
            summary = mgz.summary.Summary(f)

            # Extract match metadata
            print("=" * 80)
            print("MATCH METADATA")
            print("=" * 80)

            # Get basic match info
            if hasattr(summary, 'get_version'):
                version = summary.get_version()
                print(f"Game Version:     {version}")

            if hasattr(summary, 'get_map'):
                map_info = summary.get_map()
                if map_info:
                    print(f"Map:              {map_info.get('name', 'Unknown')}")
                    print(f"Map Size:         {map_info.get('size', 'Unknown')}")

            if hasattr(summary, 'get_settings'):
                settings = summary.get_settings()
                if settings:
                    print(f"Game Type:        {settings.get('type', 'Unknown')}")
                    print(f"Game Speed:       {settings.get('speed', 'Unknown')}")
                    print(f"Victory Type:     {settings.get('victory_condition', 'Unknown')}")

                    # Population limit
                    if 'pop_limit' in settings:
                        print(f"Population Limit: {settings.get('pop_limit')}")

            if hasattr(summary, 'get_duration'):
                duration = summary.get_duration()
                if duration:
                    print(f"Match Duration:   {format_duration(duration)}")

            if hasattr(summary, 'get_completed'):
                timestamp = summary.get_completed()
                if timestamp:
                    print(f"Date Played:      {timestamp}")

            # Extract player information
            print("\n" + "=" * 80)
            print("PLAYERS")
            print("=" * 80)

            players = []
            if hasattr(summary, 'get_players'):
                players = summary.get_players()

            if players:
                for i, player in enumerate(players, 1):
                    print(f"\nPlayer {i}:")
                    print(f"  Name:           {player.get('name', 'Unknown')}")
                    print(f"  Civilization:   {player.get('civilization', 'Unknown')}")
                    print(f"  Color:          {player.get('color_id', 'Unknown')}")
                    print(f"  Team:           {player.get('team_id', 'N/A')}")

                    if 'winner' in player:
                        status = "Winner" if player['winner'] else "Defeated"
                        print(f"  Status:         {status}")

                    # Player scores
                    if 'score' in player and player['score'] is not None:
                        score_data = player['score']
                        print(f"  Total Score:    {score_data.get('total_score', 'N/A')}")
                        print(f"  Military Score: {score_data.get('military_score', 'N/A')}")
                        print(f"  Economy Score:  {score_data.get('economy_score', 'N/A')}")
                        print(f"  Technology Score: {score_data.get('technology_score', 'N/A')}")
                        print(f"  Society Score:  {score_data.get('society_score', 'N/A')}")
            else:
                print("\nNo player data available.")

            # Match outcome
            print("\n" + "=" * 80)
            print("MATCH OUTCOME")
            print("=" * 80)

            if hasattr(summary, 'get_winner'):
                winner = summary.get_winner()
                if winner:
                    print(f"Winner:           {winner}")

            # Try to get victory condition
            if hasattr(summary, 'get_settings'):
                settings = summary.get_settings()
                if settings and 'victory_condition' in settings:
                    print(f"Victory Condition: {settings['victory_condition']}")

            # Additional statistics if available
            if hasattr(summary, 'get_teams'):
                teams = summary.get_teams()
                if teams:
                    print(f"\nTeams:            {teams}")

            print("\n" + "=" * 80)
            print("ANALYSIS COMPLETE")
            print("=" * 80)

    except FileNotFoundError:
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)
    except PermissionError:
        print(f"ERROR: Permission denied: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to parse record file: {e}")
        print(f"Error type: {type(e).__name__}")
        sys.exit(1)


def main():
    """Main entry point."""

    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Analyze Age of Empires 2 recorded game files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python aoe2_analyzer.py game.aoe2record
  python aoe2_analyzer.py game.aoe2record --detailed
  python aoe2_analyzer.py game.aoe2record --detailed --max-actions 1000
        """
    )

    parser.add_argument('file', help='Path to .aoe2record or .mgz file')
    parser.add_argument('--detailed', '-d', action='store_true',
                        help='Show detailed action-by-action analysis')
    parser.add_argument('--max-actions', '-m', type=int, default=None,
                        help='Maximum number of actions to display (default: all)')
    parser.add_argument('--filter', '-f', type=str, default=None,
                        help='Filter actions (e.g., "villager", "build", "research")')
    parser.add_argument('--villager-production', '-v', action='store_true',
                        help='Show villager production table by minute')
    parser.add_argument('--strategy', '-s', action='store_true',
                        help='Analyze opening strategy for each player')

    args = parser.parse_args()

    # Validate file exists
    if not os.path.exists(args.file):
        print(f"ERROR: File does not exist: {args.file}")
        sys.exit(1)

    # Validate file extension
    if not (args.file.endswith('.aoe2record') or args.file.endswith('.mgz')):
        print("WARNING: File does not have .aoe2record or .mgz extension.")
        print("Attempting to parse anyway...\n")

    # Analyze the record (summary)
    analyze_record(args.file)

    # If villager production analysis requested, run it
    if args.villager_production:
        analyze_villager_production(args.file)

    # If strategy analysis requested, run it
    if args.strategy:
        analyze_strategy(args.file)

    # If detailed analysis requested, run it
    if args.detailed:
        analyze_detailed_actions(args.file, args.max_actions, args.filter)


if __name__ == "__main__":
    main()
