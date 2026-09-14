# Current: authorized Wei voice clone

The user confirmed permission to clone the narrator. ElevenLabs Instant Voice Cloning created voice MlW5cFazoi1gP2ifK2iW from the extracted 78-second PLAY_WEI1S1 recording; requires_verification=false. The original reference is English DLC7.pck media 513736269. This is actual sample-based cloning, replacing the previous library similarity match. Voice metadata is in wei-voice-clone.json; no credential is stored there.

Current output: intro-v4/tiger-cavalry-intro.mp4, with two untitled pages, speech-aligned letters, and quiet Chinese civilization music. The audio is newly synthesized, not original recorded game dialogue. Per-page audio, exact provider alignments, script, provenance, and validation are retained alongside the video. The 59-match description has new chapter offsets for this intro; the compilation itself is still separate.

Reproduction (ELEVENLABS_API_KEY in process environment; PYTHONPATH=apps/video;.; installed FFmpeg accessible):

- create_intro_voice_clone.py (reuses matching saved clone metadata)
- generate_intro_narration.py --voice-id MlW5cFazoi1gP2ifK2iW --voice-kind instant_clone --output aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/intro-v4
- build_campaign_intro.py --plan apps/video/intro/tiger-cavalry-cloned.json --output aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/intro-v4

## Previous versions and research

# Narration implemented — 2026-09-08

Current output: intro-v3/tiger-cavalry-intro.mp4 (32.633 seconds). Licensed ElevenLabs voice Prayan (SQZnH90qSS0OjsqLasTa), the first-ranked similar-voices result using the approved 20-second Wei sample. This is a sample-guided library voice approximation, not a clone or a verified perceptual identity match. Speech uses multilingual v2, speed 0.90, stability 0.65. Raw character alignment drives the letter reveal, with 0.4 seconds lead and 2 seconds final hold per page. Voice target is -17 LUFS and music -31 LUFS before mixing/fades. Provider audio, alignment, script and selection provenance are retained in intro-v3. No API key is stored in source or outputs.

Both original references were resolved locally: PLAY_WEI1S1 -> action 1023154402 -> sound 607851625 -> media 513736269 in English DLC7.pck (78 seconds); PLAY_CM_01 -> action 721354605 -> sound 734471805 -> media 87003190 in English Base.1.pck (32 seconds). The reusable extract_intro_reference.py supports these direct v154 Wwise events. Wei exists, so it was preferred over the Art of War fallback.

Reproduce narration with ELEVENLABS_API_KEY in the process environment, PYTHONPATH=apps/video;., then run generate_intro_narration.py --voice-id SQZnH90qSS0OjsqLasTa. Identical cached requests are reused. Render with build_campaign_intro.py --plan apps/video/intro/tiger-cavalry-narrated.json --output aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/intro-v3. Both commands need access to installed FFmpeg. The generated plan includes local absolute audio/alignment paths.

An optional upload of generated audio for independent transcription was rejected by automatic approval review. It was not retried. Validation checks audio decoding/levels, video properties, alignment matching the submitted text, and visual frames; it does not establish that proper-name pronunciation or perceptual similarity is exact.

## Earlier options research (superseded by implementation above)

# Narration options â€” checked 2026-09-08

The current video contains music, not generated narration. The exact 485-character spoken copy is saved in intro-v2/narration-script.txt. No transcription is needed to read our own script aloud.

## Installed campaign audio

Campaign JSON contains explicit audio event names and text string IDs. Art of War's first introduction uses PLAY_CM_01 in resources/_common/campaign/cam0.json; its first caption references string 228101. Wei uses PLAY_3K1_INTRO_A, PLAY_3K1_INTRO_B, and PLAY_WEI1S1 in 3kcam2.json. English audio packages are under wwise/en (Base.pck, Base.1.pck and DLC packages).

These are Wwise event identifiers, not WAV filenames. To isolate a specific narrator, follow the event through the sound bank to its media IDs, extract the WEM, decode it, and check whether music is already mixed into the recording. That event-to-media traversal is not implemented in this change. Existing campaign text strings can help transcribe a reference once identified, but require checking against the actual spoken clip.

## API: ElevenLabs (recommended for this short intro)

The official API page currently advertises v3 and Multilingual v2 at $0.10 per 1,000 characters; 485 characters is approximately $0.049 per generation at that advertised rate. The page currently has a promotional pricing banner, so verify checkout terms. Account/plan requirements, minimum funding, taxes and retries can cost more than that marginal generation estimate.

Starter is $6/month and includes Instant Voice Cloning. Its documentation requires permission to clone the voice. Owning the game installation alone does not establish that permission. Use a licensed stock voice or design an original narrator with similar broad delivery unless permission for the actual game actor is obtained.

Suggested original voice direction: mature male historical storyteller, warm low register, measured cadence, restrained gravitas, clear English diction, reflective delivery, gentle pauses between sentences. Avoid exaggerated trailer delivery.

Setup: select/design a voice in ElevenLabs, create a restricted TTS API key, store it locally as ELEVENLABS_API_KEY (never paste it into source), and provide the voice ID. Generate one WAV per page. Use synthesis timestamps or forced alignment for narration-synchronized text, then adjust page holds to the actual speech durations. Mix music beneath speech and fade at the end. This turn did not create an account, buy credits, upload game dialogue, or generate a cloned voice.

Sources:
- https://elevenlabs.io/pricing/api
- https://elevenlabs.io/pricing
- https://help.elevenlabs.io/hc/en-us/articles/13313587528849-What-is-My-Voices

## Local: Qwen3-TTS

The official Qwen3-TTS repository supplies 1.7B and 0.6B Base models for sample-based voice cloning, and a 1.7B VoiceDesign model for original voices described in text. Base takes reference audio plus its transcript; speaker-only mode can omit the transcript with a quality tradeoff. The repository describes a three-second cloning capability; a clean, representative reference still needs auditioning.

The 1.7B model is a reasonable fit to investigate on the user's RTX 5090, but this task did not benchmark that machine. Use an isolated Python environment and a CUDA/PyTorch build compatible with the card; the official quickstart uses GPU inference. There is no per-generation API bill, but model setup, downloads, electricity, and troubleshooting remain. VoiceDesign followed by a reusable generated reference is an option for a consistent original campaign-like narrator.

Source: https://github.com/QwenLM/Qwen3-TTS

## Music already implemented

Extracted media 784299781 from installed wwise/Base.pck and decoded it with official vgmstream r2117. It is 53.718 seconds, stereo 48 kHz Wwise Opus. A community-authored mapping identifies it as the Chinese long civilization theme; this identity is not embedded as a readable filename. It is used as the Chinese fallback to match the Art of War art, not claimed to be the Wei theme or the exact campaign music.

Music is normalized to -25 LUFS before fades, with a 1.5-second fade-in and 3-second fade-out over the 42-second intro. No original actor audio is in the output.

- https://forums.ageofempires.com/t/how-to-use-other-civilization-sound/227552
- https://github.com/vgmstream/vgmstream/releases/tag/r2117
