#!/usr/bin/env python3
"""
Exportiert einen fertigen Schnitt als CapCut-Projekt zum manuellen Nachfeilen.

Julian schneidet mit der Pipeline und feilt dann in CapCut nach (05.08.2026).
Erzeugt wird ein NEUES Projekt — bestehende werden nie angefasst.

Was im Projekt landet:
  Spur 1 (Haupt)   : die Keeper-Fenster als Segmente aus dem ROHVIDEO,
                     damit er Schnittgrenzen noch verschieben kann
  Spur 2 (Overlay) : B-Roll / Kopf-Inserts an ihren Zeiten
  Spur 3 (Audio)   : Musikbett, falls angegeben

Bewusst NICHT drin: Untertitel. Die macht die Pipeline besser (Style, Timing,
Bildschnitt-Kopplung) — in CapCut waeren sie nur muehsam nachzubauen.

Usage:
  capcut_export.py <rohvideo> <keepers.json> [--broll <plan.json>]
                   [--musik <datei.mp3>] [--name "Projektname"]

Zwei Dinge, die beim ersten Anlauf schiefgingen (05.08.2026):
  * CapCut MUSS geschlossen sein — sonst schreibt es beim Beenden seinen
    Speicherstand ueber das erzeugte Projekt. Wird hier geprueft.
  * Alle Medien landen IM Projektordner (`media/`). macOS gibt CapCut keinen
    Zugriff auf beliebige Ordner; extern liegende Dateien erscheinen als
    "Kein Zugriff auf die Datei moeglich". Das Rohvideo wird dabei als
    1080p-Arbeitsfassung kopiert — zum Nachfeilen reicht das, und 4K wuerde
    die Platte sprengen.
"""
import argparse, json, os, shutil, subprocess, sys, time, uuid
from pathlib import Path

CAPCUT = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
US = 1_000_000  # CapCut rechnet in Mikrosekunden
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"  # Zielpegel wie im finalen Render


def capcut_laeuft() -> bool:
    return subprocess.run(["pgrep", "-x", "CapCut"],
                          capture_output=True).returncode == 0


def uid() -> str:
    return str(uuid.uuid4()).upper()


def video_info(pfad: str) -> dict:
    """Breite, Hoehe, Dauer (s), fps — via ffprobe."""
    os.environ["PATH"] = str(Path.home() / "bin") + ":" + os.environ["PATH"]
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate", "-show_entries", "format=duration",
         "-of", "json", pfad], capture_output=True, text=True)
    d = json.loads(r.stdout)
    s = d["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"w": int(s["width"]), "h": int(s["height"]),
            "dur": float(d["format"]["duration"]), "fps": int(num) / int(den)}


def vorlage_finden() -> Path:
    """Ein bestehendes Projekt als Struktur-Vorlage. Wir ERFINDEN das Format
    nicht, sondern uebernehmen eins, das CapCut selbst geschrieben hat —
    die Segment-Objekte haben ~40 Felder, von denen die meisten egal sind,
    aber fehlen duerfen sie nicht."""
    kandidaten = []
    for p in CAPCUT.iterdir():
        if not (p.is_dir() and (p / "draft_info.json").exists()):
            continue
        try:
            d = json.load(open(p / "draft_info.json"))
        except Exception:
            continue
        # MUSS ein Video-Segment enthalten — daraus klonen wir die Struktur.
        vids = [t for t in d.get("tracks", [])
                if t.get("type") == "video" and t.get("segments")]
        if vids:
            kandidaten.append((len(d.get("tracks", [])), p))
    if not kandidaten:
        # Neuer Rechner ohne eigene Projekte: das mitgelieferte Geruest nehmen.
        # Ein Video-Segment hat ~49 Felder, ein Material ~63 — die erfindet man
        # nicht, deshalb liegt eine echte, von CapCut geschriebene Vorlage bei.
        eigen = Path(__file__).resolve().parent.parent / "vorlage"
        if (eigen / "draft_info.json").exists():
            print(f"Vorlage: mitgeliefertes Geruest ({eigen})")
            return eigen
        sys.exit("Kein CapCut-Projekt mit Video-Segment gefunden und keine "
                 "Vorlage im Paket — einmal ein Video in CapCut auf die "
                 "Timeline ziehen und speichern.")
    # Wenigste Spuren = am einfachsten sauber zu leeren.
    return sorted(kandidaten, key=lambda x: x[0])[0][1]


