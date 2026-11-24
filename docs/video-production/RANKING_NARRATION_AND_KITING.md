# Ranking videos: narration and kiting decisions

Owner decisions for the Donut ranking videos (fast ranged units vs 15 Franks Knights in Castle Age, vs 15 Spanish Paladins in Imperial Age). Recorded 2026-11-24.

## 1. Narration voice — decided

| Setting | Decision |
| --- | --- |
| Engine | Chatterbox (`chatterbox-tts` 0.1.7), run by [`tts_local.py`](../../apps/video/tts_local.py) in its own venv (`data/local/tts/cb/.venv`) |
| Voice | Cloned from a Kokoro `zf_xiaoxiao` clip (English G2P, `lang_code='a'`), kept locally at `data/local/tts/voices/xiaoxiao-ref.wav` |
| Base emotion | `exaggeration=1.0`, `cfg_weight=0.3`. The owner compared 0.8, 1.0 and 1.2 and picked 1.0 |
| CLI | `build_ranking_preview.py --voice "chatterbox:<ref.wav>@1.0,0.3"` |

## 2. Emotion inside a line — decided: chunked markup

Chatterbox has one `exaggeration` value per `generate()` call. It has no emotion tags; the bracket tags in its vocabulary are undocumented. Punctuation works only in part:

- `punc_norm` turns `...`, `…`, `:` and `;` into commas, so they do nothing for emotion.
- `!`, `?` and `,` reach the model.

To change emotion within a line, split it at a clause boundary (comma or full stop) and generate each chunk with its own settings, using the same reference voice and a fixed seed. Join the chunks with a short gap and 15 ms fades. In the A/B the owner approved both chunked variants:

- **"…loses to most cavalry. *But against Paladins, it actually wins?!*"** Neutral first sentence, surprised second sentence: "this is great".
- **"*Forty kills for zero losses!* *Then the Paladins closed in.*"** Excited, then serious: "this is great".

Markup for script writers (to implement):

| Tag | exaggeration | cfg_weight | Use |
| --- | ---: | ---: | --- |
| none | 0.5 | 0.5 | Plain setup sentences |
| `{excited}…{/}` | 0.9 | 0.3 | Big wins, end with `!` |
| `{surprised}…{/}` | 0.9 | 0.3 | Upsets, end with `?!` or `!` |
| `{serious}…{/}` | 0.35 | 0.6 | Turns for the worse, verdicts |

Rules for whoever writes the script, human or LLM:
- Wrap whole clauses of at least four words, never a single word.
- Use at most one tagged chunk per sentence.
- Don't use `...`, `:` or `;` for effect; no all-caps.
- Merge chunks of under about three words into their neighbour, because very short chunks hallucinate.
- Cap exaggeration at 1.0; above about 1.2 it becomes unstable.
- Gaps: 120 ms after a comma inside a sentence, 300 ms between sentences.

Open question: whether untagged lines use 0.5/0.5 (as tested in the A/B) or the base 1.0/0.3. Decide when the scripts are revised.

## 3. Proper-noun pronunciation — decided: phonemes via Kokoro, voice-converted

**Why respellings failed.** Chatterbox has no G2P step. Its tokenizer is a 704-token grapheme BPE with only 265 multi-letter tokens, so a respelling falls apart into letters: `Gbay-toh` becomes `G b ay - to h`, and the hyphens read as pauses. A 183-name reel in hyphenated respellings failed by ear. IPA input is not supported either (see resemble-ai/chatterbox issues #115 and #346).

**Method C, chosen in the A/B** over hyphenated respellings and plain-word respellings:
1. Kokoro, with the English G2P (`KPipeline(lang_code='a')`) and voice `zf_xiaoxiao`, speaks the **whole sentence**. Each dictionary name is written as a misaki phoneme override, `[Gbeto](/ɡbˈAtO/)`. Misaki uses its own symbols: `A`=eɪ, `I`=aɪ, `O`=oʊ, `W`=aʊ, `Y`=ɔɪ, plus `ʤ ʧ ɹ ɡ`, with stress marks `ˈ ˌ`. The US vocabulary has no `x`; use `k`.
2. `ChatterboxVC.generate(wav, target_voice_path=<ref.wav>)` re-voices that sentence onto the same reference, using the S3Gen decoder the TTS uses, so the timbre matches.
3. Only sentences that contain a dictionary name go through this path. The cost is Kokoro's flatter rhythm on those lines. Avoid putting a name inside an emotion-tagged chunk.

The name list `apps/video/pronunciations.json` needs a phoneme field for each term to replace the respelling (`say`). The 11 tested phoneme strings, used in the A/B:

| Term | Phonemes |
| --- | --- |
| Gbeto | `ɡbˈAtO` |
| Kshatriya | `kʃˈɑtɹijə` |
| Xianbei | `ʃjˈɛnbA` |
| Szlachta | `ʃlˈɑktə` |
| Mangudai | `mˈɑŋɡudˌI` |
| Chu Ko Nu | `ʧˈu kˈO nˈu` |
| Leitis | `lˈItɪs` |
| Druzhina | `dɹuʒˈinə` |
| Shatagni | `ʃətˈɑɡni` |
| Ratha | `ɹˈɑtə` |
| Khmer | `kəmˈɛɹ` |

## 4. Donut AI kiting — decided

`ddkDonutQuietAI` behaviour, tuned with the patches in [`donut_ai_timing.py`](../../apps/video/donut_ai_timing.py) and applied by `prepare_donut_ai_timing.py`. Each patch needs a fresh `--name`, because the game caches AI parses by file name.

- **Retreat length: unchanged.** The 2 s and 3 s minimum retreats (`--min-retreat-ms`) were tried on the Magyar HCA, a single run each. The owner judged the current timing solid.
- **Volley cap: use it for the Mongol HCA (Imperial) and the Castle Age Mongol Cavalry Archer** (`--cap-volley`). Today's 3 s volley timeout let these units fire twice before kiting (31–36% short shot gaps). Capping the volley at reload − 100 ms removed this (0% short gaps). Over 4 runs the Mongol HCA went from −53.2 to −48.1 ranged HP margin.
- **Standing to fire longer: rejected.** Holding the volley for 2–3 shots (`--hold-volley-ms`), or firing until the knights are within 3 tiles (`--threat-gate`), was worse for every unit tested, over 4 runs per setting:

  | Unit | Today | Hold 2 shots | Hold 3 shots | Fire until 3 tiles |
  | --- | ---: | ---: | ---: | ---: |
  | Mongol HCA | −53.2 | −53.3 | −53.8 | −64.5 |
  | Magyar HCA | −12.8 | −57.2 | −47.8 | −54.3 |

  Camel Archer and Kipchak tests agreed: today's quick kiting is best.
- **Mangudai: no change.** Its alternating shot gaps persist under every cap. They are its natural reload cadence, not a double fire.

Whether the shown runs for the Mongol units switch to volley-capped recordings is still the owner's call.

## 5. Next steps

1. Add misaki phonemes to `pronunciations.json` for all 183 terms, and route name-bearing sentences through Kokoro + `ChatterboxVC` in `tts_local.py`.
2. Implement the `{tag}…{/}` chunk markup in `tts_local.py`, and tag the Imperial and Castle scripts.
3. Re-voice and re-render the Imperial video, then render the Castle video.
