#!/usr/bin/env python3
"""Waehlt aus den Wellenform-Segmenten die Keeper aus.

REGEL (Julians Vorgabe): Wird eine Zeile mehrfach gesprochen, gewinnt IMMER
die LETZTE Version. Fehlstarts verlieren gegen den vollstaendigen spaeteren Take.

Drei Erkennungswege, weil Fehlstarts unterschiedlich aussehen:
1. AEHNLICHKEIT  - fast gleicher Text -> selbe Zeile
2. PRAEFIX/ANFANG - die ersten N Woerter stimmen ueberein ("nummer 3 notizen" vs
   "nummer 3 notizen machen notizen sind gut...") -> abgebrochener Take
3. MUELL-FILTER  - Whisper halluziniert bei Stille/Atem typische Floskeln
   ("vielen dank fuers zuhoeren", "untertitel von...") und produziert
   Ein-Wort-Fragmente. Beides raus.

Usage: python3 pick_takes.py [--sim 0.68] [--head-words 3] [--min-dur 0.8]
Liest segments_wave.json, schreibt keepers.json.
"""
import json, argparse, re
from difflib import SequenceMatcher

ap = argparse.ArgumentParser()
ap.add_argument("--sim", type=float, default=0.68)
ap.add_argument("--head-words", type=int, default=3, help="gleiche Anfangswoerter -> selbe Zeile")
ap.add_argument("--min-dur", type=float, default=0.8, help="kuerzere Segmente nur behalten wenn eigenstaendig")
ap.add_argument("--min-words", type=int, default=3)
ap.add_argument("--pad-head", type=float, default=0.06)
ap.add_argument("--pad-tail", type=float, default=0.12)
ap.add_argument("--merge-gap", type=float, default=0.60, help="dichter benachbarte Segmente zu einem Fenster verschmelzen")
ap.add_argument("--window", type=float, default=30.0,
                help="max. Abstand in s, in dem zwei Segmente Takes derselben Zeile sein koennen")
a = ap.parse_args()

segs = json.load(open("segments_wave.json"))

# Typische Whisper-Halluzinationen bei Stille/Atem/Geraeusch
JUNK = [
    "vielen dank", "untertitel", "amara.org", "abonniert", "bis zum naechsten",
    "danke fuers zuschauen", "danke fuer s zuhoeren", "zuhoeren", "musik",
    "applaus", "copyright", "swr", "zdf", "ard",
]


WORDNUM = {"eins":"1","zwei":"2","drei":"3","vier":"4","fuenf":"5","sechs":"6",
           "sieben":"7","acht":"8","neun":"9","zehn":"10","erstens":"1","zweitens":"2"}

def norm(t):
    t = t.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = re.sub(r"[^\w ]+", " ", t)
    t = re.sub(r"\bnr\b", "nummer", t)
    words = [WORDNUM.get(w, w) for w in t.split()]
    return " ".join(words).strip()


def linekey(t):
    """Zeilen-Schluessel: 'nummer 3' o.ae. - fasst alle Takes derselben Listenzeile zusammen."""
    n = norm(t)
    m = re.match(r"^nummer (\d+)", n)
    return f"nummer {m.group(1)}" if m else None


def is_junk(t):
    n = norm(t)
    if not n:
        return True
    return any(j in n for j in JUNK)


# Funktionswoerter tragen keine Aussage. Ohne sie wuerde "wenn du mehr VIEWS
# willst" und "wenn du mehr CALLS willst" denselben Kopf ergeben — Julians
# Skripte sind fast immer parallel gebaut, dadurch hat der head-Test ganze
# Listen als Wiederholung verworfen (06.08.2026, C0761: 6s von 131s uebrig).
STOPP = {
    "wenn", "wann", "weil", "dass", "ob", "als", "wie", "was", "wer", "wo",
    "du", "dir", "dich", "ich", "mir", "mich", "er", "sie", "es", "wir", "ihr",
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
    "einer", "eines", "und", "oder", "aber", "dann", "so", "auch", "noch",
    "schon", "mal", "halt", "ja", "nein", "nicht", "kein", "keine", "nur",
    "mehr", "sehr", "ganz", "ist", "sind", "war", "waren", "hat", "haben",
    "wird", "werden", "kann", "koennen", "muss", "muessen", "soll", "sollen",
    "ueber", "fuer", "mit", "von", "zu", "aus", "auf", "in", "im", "am", "an",
    "bei", "nach", "vor", "um", "durch", "gegen", "ohne", "bis", "seit",
}


