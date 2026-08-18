#!/usr/bin/env python3
"""Word-level millisecond transcription via faster-whisper.
Usage: python3 transcribe.py audio16k.wav [model] [language]
Writes words.json (every word + start/end) and segments.json (whisper segments).
NOTE: whisper timestamps are NOT cut-accurate (drift up to ~0.7s). Use them for
TEXT and rough take location only; detect real cut points from the waveform (cut.py).

Language defaults to "de" (Julian speaks German). Pass "en" as 3rd arg for English,
or "auto" to let whisper detect. Never leave this on the wrong language - whisper
silently TRANSLATES instead of transcribing, which breaks take matching."""
import sys, json
from faster_whisper import WhisperModel

wav = sys.argv[1] if len(sys.argv) > 1 else "audio16k.wav"
model_name = sys.argv[2] if len(sys.argv) > 2 else "medium"
lang = sys.argv[3] if len(sys.argv) > 3 else "de"
if lang == "auto":
    lang = None

model = WhisperModel(model_name, device="cpu", compute_type="int8")
segments, info = model.transcribe(
    wav, word_timestamps=True, vad_filter=False, beam_size=5, language=lang,
    task="transcribe",
)

words, segs = [], []
for seg in segments:
    segs.append({"start": round(seg.start, 3), "end": round(seg.end, 3), "text": seg.text.strip()})
    for w in (seg.words or []):
        words.append({"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word})
    print(f"[{seg.start:7.3f} -> {seg.end:7.3f}] {seg.text.strip()}", flush=True)

json.dump(words, open("words.json", "w"), indent=0)
json.dump(segs, open("segments.json", "w"), indent=2)
print(f"\nDONE: {len(words)} words, {len(segs)} segments -> words.json / segments.json")
