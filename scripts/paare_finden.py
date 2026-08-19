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
import argparse, re, json, os, subprocess, sys, tempfile
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



def tonpegel(datei):
    """Mittlerer Lautstaerkepegel in dB. Wird gebraucht, um bei zwei Kameras
    zu entscheiden, welche den brauchbaren Ton hat."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-ss", "30", "-t", "30", "-i", str(datei),
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True)
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def ton_ausziehen(video, ziel):
    """Tonspur verlustfrei aus einem Video herausloesen.

    Bei einem Zwei-Kamera-Aufbau ist die Tonquelle selbst ein Video von
    mehreren Gigabyte. Die komplette Datei als "Mikro-Aufnahme" ins Projekt zu
    kopieren waere Unsinn - die Tonspur allein sind ein paar Megabyte.
    """
    if ziel.exists():
        return ziel
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
                        "-vn", "-c:a", "copy", str(ziel)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not ziel.exists():
        # Manche Codecs lassen sich nicht 1:1 in eine m4a legen - dann neu
        # kodieren, hoerbar ist der Unterschied bei Sprache nicht.
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
                        "-vn", "-c:a", "aac", "-b:a", "192k", str(ziel)],
                       capture_output=True, text=True)
    return ziel if ziel.exists() else None


def kamerapaare(videos, ev, pegel, min_guete, min_abstand=6.0):
    """Findet Video-Paare aus einem Zwei-Kamera-Aufbau.

    Zwei Kameras laufen gleichzeitig, eine hat den besseren Ton (Ansteckmikro,
    naeher dran). Erkannt wird das an zwei Dingen: die Tonspuren korrelieren
    hoch (dieselbe Szene), und die Pegel unterscheiden sich deutlich.

    Der Pegelabstand ist die Sicherung. Ohne ihn wuerden zwei Aufnahmen
    derselben Szene mit gleichwertigem Ton zusammengelegt und eine davon als
    blosse Tonquelle verheizt - obwohl es zwei brauchbare Perspektiven sind.
    Rueckgabe: {bildvideo: (tonvideo, versatz, guete)}
    """
    paare, vergeben = {}, set()
    for i, a in enumerate(videos):
        if a in vergeben or a not in ev:
            continue
        for b in videos[i + 1:]:
            if b in vergeben or b not in ev:
                continue
            off, g = versatz(ev[a], ev[b])
            if g < min_guete:
                continue
            pa, pb = pegel.get(a), pegel.get(b)
            if pa is None or pb is None or abs(pa - pb) < min_abstand:
                continue
            # Lauterer Ton gewinnt als Tonquelle, das andere liefert das Bild.
            if pa > pb:
                bild, ton, vs = b, a, -off
            else:
                bild, ton, vs = a, b, off
            paare[bild] = (ton, vs, g)
            vergeben.update({a, b})
            break
    return paare


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

    ea_extra = {}
    ev = {}
    for v in videos:
        e = huellkurve(str(v))
        if e is None:
            print(f"  !! Ton nicht lesbar: {v.name}")
        else:
            ev[v] = e

    # --- Zwei-Kamera-Aufbau erkennen ---
    kam = {}
    if not audios and len(videos) >= 2:
        pegel = {v: tonpegel(v) for v in ev}
        kam = kamerapaare(videos, ev, pegel, GUETE_MIN)
        if kam:
            print(f"\n{len(kam)} Kamerapaare erkannt "
                  f"(zwei Kameras, Ton von der mit dem besseren Pegel):")
            for bild, (ton, vs, g) in kam.items():
                print(f"  Bild {bild.name:22s} Ton {ton.name:22s} "
                      f"{pegel[bild]:6.1f} dB vs {pegel[ton]:6.1f} dB  "
                      f"{vs:+6.2f}s  Guete {g:.2f}")
                spur = ton.with_suffix(".tonspur.m4a")
                if ton_ausziehen(ton, spur):
                    audios.append(spur)
                    ea_extra[bild] = spur
                else:
                    print(f"    !! Ton konnte nicht ausgezogen werden: {ton.name}")
            # Die Tonkameras sind keine eigenstaendigen Videos mehr.
            videos = [v for v in videos if v not in {t for t, _, _ in kam.values()}]
            print()
    ea = {p: huellkurve(str(p)) for p in audios}
    ea = {k: v for k, v in ea.items() if v is not None}

    ergebnis, vergeben = [], set()
    for v in videos:
        if v not in ev:
            ergebnis.append({"video": str(v), "audio": None, "versatz": 0.0, "güte": 0.0})
            continue
        # Bei erkanntem Kamerapaar steht die Zuordnung schon fest - dann nicht
        # noch einmal raten, sondern den ausgezogenen Ton direkt nehmen.
        if v in ea_extra:
            ton, vs, g = kam[v][0], kam[v][1], kam[v][2]
            print(f"  {v.name:26s} <- {ea_extra[v].name:28s} {vs:+7.2f}s  "
                  f"Güte {g:.2f}  (zweite Kamera)")
            ergebnis.append({"video": str(v), "audio": str(ea_extra[v]),
                             "versatz": round(vs, 3), "güte": round(g, 3),
                             "quelle": "zweite kamera", "tonvideo": str(ton)})
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