def head(t, k):
    """Die ersten k INHALTSWOERTER. Faellt auf die rohen Woerter zurueck, wenn
    nach dem Stoppwort-Filter zu wenig uebrig bleibt (z.B. reine Floskeln)."""
    words = [w for w in norm(t).split() if w not in STOPP]
    if len(words) < k:
        return ""
    return " ".join(words[:k])


def similar(x, y):
    nx, ny = norm(x), norm(y)
    if not nx or not ny:
        return 0.0
    short, long_ = (nx, ny) if len(nx) <= len(ny) else (ny, nx)
    if len(short) >= 8 and long_.startswith(short):
        return 1.0
    return SequenceMatcher(None, nx, ny).ratio()


# --- Vorfilter ---
cand, dropped = [], []
for s in segs:
    n = norm(s["text"])
    if is_junk(s["text"]):
        dropped.append((s, "muell/halluzination")); continue
    if len(n.split()) < a.min_words and s["dur"] < a.min_dur:
        dropped.append((s, "fragment")); continue
    cand.append(s)

# --- Gruppieren: spaeteres Segment gewinnt ---
alive = [True] * len(cand)
groups = []
for i in range(len(cand)):
    if not alive[i]:
        continue
    grp = [i]
    for j in range(i + 1, len(cand)):
        if not alive[j]:
            continue
        same = similar(cand[i]["text"], cand[j]["text"]) >= a.sim
        if not same:
            # Der head-Test ist das SCHWACHE Signal: gleicher Anfang heisst nur
            # dann Retake, wenn er dicht dahinter liegt — ein Fehlstart wird
            # sofort neu angesetzt, nicht eine Minute spaeter. Ohne dieses
            # Fenster fielen weit auseinanderliegende, nur aehnlich beginnende
            # Saetze faelschlich zusammen. Echte Textgleichheit (similar) und
            # explizite Zeilennummern brauchen das Fenster nicht — die sind
            # eindeutig, auch ueber zwei komplette Listendurchlaeufe hinweg.
            if cand[j]["start"] - cand[i]["end"] <= a.window:
                hi, hj = head(cand[i]["text"], a.head_words), head(cand[j]["text"], a.head_words)
                if hi and hi == hj:
                    same = True
        if not same:
            ki, kj = linekey(cand[i]["text"]), linekey(cand[j]["text"])
            if ki and ki == kj:
                same = True
        if not same and cand[i]["dur"] < 2.0 and (cand[j]["start"] - cand[i]["end"]) < 25:
            hi2 = head(cand[i]["text"], 2)
            if hi2 and norm(cand[j]["text"]).startswith(hi2):
                same = True
        if same:
            grp.append(j)
    if len(grp) > 1:
        for g in grp[:-1]:
            alive[g] = False
        groups.append((grp, grp[-1]))

winners = sorted((cand[i] for i in range(len(cand)) if alive[i]), key=lambda s: s["start"])

# Benachbarte Gewinner verschmelzen: liegen zwei Segmente dichter als merge_gap
# beieinander, ist das eine natuerliche Sprechpause im selben Satz - getrennte
# Fenster wuerden sich durchs Padding ueberlappen und cut.py verwirft sie dann.
merged = []
for s in winners:
    if merged and s["start"] - merged[-1]["end"] < a.merge_gap:
        merged[-1] = {**merged[-1], "end": s["end"],
                      "text": merged[-1]["text"] + " " + s["text"]}
    else:
        merged.append(dict(s))

keepers = [{
    "a": round(max(0, s["start"] - a.pad_head), 3),
    "b": round(s["end"] + a.pad_tail, 3),
    "label": f'S{s["i"]} {norm(s["text"])[:40]}'
} for s in merged]

json.dump(keepers, open("keepers.json", "w"), ensure_ascii=False, indent=1)

print(f"{len(segs)} Segmente | {len(dropped)} vorgefiltert | {len(groups)} Wiederholungs-Gruppen")
if dropped:
    print("\nVorgefiltert:")
    for s, why in dropped:
        print(f'  S{s["i"]:<3} {s["start"]:7.2f}s  [{why}]  "{s["text"][:45]}"')
print("\nWiederholungen (letzte Version behalten):")
for grp, win in groups:
    losers = ", ".join(f'S{cand[g]["i"]}' for g in grp if g != win)
    print(f'  S{cand[win]["i"]:<3} @{cand[win]["start"]:7.2f}s  "{cand[win]["text"][:48]}"')
    print(f'       raus: {losers}')

total = sum(k["b"] - k["a"] for k in keepers)
print(f"\n=> {len(keepers)} Keeper, ~{total:.1f}s")
for k in keepers:
    print(f'  {k["a"]:7.2f}-{k["b"]:7.2f}  {k["label"]}')