def mikro_sync(video: str, audio: str) -> float:
    """Versatz der externen Mikro-Aufnahme gegenueber dem Kameraton, in Sekunden.
    Positiv = das Mikro lief bereits, als die Kamera startete.

    Julian nimmt Bild (Sony) und Ton (Ansteckmikro) getrennt auf; in CapCut
    hiess das bisher "Kombinationsclip". Statt nach Dateidauer zu raten wird
    die Lautstaerke-Huellkurve beider Spuren kreuzkorreliert — das findet
    Zuordnung und Versatz in einem Schritt (06.08.2026)."""
    import numpy as np, wave, tempfile
    os.environ["PATH"] = str(Path.home() / "bin") + ":" + os.environ["PATH"]

    def env(pfad, ss=None, t=None):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
        cmd = ["ffmpeg", "-y", "-v", "error"]
        if ss is not None:
            cmd += ["-ss", str(ss)]
        if t is not None:
            cmd += ["-t", str(t)]
        subprocess.run(cmd + ["-i", pfad, "-ac", "1", "-ar", "16000", tmp], check=True)
        w = wave.open(tmp, "rb")
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        w.close(); os.unlink(tmp)
        hop, n = 160, len(a) // 160
        e = np.sqrt(np.array([np.mean(a[i*hop:(i+1)*hop] ** 2) for i in range(n)]))
        e = e - e.mean()
        return e / (np.linalg.norm(e) + 1e-9)

    x, y = env(video), env(audio)
    n = 1 << int(np.ceil(np.log2(len(x) + len(y))))
    c = np.fft.irfft(np.fft.rfft(y, n) * np.conj(np.fft.rfft(x, n)), n)
    c = np.concatenate([c[-(len(x)-1):], c[:len(y)]])
    k = int(np.argmax(c))
    off, guete = (k - (len(x) - 1)) * 0.01, float(c[k])
    if guete < 0.4:
        sys.exit(f"Mikro passt nicht zum Video (Guete {guete:.2f}) — falsche Datei?")
    print(f"  Mikro-Sync: {off:+.2f}s (Guete {guete:.2f})")
    return off


def audio_vorlage():
    """Audio-Material, -Segment, -Spur und Hilfsmaterialien aus einem Projekt,
    das CapCut selbst geschrieben hat. Ein Audio-Segment haengt an fuenf
    Zusatzmaterialien (speed, beats, placeholder, channel-mapping, vocal
    separation) — die werden mitgeklont, statt sie zu erfinden."""
    for p in sorted((x for x in CAPCUT.iterdir() if (x / "draft_info.json").exists()),
                    key=lambda x: -(x / "draft_info.json").stat().st_mtime):
        try:
            d = json.load(open(p / "draft_info.json"))
        except Exception:
            continue
        spur = next((t for t in d.get("tracks", [])
                     if t.get("type") == "audio" and t.get("segments")), None)
        if not spur:
            continue
        seg = spur["segments"][0]
        mat = next((m for m in d["materials"].get("audios", [])
                    if m["id"] == seg.get("material_id")), None)
        if not mat:
            continue
        extras = {}
        for key, arr in d["materials"].items():
            if not isinstance(arr, list):
                continue
            for m in arr:
                if isinstance(m, dict) and m.get("id") in seg.get("extra_material_refs", []):
                    extras.setdefault(key, []).append(m)
        print(f"  Audio-Vorlage: {p.name}")
        return mat, seg, {k: v for k, v in spur.items() if k != "segments"}, extras
    return None, None, None, None


