"""Summarize player-3 melee activation orders in decoded Hand Cannoneer tapes."""

import glob
import json
import os
import sys

from read_ai_orders import orders


def summarize(path):
    records, _ = orders(path)
    attack = [record for record in records
              if record["playerId"] == 3 and record["orderType"] == 700]
    first_by_recipient = {}
    for record in attack:
        first_by_recipient.setdefault(record["recipient"], record["t"])
    first_times = sorted(first_by_recipient.values())
    return {
        "tag": os.path.basename(path).removesuffix(".frames.bin"),
        "orders": len(attack),
        "unique_recipients": len(first_times),
        "first_activation_ms": first_times,
    }


def main():
    root = sys.argv[1]
    paths = sorted(glob.glob(os.path.join(root, "*.frames.bin")))
    rows = [summarize(path) for path in paths]
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
