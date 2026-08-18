#!/usr/bin/env python3
"""
Paart Videos mit den passenden externen Mikro-Aufnahmen in einem Ordner.

Julian filmt Bild (Sony) und Ton (Ansteckmikro) getrennt. Welche Aufnahme zu
welchem Clip gehört, lässt sich NICHT an der Dateidauer ablesen - am
06.08.2026 gehörte die 131,6s-Aufnahme zum 123s-Video und nicht zum
130,6s-Video. Zuverlaessig ist nur der Toninhalt: die Lautstärke-Huellkurven
von Kameraton und Mikro werden kreuzkorreliert, das hoechste Maximum gewinnt.
Richtige Paare erreichen ~0.85, falsche bleiben unter 0.15 - der Abstand ist
so gross, dass die Zuordnung eindeutig ist.

Usage:
  paare_finden.py <ordner> [--json paare.json]
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

VIDEO_ENDUNGEN = {".mp4", ".mov", ".m4v"}
AUDIO_ENDUNGEN = {".m4a", ".wav", ".mp3", ".aac"}
GUETE_MIN = 0.40


def ffmpeg_pfad():
    os.environ["PATH"] = str(Path.home() / "bin") + ":" + os.environ["PATH"]


def huellkurve(pfad, max_sekunden=600):
    """Lautstärke je 10ms, mittelwertfrei und normiert."""
    import numpy as np, wave
    ffmpeg_pfad()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-t", str(max_sekunden),
                        "-i", pfad, "-ac", "1", "-ar", "16000", tmp],
                       capture_output=True)
    if r.returncode != 0 or not os.path.getsize(tmp):
        os.unlink(tmp)
        return None
    w = wave.open(tmp, "rb")
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    w.close(); os.unlink(tmp)
    hop, n = 160, len(a) // 160
    if n < 50:
        return None
    e = np.sqrt(np.array([np.mean(a[i*hop:(i+1)*hop] ** 2) for i in range(n)]))
    e = e - e.mean()
    norm = np.linalg.norm(e)
    return e / norm if norm else None


def versatz(video_env, audio_env):
    """(Versatz in Sekunden, Güte). Positiv = Mikro lief schon, als die
    Kamera startete."""
    import numpy as np
    n = 1 << int(np.ceil(np.log2(len(video_env) + len(audio_env))))
    c = np.fft.irfft(np.fft.rfft(audio_env, n) * np.conj(np.fft.rfft(video_env, n)), n)
    c = np.concatenate([c[-(len(video_env)-1):], c[:len(audio_env)]])
    k = int(np.argmax(c))
    return (k - (len(video_env) - 1)) * 0.01, float(c[k])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ordner")
    ap.add_argument("--json", help="Ergebnis als JSON ablegen")
    a = ap.parse_args()

    ordner = Path(a.ordner).expanduser()
    if not ordner.is_dir():
        sys.exit(f"Kein Ordner: {ordner}")

    videos = sorted(p for p in ordner.rglob("*")
                    if p.suffix.lower() in VIDEO_ENDUNGEN and not p.name.startswith("."))
    audios = sorted(p for p in ordner.rglob("*")
                    if p.suffix.lower() in AUDIO_ENDUNGEN and not p.name.startswith("."))
    if not videos:
        sys.exit(f"Keine Videos in {ordner}")
    print(f"{len(videos)} Videos, {len(audios)} Tonaufnahmen in {ordner.name}")
    if not audios:
        print("Keine externen Aufnahmen - es wird der Kameraton verwendet.")

    ev = {}
    for v in videos:
        e = huellkurve(str(v))
        if e is None:
            print(f"  !! Ton nicht lesbar: {v.name}")
        else:
            ev[v] = e
    ea = {p: huellkurve(str(p)) for p in audios}
    ea = {k: v for k, v in ea.items() if v is not None}

    ergebnis, vergeben = [], set()
    for v in videos:
        if v not in ev:
            ergebnis.append({"video": str(v), "audio": None, "versatz": 0.0, "güte": 0.0})
            continue
        best = (None, 0.0, -1.0)
        for p, e in ea.items():
            if p in vergeben:
                continue
            off, g = versatz(ev[v], e)
            if g > best[2]:
                best = (p, off, g)
        if best[0] and best[2] >= GUETE_MIN:
            vergeben.add(best[0])
            print(f"  {v.name:26s} <- {best[0].name:28s} {best[1]:+7.2f}s  Güte {best[2]:.2f}")
            ergebnis.append({"video": str(v), "audio": str(best[0]),
                             "versatz": round(best[1], 3), "güte": round(best[2], 3)})
        else:
            g = f"beste Güte {best[2]:.2f}" if best[0] else "keine Kandidaten"
            print(f"  {v.name:26s} <- KAMERATON ({g})")
            ergebnis.append({"video": str(v), "audio": None, "versatz": 0.0,
                             "güte": round(max(best[2], 0.0), 3)})

    if a.json:
        json.dump(ergebnis, open(a.json, "w"), ensure_ascii=False, indent=1)
        print(f"\n-> {a.json}")


if __name__ == "__main__":
    main()