def ins_projekt(quelle: str, ziel_dir: Path, als_proxy: bool = False,
                audio=None, audio_off: float = 0.0, proxy_name=None) -> str:
    """Datei in den Projektordner legen. macOS gibt CapCut keinen Zugriff auf
    beliebige Ordner — extern liegende Medien erscheinen als "Kein Zugriff auf
    die Datei moeglich" (05.08.2026). Grosse Quellvideos werden dabei zu einer
    1080p-Arbeitsfassung: zum Nachfeilen reicht das, 4K wuerde die Platte
    sprengen (der finale Export laeuft ohnehin ueber die Pipeline)."""
    ziel_dir.mkdir(parents=True, exist_ok=True)
    if als_proxy:
        ziel = ziel_dir / (proxy_name or "quelle.mp4")
        print(f"  Arbeitsfassung 1080p: {Path(quelle).name} -> {ziel.name}")
        # Die LANGE Kante auf 1920 — sonst wuerde ein Querformat-Video
        # (3840x2160) auf Hoehe 1920 skaliert und damit 3413px breit statt
        # kleiner (06.08.2026).
        skal = ("scale='if(gt(iw,ih),1920,-2)':'if(gt(iw,ih),-2,1920)'"
                ":force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2")
        cmd = ["ffmpeg", "-y", "-v", "error"]
        if audio:
            # Externe Mikro-Spur so schieben, dass sie zum Bild passt:
            # Mikro lief vor -> vorne wegschneiden; Mikro startete spaeter ->
            # Stille voranstellen.
            if audio_off >= 0:
                cmd += ["-i", quelle, "-ss", f"{audio_off:.3f}", "-i", audio]
                kette = []
            else:
                cmd += ["-i", quelle, "-i", audio]
                kette = [f"adelay={int(round(-audio_off*1000))}:all=1"]
            # Rohes Ansteckmikro liegt bei ~-32 LUFS — in CapCut waere das
            # kaum hoerbar. Auf Zielpegel ziehen, damit die Arbeitsfassung
            # direkt brauchbar ist (06.08.2026). Der finale Render
            # normalisiert ohnehin selbst, das hier bleibt folgenlos.
            kette.append(LOUDNORM)
            cmd += ["-map", "0:v:0", "-map", "1:a:0", "-af", ",".join(kette)]
        else:
            cmd += ["-i", quelle, "-af", LOUDNORM]
        subprocess.run(
            cmd + ["-vf", skal, "-c:v", "libx264", "-crf", "20",
                   "-preset", "fast", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "192k", "-shortest", str(ziel)], check=True)
    else:
        ziel = ziel_dir / Path(quelle).name
        if not ziel.exists():
            shutil.copy(quelle, ziel)
    return str(ziel)


def material_video(pfad: str, info: dict) -> dict:
    return {
        "id": uid(), "type": "video", "path": pfad,
        "material_name": Path(pfad).name,
        "duration": int(info["dur"] * US),
        "width": info["w"], "height": info["h"],
        "has_audio": True, "crop_scale": 1.0,
        "local_material_id": "", "extra_type_option": 0,
        "category_name": "local", "check_flag": 63487,
        "crop": {"lower_left_x": 0.0, "lower_left_y": 1.0,
                 "lower_right_x": 1.0, "lower_right_y": 1.0,
                 "upper_left_x": 0.0, "upper_left_y": 0.0,
                 "upper_right_x": 1.0, "upper_right_y": 0.0},
        "crop_ratio": "free", "source_platform": 0, "type_option": 0,
    }


