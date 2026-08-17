#!/usr/bin/env python3
"""Baut words.json aus segments_wave.json.

WARUM: cut.py verankert jedes Keeper-Fenster an Woertern aus words.json und
verwirft das Fenster, wenn dort keins liegt ("no words in window"). Die
Whisper-Wort-Timestamps sind bei Wiederholungen aber unbrauchbar (Woerter
werden ueber Pausen gestreckt) - dann faellt ein korrektes Fenster still raus.

FIX: Wir erzeugen words.json aus den Wellenform-Segmenten. Deren Zeiten stimmen
per Definition, weil sie aus der Energie des Audios kommen. Der Text jedes
Segments wird gleichmaessig ueber seine Dauer verteilt.

Usage: python3 words_from_segments.py   (im Arbeitsordner)
Schreibt words.json (Backup der alten Datei als words_whisper.json).
"""
import json, os

segs = json.load(open("segments_wave.json"))

if os.path.exists("words.json") and not os.path.exists("words_whisper.json"):
    os.rename("words.json", "words_whisper.json")
    print("alte words.json -> words_whisper.json gesichert")

words = []
for s in segs:
    toks = s["text"].split()
    if not toks:
        continue
    dur = (s["end"] - s["start"]) / len(toks)
    for i, t in enumerate(toks):
        words.append({
            "start": round(s["start"] + i * dur, 3),
            "end": round(s["start"] + (i + 1) * dur, 3),
            "word": t,
        })

json.dump(words, open("words.json", "w"), ensure_ascii=False, indent=0)
print(f"{len(words)} Woerter aus {len(segs)} Wellenform-Segmenten -> words.json")
