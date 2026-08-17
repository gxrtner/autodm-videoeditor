#!/usr/bin/env python3
"""Waveform-basierte Sprech-Segmentierung + Take-Auswahl.

WARUM: Whisper-Wort-Timestamps sind bei Wiederholungen unbrauchbar - whisper
transkribiert Retakes oft gar nicht und streckt stattdessen einzelne Woerter
ueber die Pause (Beispiel: "Levels" = 4.5s). Wer darauf schneidet, behaelt
Pausen und Fehlstarts.

STATTDESSEN: Die Wellenform sagt die Wahrheit ueber Sprache/Stille. Wir finden
echte Sprech-Segmente, transkribieren JEDES einzeln (kurze Clips = zuverlaessig),
gruppieren Wiederholungen und behalten pro Zeile den LETZTEN vollstaendigen Take.

Usage:
  python3 segment.py audio16k.wav [--gap 0.35] [--thr 0.005] [--min 0.35]
Schreibt segments_wave.json (alle Segmente mit Text) - danach pick_takes.py.
"""
import sys, json, wave, argparse
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("wav", nargs="?", default="audio16k.wav")
ap.add_argument("--gap", type=float, default=0.35, help="Stille in s -> neues Segment")
ap.add_argument("--thr", type=float, default=0.005, help="RMS-Schwelle Sprache vs. Atem")
ap.add_argument("--hyst", type=float, default=0.40,
                help="Ausstiegsschwelle als Anteil von --thr (Hysterese)")
ap.add_argument("--min", type=float, default=0.30, help="kuerzere Segmente verwerfen")
ap.add_argument("--lang", default="de")
ap.add_argument("--model", default="medium")
a = ap.parse_args()

# --- Audio laden ---
w = wave.open(a.wav, "rb")
sr = w.getframerate()
n = w.getnframes()
audio = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
w.close()

# --- RMS pro 10ms-Frame ---
hop = int(sr * 0.01)
frames = len(audio) // hop
rms = np.array([np.sqrt(np.mean(audio[i*hop:(i+1)*hop] ** 2)) for i in range(frames)])

# --- Segmente: zusammenhaengende Sprache, getrennt durch Stille >= gap ---
#
# HYSTERESE (06.08.2026): Mit EINER Schwelle wurden Satzenden abgeschnitten.
# Julians Stimme faellt zum Satzende hin ab ("...die Ziele deiner Traumfollower"),
# rutscht unter thr und das Segment endete mitten im letzten Wort. Fuer
# pick_takes.py sah der GUTE Take dadurch abgebrochen aus und verlor gegen
# einen frueheren Fehlstart. Deshalb: einsteigen bei thr, aussteigen erst bei
# thr*hyst. Klassisches VAD-Muster.
thr_in, thr_out = a.thr, a.thr * a.hyst
gap_frames = int(a.gap / 0.01)
segs, start, silence = [], None, 0
for i in range(frames):
    if start is None:
        if rms[i] > thr_in:
            start, silence = i, 0
        continue
    if rms[i] > thr_out:
        silence = 0
        continue
    silence += 1
    if silence >= gap_frames:
        end = i - silence + 1
        if (end - start) * 0.01 >= a.min:
            segs.append((start * 0.01, end * 0.01))
        start, silence = None, 0
if start is not None:
    end = frames - silence if silence else frames
    if (end - start) * 0.01 >= a.min:
        segs.append((start * 0.01, end * 0.01))

print(f"{len(segs)} Sprech-Segmente gefunden "
      f"(gap={a.gap}s, thr={a.thr}, aus bei {thr_out:.4f})", flush=True)

# --- Jedes Segment einzeln transkribieren ---
#
# MODELLWAHL (06.08.2026): Vorher faster_whisper "medium" auf CPU. Bei den
# 1-2s kurzen Einzelclips lieferte das grob falsche Texte ("Roemmicht auf arme
# Menschen" statt "Hoer nicht auf arme Menschen") — und mit falschen Texten
# kann pick_takes.py Wiederholungen nicht erkennen, der Schnitt wird Muell.
# Gegenprobe: DERSELBE Ton am Stueck mit large-v3-turbo war fehlerfrei, es lag
# also am Modell, nicht an der Aufnahme. mlx-whisper laeuft zudem auf der GPU
# und cached das Modell prozessweit, die vielen Einzelaufrufe kosten also nichts.
try:
    import mlx_whisper
    REPO = "mlx-community/whisper-large-v3-turbo"

    def transkribiere(clip):
        return mlx_whisper.transcribe(clip, path_or_hf_repo=REPO,
                                      language=a.lang, fp16=True)["text"].strip()
    print(f"Transkription: mlx-whisper large-v3-turbo", flush=True)
except ImportError:
    from faster_whisper import WhisperModel
    _m = WhisperModel(a.model, device="cpu", compute_type="int8")

    def transkribiere(clip):
        parts, _ = _m.transcribe(clip, language=a.lang, task="transcribe",
                                 vad_filter=False, beam_size=5)
        return " ".join(p.text.strip() for p in parts).strip()
    print(f"Transkription: faster-whisper {a.model} (mlx nicht verfuegbar)", flush=True)

out = []
for i, (s, e) in enumerate(segs):
    clip = audio[int(s * sr):int(e * sr)]
    text = transkribiere(clip)
    out.append({"i": i, "start": round(s, 3), "end": round(e, 3),
                "dur": round(e - s, 2), "text": text})
    print(f"  {i:3d}  {s:7.2f}-{e:7.2f} ({e-s:5.2f}s)  {text[:70]}", flush=True)

json.dump(out, open("segments_wave.json", "w"), ensure_ascii=False, indent=1)
total = sum(x["dur"] for x in out)
print(f"\nDONE: {len(out)} Segmente, {total:.1f}s Sprache -> segments_wave.json")
