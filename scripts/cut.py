#!/usr/bin/env python3
"""Waveform-accurate multi-take cut + render.

Given keeper-take windows, detects the TRUE speech onset/offset of each take from
the audio waveform (NOT whisper timestamps), then renders a tight, click-free cut.

Encodes the video-cut lessons:
  - whisper timestamps drift ~0.7s -> detect cut points from the waveform
  - fixed energy threshold (~0.005) sits between breath (~0.0015) and word (~0.02+)
  - scan INWARD (forward for onset, backward for offset) so dramatic internal
    pauses never split or clip a line
  - micro audio fades (~14ms) => no clicks, hard video cuts stay snappy

Usage:
  python3 cut.py --input IN.mp4 --audio audio16k.wav --words words.json \
     --keepers keepers.json --out OUT.mp4 [--head 0.03] [--tail 0.07] \
     [--thr 0.005] [--max-internal-pause 0] [--crf 18]

keepers.json: [{"a":46.0,"b":50.3,"label":"L1 ..."}, ...]  (rough windows in seconds)
"""
import argparse, json, wave, subprocess
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--input", required=True)
ap.add_argument("--audio", default="audio16k.wav")
ap.add_argument("--words", default="words.json")
ap.add_argument("--keepers", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--head", type=float, default=0.03)
ap.add_argument("--tail", type=float, default=0.07)
ap.add_argument("--end-tail", type=float, default=0.0,
                help="extra hold on the FINAL segment only — let the last line breathe / land "
                     "the ending (extends into the real trailing silence, stops before any "
                     "resumed speech so it can't grab the next take). 0 = same as --tail.")
ap.add_argument("--thr", type=float, default=0.005, help="energy threshold (breath<thr<word)")
ap.add_argument("--margin", type=float, default=0.35, help="search margin around word edge (s)")
ap.add_argument("--max-internal-pause", type=float, default=0.0,
                help="if >0, clamp every internal silence inside a take to this max (s)")
ap.add_argument("--fade", type=float, default=0.014, help="micro audio fade per edge (s)")
ap.add_argument("--crf", type=int, default=18)
ap.add_argument("--preset", default="medium")
a = ap.parse_args()

words = json.load(open(a.words))
keepers = json.load(open(a.keepers))

w = wave.open(a.audio, "rb"); sr = w.getframerate()
sig = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
hop = 0.004; win = int(0.020 * sr); SUS = 0.04; THR = a.thr

def rms(t):
    i = int(t * sr); s = sig[max(0, i - win // 2): i + win // 2]
    return float(np.sqrt(np.mean(s ** 2))) if len(s) else 0.0

def sustained(t, d=SUS):
    tt = t
    while tt < t + d:
        if rms(tt) < THR: return False
        tt += hop
    return True

def onset(fw):                         # forward scan from before first word
    t = fw - a.margin
    while t < fw + 1.0:
        if rms(t) >= THR and sustained(t): return round(t, 3)
        t += hop
    return round(fw, 3)

def offset(lw):                        # backward scan from after last word
    t = lw + a.margin
    while t > lw - 1.0:
        if rms(t) >= THR and sustained(t - SUS): return round(t, 3)
        t -= hop
    return round(lw, 3)

def words_in(a0, b0):
    return [x for x in words if a0 <= (x["start"] + x["end"]) / 2 <= b0]

# ---- detect true edges ----
segs = []
for k in keepers:
    ws = words_in(k["a"], k["b"])
    if not ws:
        print(f'!! no words in window {k["a"]}-{k["b"]} ({k.get("label","")}) — check keepers'); continue
    on, off = onset(ws[0]["start"]), offset(ws[-1]["end"])
    txt = "".join(x["word"] for x in ws).strip()
    segs.append({"label": k.get("label", ""), "on": on, "off": off, "text": txt})
    print(f'{k.get("label",""):28s} {on:8.3f}-{off:8.3f} ({off-on:5.2f}s)  "{txt[:46]}"')

# ---- overlap guard (lesson 7) ----
# If any two kept segments cover overlapping SOURCE time, the same audio plays
# twice -> a duplicated word/phrase. Warn loudly; the fix is to MERGE the two
# windows into one continuous take, or move one window off the shared boundary.
for i in range(len(segs)):
    for j in range(i + 1, len(segs)):
        lo, hi = max(segs[i]["on"], segs[j]["on"]), min(segs[i]["off"], segs[j]["off"])
        if hi - lo > 0.05:
            print(f'!! OVERLAP: "{segs[i]["label"]}" [{segs[i]["on"]:.2f}-{segs[i]["off"]:.2f}] '
                  f'& "{segs[j]["label"]}" [{segs[j]["on"]:.2f}-{segs[j]["off"]:.2f}] share '
                  f'{hi-lo:.2f}s of source -> WILL DUPLICATE AUDIO. Merge these into one window.')

# ---- build ffmpeg filtergraph ----
def trims_for(st, en):
    """Return list of (start,end) keep-windows. Splits on long internal pauses if requested."""
    if a.max_internal_pause <= 0:
        return [(st, en)]
    keeps, t, run0 = [], st, None
    seg_start = st
    while t < en:
        quiet = rms(t) < THR
        if quiet and run0 is None: run0 = t
        if (not quiet) and run0 is not None:
            if t - run0 > a.max_internal_pause:                 # long pause -> clamp
                keeps.append((seg_start, run0 + a.max_internal_pause))
                seg_start = t
            run0 = None
        t += hop
    keeps.append((seg_start, en))
    return keeps

def end_with_hold(off):
    """Final segment: let the last line breathe. Extend past the word into the real
    trailing silence up to --end-tail, but stop just before any resumed/sustained
    speech so we never grab the next take."""
    base = off + a.tail
    if a.end_tail <= a.tail:
        return round(base, 3)
    t, limit = base, off + a.end_tail
    while t < limit:
        if rms(t) >= THR and sustained(t):
            return round(max(base, t - 0.06), 3)     # speech resumed -> stop before it
        t += hop
    return round(limit, 3)

parts, vlabels, alabels, idx, total = [], [], [], 0, 0.0
last_i = len(segs) - 1
for si, s in enumerate(segs):
    st = round(s["on"] - a.head, 3)
    en = end_with_hold(s["off"]) if si == last_i else round(s["off"] + a.tail, 3)
    for (cs, ce) in trims_for(st, en):
        d = ce - cs; total += d
        parts.append(
            f'[0:v]trim=start={cs:.3f}:end={ce:.3f},setpts=PTS-STARTPTS[v{idx}];'
            f'[0:a]atrim=start={cs:.3f}:end={ce:.3f},asetpts=PTS-STARTPTS,'
            f'afade=t=in:st=0:d={a.fade},afade=t=out:st={max(0,d-a.fade):.3f}:d={a.fade}[a{idx}]')
        vlabels.append(f'[v{idx}]'); alabels.append(f'[a{idx}]'); idx += 1

concat = "".join(v + al for v, al in zip(vlabels, alabels)) + f'concat=n={idx}:v=1:a=1[vout][aout]'
fc = ";".join(parts) + ";" + concat
open("_filter.txt", "w").write(fc)

cmd = ["ffmpeg", "-y", "-i", a.input, "-filter_complex_script", "_filter.txt",
       "-map", "[vout]", "-map", "[aout]",
       "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf), "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out]
print(f"\n~{total:.1f}s across {idx} segments -> rendering {a.out} ...")
r = subprocess.run(cmd, capture_output=True, text=True)
print("RC", r.returncode, "OK" if r.returncode == 0 else r.stderr[-1200:])
