#!/bin/bash
# Compile the ScreenCaptureKit recorder. Run once, and again after editing the .swift.
# Produces ./sck_record (gitignored — it's a platform-specific binary; build locally).
set -euo pipefail
cd "$(dirname "$0")"
swiftc -O sck_record.swift -o sck_record
echo "built: $(pwd)/sck_record"
