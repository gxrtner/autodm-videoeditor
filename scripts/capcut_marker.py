#!/usr/bin/env python3
"""
Setzt Marker auf brenzlige Stellen im CapCut-Projekt.

Der automatische Schnitt liegt nicht immer richtig. Statt den Nutzer das ganze
Video absuchen zu lassen, markiert dieses Skript die Stellen, an denen die
Take-Auswahl unsicher war - er springt in CapCut von Marker zu Marker und
prüft nur die.

Woran eine Stelle als unsicher gilt (aus segments_wave.json + keepers.json):

  abbruch    Der Text des Fensters endet mitten im Wort oder auf einem
             Bindestrich - typisch für einen abgebrochenen Take.
  dicht      Kurz vor dem Fenster lag ein sehr ähnlicher Take. Dann kann die
             Automatik den falschen erwischt haben.
  kurz       Fenster unter 0.8s - oft ein Fragment statt einer Aussage.
  lücke     Vor dem Fenster wurde mehr als 8s Rohmaterial verworfen. Dort kann
             eine Aussage komplett fehlen.
  doppelt    Zwei aufeinanderfolgende Fenster beginnen fast gleich - mögliche
             Wiederholung im Schnitt.
  wahl       Aus mehreren Anläufen wurde gewählt, und eine deutlich LÄNGERE
             Fassung ist dabei rausgeflogen. Die Automatik nimmt die letzte
             vollständige Fassung - wenn du die Aussage in der Mitte am besten
             gesprochen hast, ist die hier verloren gegangen.
  aufzählung Die zusammengefassten Fassungen unterscheiden sich inhaltlich
             stark. Dann war es womöglich gar keine Wiederholung, sondern eine
             Aufzählung ("zwei Reels pro Tag" / "zwei Karussells pro Woche") -
             und es fehlen Punkte.

Die letzten beiden kommen aus entscheidungen.json, die pick_takes.py neben
keepers.json schreibt. Fehlt die Datei, entfallen nur diese zwei Marker.

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
ÄHNLICH_AB = 0.72
UNEINIG_AB = 0.45     # ab hier gilt eine Gruppe als inhaltlich uneinig


def uid():
    return str(uuid.uuid4()).upper()


def capcut_läuft():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def norm(t):
    t = (t or "").lower()
    t = t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def bricht_ab(text, folgt_direkt):
    """Endet der Text mitten drin?

    Ein Komma am Ende ist KEIN Abbruch - der Satz läuft im nächsten Fenster
    weiter. Ebenso wenig, wenn das folgende Fenster im Rohmaterial unmittelbar
    anschließt; dann ist es eine gewollte Fortsetzung und kein Fehlstart
    (17.08.2026: sonst meldet jeder mehrteilige Satz einen Abbruch)."""
    t = (text or "").strip()
    if not t:
        return False
    if t.endswith("-"):          # abgeschnittenes Wort - sicherer Abbruch
        return True
    if re.search(r"[.!?…,;:]$", t):
        return False
    if folgt_direkt:
        return False
    return len(t.split()) >= 2


def prüfe(segs, keepers, entscheidungen=None):
    """Liefert [(zeit_im_schnitt, grund, text)] - Zeit auf der Timeline."""
    funde = []
    # Entscheidungen auf den Rohsegment-Index des Siegers abbilden, damit sie
    # sich dem passenden Fenster zuordnen lassen.
    nach_sieger = {e["sieger"]["i"]: e for e in (entscheidungen or [])}
    t = 0.0
    vorher_text = None
    for i, k in enumerate(keepers):
        dauer = k["b"] - k["a"]
        # Welche Rohsegmente liegen in diesem Fenster?
        drin = [s for s in segs if s["start"] >= k["a"] - 0.05 and s["end"] <= k["b"] + 0.05]
        text = " ".join(s.get("text", "") for s in drin).strip() or k.get("label", "")

        if dauer < MIN_DAUER:
            funde.append((t, "kurz", f"{dauer:.2f}s - evtl. Fragment"))

        # --- aus dem Entscheidungsprotokoll ---
        for s_ in drin:
            e = nach_sieger.get(s_["i"])
            if not e:
                continue
            if e.get("laengere_verworfen"):
                funde.append((t, "wahl",
                              f'aus {e["anlaeufe"]} Anläufen - eine '
                              f'{e["laengste_verworfene_dauer"]}s lange Fassung flog raus'))
            elif e.get("inhaltlich_uneinig", 0) >= UNEINIG_AB and e["anlaeufe"] >= 2:
                funde.append((t, "aufzählung",
                              f'{e["anlaeufe"]} Fassungen zusammengefasst, aber '
                              f'inhaltlich verschieden - evtl. eigene Punkte'))
            break

        # Schließt das nächste Fenster im ROHMATERIAL direkt an?
        folgt_direkt = (i + 1 < len(keepers)
                        and 0 <= keepers[i+1]["a"] - k["b"] < 1.2)
        if bricht_ab(text, folgt_direkt):
            funde.append((t, "abbruch", text[-46:]))

        # ähnlicher Take kurz davor im Rohmaterial verworfen?
        for s in segs:
            if not (0 < k["a"] - s["end"] < 25):
                continue
            if s["start"] >= k["a"]:
                continue
            if SequenceMatcher(None, norm(s.get("text")), norm(text)).ratio() >= ÄHNLICH_AB:
                funde.append((t, "dicht", f"ähnlicher Take bei {s['start']:.1f}s im Rohmaterial"))
                break

        # große Lücke davor -> könnte eine Aussage fehlen
        vor_ende = keepers[i-1]["b"] if i else 0.0
        if k["a"] - vor_ende > LUECKE_AB:
            funde.append((t, "lücke", f"{k['a']-vor_ende:.0f}s Rohmaterial verworfen"))

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
    if capcut_läuft() and not a.trocken:
        sys.exit("CapCut läuft - bitte mit Cmd+Q beenden.")

    segs = json.load(open(edit / "segments_wave.json"))
    keepers = json.load(open(edit / "keepers.json"))
    ent_pfad = Path(a.edit) / "entscheidungen.json"
    entscheidungen = json.load(open(ent_pfad)) if ent_pfad.exists() else None
    funde = prüfe(segs, keepers, entscheidungen)

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
