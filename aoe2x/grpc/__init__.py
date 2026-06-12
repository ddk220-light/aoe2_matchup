"""Live-game gRPC capture/decode (layer 2) — the CadeRemote spectator API.

The scripts here are designed to run AS SCRIPTS (subprocess from the video
pipeline, or directly for lab capture) with a python that has grpcio +
protobuf; they self-insert their own directory on sys.path for the
cade_api_pb2* stubs.

- grpc_hp_log.py    stream recorder: dumps raw Frames() to <prefix>.frames.bin
                    + live fight-end tailer (writes <prefix>.END)
- decode_state_v2.py  flat-document state decoder (entity-band seeding,
                    delta patches, re-anchor desync recovery)
- redecode_hp.py    offline: .frames.bin -> exact per-frame HP/unit timeline
- cade_api.proto / cade_api_pb2*.py  schema + generated stubs

mTLS client credentials (cade-client.key/.pem, certificate-authority.pem)
must sit BESIDE these scripts and are gitignored — see README.md.

This package is the single canonical copy (2026-06-11): it absorbed the
strictly-improved scenario_builder/grpc fork (relative paths, HP>0 filter,
entity-band density check, 200KB-skip scan fix); the older copies in lab/
were deleted. lab/'s frozen `_*.py` one-off diagnostics may still reference
the old locations — see lab/README.md.
"""
