# aoe2x/grpc — live-game gRPC capture & decode (layer 2)

Connects to AoE2:DE's local CadeRemote spectator API (`ipv6:[::1]:4341`)
to capture the game's real internal state — the ground truth that the
replay classifier (aoe2x/replay) is scored against, and the HP/fight-end
sidecar source for the video pipeline (apps/video).

## Consumers

- **apps/video** — `auto/grpc_capture.py` launches `grpc_hp_log.py` as a
  subprocess during recordings and `redecode_hp.py` offline (paths from
  `auto/config.py`, overridable via `AOE2_GRPC_*` env vars).
- **lab/** — ground-truth capture (`record_games.py`) and the label
  pipeline build on `decode_state_v2.py`.

## Credentials (NEVER commit)

The CadeRemote endpoint requires mTLS. Place beside these scripts
(all `*.key` / `*.pem` here are gitignored):

```
aoe2x/grpc/cade-client.key
aoe2x/grpc/cade-client.pem
aoe2x/grpc/certificate-authority.pem
```

They are extracted from the local game install (see
`docs/aoe2record/docs/` capture notes). If you believe a copy ever
leaked, regenerate/re-extract them — treat them like any private key.

## Patch sensitivity

The proto schema is stable across game patches in practice; the decoder's
entity-band heuristics (`decode_state_v2.py`) are the patch-sensitive part.
After a game patch, re-validate with a fresh capture before trusting labels
(see lab/README.md scoring runbook).