def segment(vorlage: dict, material_id: str, ziel_start: float, ziel_dauer: float,
            quelle_start: float, render_index: int = 0, volume: float = 1.0) -> dict:
    """Segment aus der Vorlage klonen und die Zeiten setzen."""
    s = json.loads(json.dumps(vorlage))   # tiefe Kopie
    s["id"] = uid()
    s["material_id"] = material_id
    s["target_timerange"] = {"start": int(ziel_start * US), "duration": int(ziel_dauer * US)}
    s["source_timerange"] = {"start": int(quelle_start * US), "duration": int(ziel_dauer * US)}
    s["speed"] = 1.0
    s["volume"] = volume
    s["visible"] = True
    s["render_index"] = render_index
    for k in ("extra_material_refs", "keyframe_refs", "common_keyframes"):
        if k in s and isinstance(s[k], list):
            s[k] = []
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rohvideo", nargs="?")
    ap.add_argument("keepers", nargs="?")
    ap.add_argument("--broll")
    ap.add_argument("--musik")
    ap.add_argument("--name")
    ap.add_argument("--audio", help="externe Mikro-Aufnahme (wird automatisch synchronisiert)")
    ap.add_argument("--audio-spur", action="store_true",
                    help="Stimme als EIGENE Audiospur unter dem Bild statt ins Video gemischt; der Kameraton am Clip wird stummgeschaltet")
    # Julian filmt den CTA oft als EIGENE Aufnahme (06.08.2026, "koffein +
    # L-theanin": Hauptteil C0773 + CTA C0775). Damit daraus EIN Projekt statt
    # zwei wird, nimmt --teil mehrere Quellen entgegen; ihre Keeper landen
    # nacheinander auf derselben Spur.
    ap.add_argument("--teil", action="append", metavar="VIDEO|KEEPERS|AUDIO",
                    help="mehrteiliges Video, mehrfach angebbar (ersetzt die "
                         "positionalen Argumente). AUDIO ist optional.")
    a = ap.parse_args()

    if a.teil:
        teile = []
        for t in a.teil:
            p = (t.split("|") + ["", ""])[:3]
            if not p[0] or not p[1]:
                sys.exit(f"--teil braucht VIDEO|KEEPERS[|AUDIO], bekommen: {t}")
            teile.append((p[0], p[1], p[2] or None))
    elif a.rohvideo and a.keepers:
        teile = [(a.rohvideo, a.keepers, a.audio)]
    else:
        sys.exit("Entweder <rohvideo> <keepers> oder mindestens ein --teil angeben.")

    # CapCut haelt ein geoeffnetes Projekt im Speicher und schreibt es beim
    # Beenden zurueck — jede Aenderung hier waere still wieder weg
    # (05.08.2026 zweimal passiert, sah aus als haette der Export nicht
    # funktioniert). Deshalb harter Abbruch statt sinnlos zu schreiben.
    if capcut_laeuft():
        sys.exit("CapCut laeuft — bitte mit Cmd+Q beenden und neu starten.\n"
                 "       Sonst ueberschreibt es das erzeugte Projekt beim Beenden.")

    roh = str(Path(teile[0][0]).resolve())
    info = video_info(roh)
    name = a.name or (Path(roh).stem + " — Nachfeilen")

    vorlage_dir = vorlage_finden()
    print(f"Vorlage: {vorlage_dir.name}")
    draft = json.load(open(vorlage_dir / "draft_info.json"))

    # Ein echtes Video-Segment als Struktur-Vorlage sichern
    seg_vorlage = None
    for t in draft.get("tracks", []):
        if t.get("type") == "video" and t.get("segments"):
            seg_vorlage = t["segments"][0]
            break
    if seg_vorlage is None:
        sys.exit("Vorlage enthaelt kein Video-Segment — anderes Projekt waehlen.")

    # --- Projekt leeren und neu aufbauen ---
    draft["id"] = uid()
    draft["fps"] = float(int(info["fps"]))
    draft["canvas_config"] = {"ratio": "original", "width": info["w"],
                              "height": info["h"], "background": None}
    for k in ("videos", "audios", "texts", "effects", "material_animations",
              "speeds", "beats", "audio_fades", "placeholders"):
        draft.setdefault("materials", {})[k] = []

    # Projektordner zuerst anlegen — die Medien wandern direkt hinein.
    ordner = CAPCUT / f"{time.strftime('%m%d')}-{name[:40]}"
    n = 1
    while ordner.exists():
        n += 1
        ordner = CAPCUT / f"{time.strftime('%m%d')}-{name[:40]}-{n}"
    shutil.copytree(vorlage_dir, ordner)
    for weg in ("draft_info.json.bak", "draft_cover.jpg", "template-2.tmp"):
        (ordner / weg).unlink(missing_ok=True)
    medien = ordner / "media"

    # Hauptspur: je Teil ein eigenes Material, die Keeper laufen nacheinander
    # auf derselben Zeitachse weiter.
    draft["materials"]["videos"] = []
    haupt, t = [], 0.0
    tonstuecke = []          # fuer die getrennte Audiospur
    for nr, (vid, kp, aud) in enumerate(teile, 1):
        quelle = str(Path(vid).resolve())
        if len(teile) > 1:
            print(f"  Teil {nr}/{len(teile)}: {Path(quelle).name}")
        mikro = str(Path(aud).resolve()) if aud else None
        off = mikro_sync(quelle, mikro) if mikro else 0.0
        # --audio-spur: Mikro NICHT ins Video mischen, sondern als eigene
        # Audiospur unter das Bild legen (Julian 11.08.2026). Der Kameraton
        # bleibt am Clip, wird aber stummgeschaltet — so hat er die Stimme
        # als eigene, bearbeitbare Spur.
        gemuxt = None if a.audio_spur else mikro
        lokal = ins_projekt(quelle, medien, als_proxy=True, audio=gemuxt,
                            audio_off=off,
                            proxy_name=f"quelle{nr}.mp4" if len(teile) > 1 else None)
        if a.audio_spur and mikro:
            tonstuecke.append((mikro, off, kp, t))
        info_lokal = video_info(lokal)
        mat = material_video(lokal, info_lokal)
        draft["materials"]["videos"].append(mat)
        if nr == 1:
            draft["canvas_config"] = {"ratio": "original", "width": info_lokal["w"],
                                      "height": info_lokal["h"], "background": None}
        for k in json.load(open(kp)):
            d = round(k["b"] - k["a"], 3)
            haupt.append(segment(seg_vorlage, mat["id"], t, d, k["a"],
                                 volume=0.0 if a.audio_spur else 1.0))
            t += d
    gesamt = t
    tracks = [{"id": uid(), "type": "video", "attribute": 0, "flag": 0,
               "segments": haupt, "is_default_name": True}]
    print(f"Hauptspur: {len(haupt)} Segmente, {gesamt:.1f}s"
          + (" (Kameraton stumm)" if a.audio_spur else ""))

    # --- Stimme als eigene Audiospur, deckungsgleich zum Bildschnitt ---
    if tonstuecke:
        amat_v, aseg_v, aspur_v, aextras = audio_vorlage()
        if amat_v is None:
            print("  !! keine Audio-Vorlage gefunden — Stimme bleibt ungenutzt")
        else:
            asegs = []
            for mikro, off, kp, basis in tonstuecke:
                lokal = ins_projekt(mikro, medien)      # Datei 1:1 ins Projekt
                dauer = float(subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", lokal], capture_output=True, text=True).stdout.strip())
                m = json.loads(json.dumps(amat_v))
                m["id"] = uid(); m["path"] = lokal; m["name"] = Path(lokal).name
                m["duration"] = int(dauer * US); m["local_material_id"] = ""
                m["music_id"] = str(uuid.uuid4())
                draft["materials"].setdefault("audios", []).append(m)
                tt = basis
                for k in json.load(open(kp)):
                    d = round(k["b"] - k["a"], 3)
                    s = json.loads(json.dumps(aseg_v))
                    s["id"] = uid(); s["material_id"] = m["id"]
                    s["volume"] = 1.0
                    # Mikro-Zeit = Videozeit + Versatz
                    s["source_timerange"] = {"start": int(max(0.0, k["a"] + off) * US),
                                             "duration": int(d * US)}
                    s["target_timerange"] = {"start": int(tt * US), "duration": int(d * US)}
                    neue = []
                    for key, liste in (aextras or {}).items():
                        for alt in liste:
                            kop = json.loads(json.dumps(alt)); kop["id"] = uid()
                            draft["materials"].setdefault(key, []).append(kop)
                            neue.append(kop["id"])
                    s["extra_material_refs"] = neue
                    asegs.append(s)
                    tt += d
            spur = dict(aspur_v); spur["id"] = uid(); spur["segments"] = asegs
            tracks.append(spur)
            print(f"Stimmspur: {len(asegs)} Segmente aus {len(tonstuecke)} Aufnahme(n)")

    # Overlay-Spur: B-Roll / Inserts
    if a.broll and Path(a.broll).exists():
        plan = json.load(open(a.broll))
        basis = Path(a.broll).parent
        segs = []
        for b in plan:
            p = basis / b.get("image_path", "")
            if not p.exists():
                print(f"  uebersprungen (fehlt): {b.get('image_path')}")
                continue
            p_lokal = ins_projekt(str(p), medien)
            bi = video_info(p_lokal)
            m = material_video(p_lokal, bi)
            draft["materials"]["videos"].append(m)
            d = round(b["end_sec"] - b["start_sec"], 3)
            segs.append(segment(seg_vorlage, m["id"], b["start_sec"], d, 0.0,
                                render_index=1, volume=0.0))
        if segs:
            tracks.append({"id": uid(), "type": "video", "attribute": 0, "flag": 2,
                           "segments": segs, "is_default_name": True})
            print(f"Overlay-Spur: {len(segs)} Clips")

    draft["tracks"] = tracks
    draft["duration"] = int(gesamt * US)

    # --- draft schreiben ---
    json.dump(draft, open(ordner / "draft_info.json", "w"), ensure_ascii=False)

    meta_p = ordner / "draft_meta_info.json"
    if meta_p.exists():
        meta = json.load(open(meta_p))
        meta["draft_id"] = draft["id"]
        meta["draft_name"] = ordner.name
        meta["draft_fold_path"] = str(ordner)
        meta["tm_draft_create"] = int(time.time() * US)
        meta["tm_draft_modified"] = int(time.time() * US)
        meta["draft_materials"] = []
        json.dump(meta, open(meta_p, "w"), ensure_ascii=False)

    print(f"\n-> {ordner}")
    print("   CapCut starten (war es offen: erst beenden, dann neu starten).")


if __name__ == "__main__":
    main()
