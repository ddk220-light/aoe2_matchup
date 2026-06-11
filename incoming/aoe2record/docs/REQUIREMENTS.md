# AoE2 Record Analyzer - Requirements

## Overview
A Python program to read and analyze Age of Empires 2 recorded game files (.aoe2record) using the mgz library, providing insights into match performance and statistics.

## Technical Requirements

### Dependencies
- Python 3.8+
- mgz library (for parsing .aoe2record files)

### Installation
```bash
pip install mgz
```

## Initial Scope (v0.1)

### Core Functionality
The program should read an AoE2 record file from a specified path and output the most relevant match information.

### Input
- File path to .aoe2record file (command-line argument or hardcoded path)

### Output Information

#### Match Metadata
- Game version
- Map name
- Game type (e.g., Random Map, Death Match)
- Match duration
- Date/time played
- Game speed

#### Player Information
- Player names
- Civilizations chosen
- Team assignments
- Player colors
- Victory/defeat status
- Final scores

#### Basic Statistics (per player)
- Military score
- Economy score
- Technology score
- Society score
- Total score

#### Match Outcome
- Winner(s)
- Victory condition achieved (Conquest, Wonder, etc.)

### Output Format
- Clean, readable text output to console
- Structured format (e.g., sections for metadata, players, statistics)

## Future Enhancements (Post v0.1)

### Advanced Analysis
- Resource collection rates over timez
- Military unit production analysis
- Technology research timeline
- Map control/expansion patterns
- APM (Actions Per Minute) tracking
- Combat efficiency metrics
- Idle time analysis

### Visualization
- No visualization for now.

### Export Options
- Show the output in a json format.

### Comparison Features
- None for now

## Success Criteria (v0.1)
- Successfully parses any valid .aoe2record file
- Displays all relevant match information clearly
- Handles errors gracefully (invalid files, missing data)
- Easy to run from command line

## Usage Example
```bash
python aoe2_analyzer.py <path_to_record_file>
```

## Error Handling
- Validate file exists
- Verify file format is valid
- Handle corrupted or incomplete recordings
- Provide meaningful error messages
