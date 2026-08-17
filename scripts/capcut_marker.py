#!/usr/bin/env python3
"""
Setzt Marker auf brenzlige Stellen im CapCut-Projekt.

Der automatische Schnitt liegt nicht immer richtig. Statt den Nutzer das ganze
Video absuchen zu lassen, markiert dieses Skript die Stellen, an denen die
Take-Auswahl unsicher war — er springt in CapCut von Marker zu Marker und
prueft nur die.

Woran eine Stelle als unsicher gilt (aus segments_wave.json + keepers.json):

  abbruch    Der Text des Fensters endet mitten im Wort oder auf einem
             Bindestrich — typisch fuer einen abgebrochenen Take.
  dicht      Kurz vor dem Fenster lag ein sehr aehnlicher Take. Dann kann die
             Automatik den falschen erwischt haben.
  kurz       Fenster unter 0.8s — oft ein Fragment statt einer Aussage.
  luecke     Vor dem Fenster wurde mehr als 8s Rohmaterial verworfen. Dort kann
             eine Aussage komplett fehlen.
  doppelt    Zwei aufeinanderfolgende Fenster beginnen fast gleich — moegliche
             Wiederholung im Schnitt.

Usage:
  capcut_marker.py "<projekt>" --edit <ordner>_edit [--trocken]
"""
import argparse, json, os, re, subprocess, sys, time, uuid
from difflib import SequenceMatcher
from pathlib import Path

CAPCUT = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
US = 1_000_000
FARBE = "#00c1cd"          # CapCuts Standard-Markerfarbe
MIN_DAUER = 0.80
LUECKE_AB = 8.0
AEHNLICH_AB = 0.72


def uid():
    return str(uuid.uuid4()).upper()


def capcut_laeuft():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def norm(t):
    t = (t or "").lower()
    t = t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def bricht_ab(text, folgt_direkt):
    """Endet der Text mitten drin?

    Ein Komma am Ende ist KEIN Abbruch — der Satz laeuft im naechsten Fenster
    weiter. Ebenso wenig, wenn das folgende Fenster im Rohmaterial unmittelbar
    anschliesst; dann ist es eine gewollte Fortsetzung und kein Fehlstart
    (17.08.2026: sonst meldet jeder mehrteilige Satz einen Abbruch)."""
    t = (text or "").strip()
    if not t:
        return False
    if t.endswith("-"):          # abgeschnittenes Wort — sicherer Abbruch
        return True
    if re.search(r"[.!?…,;:]$", t):
        return False
    if folgt_direkt:
        return False
    return len(t.split()) >= 2


def pruefe(segs, keepers):
    """Liefert [(zeit_im_schnitt, grund, text)] — Zeit auf der Timeline."""
    funde = []
    t = 0.0
    vorher_text = None
    for i, k in enumerate(keepers):
        dauer = k["b"] - k["a"]
        # Welche Rohsegmente liegen in diesem Fenster?
        drin = [s for s in segs if s["start"] >= k["a"] - 0.05 and s["end"] <= k["b"] + 0.05]
        text = " ".join(s.get("text", "") for s in drin).strip() or k.get("label", "")

        if dauer < MIN_DAUER:
            funde.append((t, "kurz", f"{dauer:.2f}s — evtl. Fragment"))

        # Schliesst das naechste Fenster im ROHMATERIAL direkt an?
        folgt_direkt = (i + 1 < len(keepers)
                        and 0 <= keepers[i+1]["a"] - k["b"] < 1.2)
        if bricht_ab(text, folgt_direkt):
            funde.append((t, "abbruch", text[-46:]))

        # aehnlicher Take kurz davor im Rohmaterial verworfen?
        for s in segs:
            if not (0 < k["a"] - s["end"] < 25):
                continue
            if s["start"] >= k["a"]:
                continue
            if SequenceMatcher(None, norm(s.get("text")), norm(text)).ratio() >= AEHNLICH_AB:
                funde.append((t, "dicht", f"aehnlicher Take bei {s['start']:.1f}s im Rohmaterial"))
                break

        # grosse Luecke davor -> koennte eine Aussage fehlen
        vor_ende = keepers[i-1]["b"] if i else 0.0
        if k["a"] - vor_ende > LUECKE_AB:
            funde.append((t, "luecke", f"{k['a']-vor_ende:.0f}s Rohmaterial verworfen"))

        # beginnt wie das vorige Fenster?
        if vorher_text:
            a = " ".join(norm(vorher_text).split()[:4])
            b = " ".join(norm(text).split()[:4])
            if a and a == b:
                funde.append((t, "doppelt", f"beginnt wie das Fenster davor: {b}"))
        vorher_text = text
        t += dauer

    # nach Zeit sortieren, pro Zeitpunkt nur den ersten Grund
    funde.sort(key=lambda x: x[0])
    schlank, letzte = [], -99.0
    for zeit, grund, info in funde:
        if zeit - letzte < 0.4:
            continue
        schlank.append((zeit, grund, info))
        letzte = zeit
    return schlank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("projekt")
    ap.add_argument("--edit", required=True, help="der <name>_edit Ordner des Schnitts")
    ap.add_argument("--trocken", action="store_true")
    a = ap.parse_args()

    projekt = Path(a.projekt) if Path(a.projekt).is_absolute() else CAPCUT / a.projekt
    if not (projekt / "draft_info.json").exists():
        sys.exit(f"Kein CapCut-Projekt: {projekt}")
    edit = Path(a.edit)
    for n in ("segments_wave.json", "keepers.json"):
        if not (edit / n).exists():
            sys.exit(f"{n} fehlt in {edit}")
    if capcut_laeuft() and not a.trocken:
        sys.exit("CapCut laeuft — bitte mit Cmd+Q beenden.")

    segs = json.load(open(edit / "segments_wave.json"))
    keepers = json.load(open(edit / "keepers.json"))
    funde = pruefe(segs, keepers)

    if not funde:
        print("Keine brenzligen Stellen gefunden.")
        return
    print(f"{len(funde)} Stellen:")
    for zeit, grund, info in funde:
        print(f"   {zeit:6.2f}s  [{grund}] {info[:60]}")
    if a.trocken:
        return

    draft = json.load(open(projekt / "draft_info.json"))
    tm = draft.get("time_marks")
    if not isinstance(tm, dict):
        tm = {"id": uid(), "mark_items": []}
    # eigene Marker ersetzen, fremde behalten
    tm["mark_items"] = [m for m in tm.get("mark_items", [])
                        if not str(m.get("title", "")).startswith("!")]
    for zeit, grund, info in funde:
        tm["mark_items"].append({
            "color": FARBE, "id": uid(),
            "time_range": {"duration": 0, "start": int(zeit * US)},
            "title": f"! {grund}: {info}"[:70],
        })
    draft["time_marks"] = tm
    json.dump(draft, open(projekt / "draft_info.json", "w"), ensure_ascii=False)

    meta_p = projekt / "draft_meta_info.json"
    if meta_p.exists():
        meta = json.load(open(meta_p))
        meta["tm_draft_modified"] = int(time.time() * US)
        json.dump(meta, open(meta_p, "w"), ensure_ascii=False)
    print(f"\n-> {len(funde)} Marker in {projekt.name}")


if __name__ == "__main__":
    main()
