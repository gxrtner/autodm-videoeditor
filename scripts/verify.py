#!/usr/bin/env python3
"""Verify a cut. Two checks:
  1. WAVEFORM  — leading dead air + inter-sentence gaps.
  2. CONTENT   — re-transcribe the OUTPUT and flag any repeated word/phrase at a
                 splice (the #1 way multi-take assembly goes wrong: a window's
                 onset/offset bleeds across a take boundary, or two takes of the
                 same line both get included -> "how how", "you're not lazy you're
                 not lazy", "it's on June 23. it's on June 23"). See SKILL lesson 7.

Usage:  python3 verify.py OUTPUT.mp4 [thr=0.005]
Exit code is NONZERO if a duplicate phrase is detected — so batch loops can gate
on it. Run from /tmp to avoid a local inspect.py shadowing the stdlib (lesson 6).

A cut is NOT done until this reports `CONTENT: clean`.
"""
import sys, subprocess, wave, os, re
import numpy as np

mp4 = sys.argv[1]
THR = float(sys.argv[2]) if len(sys.argv) > 2 else 0.005
wav = "/tmp/_vc_verify.wav"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)

# ---------- 1. waveform: dead air + gaps ----------
w = wave.open(wav, "rb"); sr = w.getframerate()
a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
win = int(0.02 * sr); hop = 0.004
def rms(t):
    i = int(t * sr); s = a[max(0, i - win // 2): i + win // 2]
    return float(np.sqrt(np.mean(s ** 2))) if len(s) else 0.0

T = len(a) / sr
t = 0.0
while rms(t) < THR and t < 2: t += hop
print(f"Duration: {T:.2f}s")
print(f"Leading dead air: {t*1000:.0f} ms   (target <50ms)")
gaps, sil, g0 = [], True, 0.0
for tt in np.arange(0, T, hop):
    q = rms(tt) < THR
    if q and not sil: g0 = tt; sil = True
    if (not q) and sil:
        if tt - g0 > 0.12: gaps.append((round(g0, 2), round((tt - g0) * 1000)))
        sil = False
print("Pauses >120ms (time : length):")
for at, ms in gaps: print(f"  {at:6.2f}s : {ms} ms")

# ---------- 2. content: repeated word/phrase detector ----------
# Words that are LEGITIMATELY said twice back-to-back in a script live here.
# AUTODM 31.07.2026: deutsche Verstaerker ergaenzt. Die Liste war rein
# englisch, dadurch meldete der Verify Julians "super, super wichtig"
# faelschlich als doppelten Take und blockierte einen sauberen Schnitt.
ALLOWED_UNIGRAM_REPEATS = {
    "more", "no", "so", "very", "really",
    "super", "sehr", "ganz", "viel", "voll", "richtig", "total",
    "ja", "nein", "immer", "nie", "echt", "extrem", "mega", "krass",
}
def norm(x): return re.sub(r"[^a-z0-9]", "", x.lower())

def find_repeats(tokens):
    """Return the longest adjacent repeated n-grams (n high->low), deduped."""
    hits = []
    for n in range(6, 0, -1):
        for i in range(len(tokens) - 2 * n + 1):
            a_ = tokens[i:i + n]; b_ = tokens[i + n:i + 2 * n]
            if a_ == b_:
                if n == 1 and a_[0] in ALLOWED_UNIGRAM_REPEATS:
                    continue
                hits.append(" ".join(a_))
    hits = sorted(set(hits), key=len, reverse=True)
    return [h for h in hits if not any(h != g and h in g for g in hits)]

content_status = "skipped (faster-whisper not installed)"
dup = []
try:
    from faster_whisper import WhisperModel
    # small.en (not base/tiny): accurate enough to (a) reliably hear numbers/dates/
    # prices — a key payload word the model DROPS is a tell the audio is mushy/clipped
    # — and (b) surface aborted-retake fragments a take trailed into (e.g. "June twen—"
    # before an appended clean "June 23"). base.en misses both. See SKILL lesson 7.
    # --- Integritaets-Check ZUERST ---
    # Eine beschaedigte Datei (z.B. wenn zwei Renders gleichzeitig auf denselben
    # Namen schreiben) laesst whisper halluzinieren ("Untertitel im Auftrag des
    # ZDF...") - der Inhalts-Check meldet dann faelschlich "clean". Deshalb erst
    # dekodieren und auf Fehler pruefen.
    import subprocess
    _p = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-f", "null", "-"],
                        capture_output=True, text=True)
    if _p.stderr.strip():
        print("!! DATEI DEFEKT - Dekodier-Fehler:")
        print("\n".join(_p.stderr.strip().splitlines()[:5]))
        print("   Neu rendern (nie zwei Renders gleichzeitig auf dieselbe Datei).")
        sys.exit(1)

    import os
    _lang = os.environ.get("VERIFY_LANG", "de")
    _model = "small" if _lang != "en" else "small.en"
    model = WhisperModel(_model, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(wav, vad_filter=False, language=_lang, task="transcribe")
    text = " ".join(s.text.strip() for s in segs)
    toks = [norm(x) for x in text.split() if norm(x)]
    dup = find_repeats(toks)
    content_status = "clean" if not dup else "DUPLICATE PHRASE(S): " + " | ".join(dup)
    print(f"\nTranscript: {text}")
except ImportError:
    pass

print(f"\nCONTENT: {content_status}")
os.remove(wav)
if dup:
    print("!! FAIL — re-pick the take for the duplicated line (use ONE continuous take that\n"
          "   already contains both beats; don't stitch two takes of the same words).")
    sys.exit(1)
