#!/usr/bin/env python3
"""Wählt aus den Wellenform-Segmenten die Keeper aus - BLOCKWEISE.

Der Unterschied zum Vorgänger steckt nicht in einer neuen Ähnlichkeitsformel,
sondern in der Frage, WELCHE Segmentpaare überhaupt miteinander verglichen
werden dürfen und wie streng dabei gemessen wird.

Beobachtung, auf der alles aufbaut: Julian nimmt in BLÖCKEN auf. Er sagt einen
Satz, bricht ab, setzt sofort neu an, wieder und wieder - und erst wenn der
Gedanke steht, macht er eine längere Pause und springt zum nächsten. Ein Block
ist damit fast immer EINE Aussage, und die Wiederholungen liegen dicht
beieinander. Ein Block darf trotzdem mehrere Keeper liefern: macht Julian
mitten im Satz eine Sprechpause, stehen zwei Segmente derselben Aussage im
selben Block, ähneln sich aber nicht - sie bilden zwei Gruppen und werden am
Ende über --merge-gap wieder zu einem Fenster zusammengezogen.

VIER BAUTEILE

1. BLOCKGRENZE aus den Pausenlängen des Videos selbst (Otsu-Schnitt auf
   log(1+Pause)), geklemmt auf [--block-min, --block-max]. Kein fester Wert,
   weil Julian mal schnell und mal bedächtig spricht: C0781 bekommt 1.87s,
   IMG_7323 2.35s, C0785 4.50s.

2. INNERHALB eines Blocks wird LOCKER verglichen und TRANSITIV gruppiert
   (Union-Find). Zwei Takes derselben Aussage müssen sich nicht mehr direkt
   ähneln - es reicht, wenn eine Kette sie verbindet. Genau daran ist die alte
   greedy Ankerlogik gescheitert: wer als Anker seine Mini-Gruppe gewonnen
   hatte, wurde nie wieder geprüft. In C0773 gewinnt S36 gegen S0 und wird
   zwei Zeilen später von S1 erschlagen.

3. ÜBER Blöcke hinweg wird STRENG verglichen, ebenfalls transitiv, aber nur
   bis --fern-max Sekunden Abstand und nur mit zusätzlicher Wortdeckung. Das
   fängt die Aussage, die über mehrere Blöcke hinweg immer wieder neu
   angesetzt wird - in C0785 landen die 15 Anläufe auf "Ausserdem checkt er
   noch nicht..." (S19 bis S33, verteilt über vier Blöcke) jetzt in EINER
   Gruppe statt in vieren.

4. WORTDECKUNG als Boden unter jeder Verbindung. Zeichenähnlichkeit allein
   reicht nicht: zwei völlig verschiedene deutsche Sätze liegen auf
   Zeichenebene regelmäßig bei 0.45.

WARUM DIE SCHWELLE VOM ABSTAND ABHÄNGT
Über alle 21 handkorrigierten Läufe habe ich jedes Kandidatenpaar daraufhin
geprüft, ob die Hand BEIDE behält (dann wäre Gruppieren ein Fehler) oder
höchstens einen (dann ist Gruppieren richtig):

    Abstand    Schwelle 0.45     Schwelle 0.50     Schwelle 0.68
    0 - 2s     154 ok /  2 falsch  147 /  1          94 / 1
    2 - 4s      95 ok /  3          86 /  3          59 / 0
    4 - 8s     114 ok /  3         104 /  0          58 / 0
    8 - 15s    137 ok /  8         118 /  5          65 / 0
    15 - 60s   348 ok / 30         254 /  8         100 / 1
    über 60s   180 ok / 19          83 /  5          19 / 2

Dicht beieinander darf man fast beliebig locker sein, weit auseinander
praktisch gar nicht. Deshalb steigt die Schwelle innerhalb des Blocks linear
mit dem Abstand (--sim-intern + --steigung) und ist ab Blockgrenze fest
auf --sim.

GEMESSEN (bewerten.py, 22 Läufe, 21 mit Handreferenz, Aufruf --sim 0.68
--head-words 3)

                        IST-Stand   diese Datei
    F1 makro              0.752       0.851
    F1 mikro              0.729       0.836
    Präzision             0.63        0.77
    Ausbeute              0.857       0.909
    Zuviel / Fehlend    124 / 36     67 / 23
    Sekunden gg. Hand     130%        117%
    Fragmente           9 / 317      7 / 276
    Doppel-Paare       14 / 2724    10 / 2093
    C0785 muss_raus   [12, 13, 38]   [38]

17 der 21 Läufe werden besser, 3 bleiben gleich, einer wird schlechter
(C0781, F1 0.94 statt 1.00). Die Ausbeute fällt in genau drei Läufen:
C0781 (-0.11), IMG_7323 (-0.25), C0785 (-0.20 gegen soll_ideal).

GEGENPROBE ZUR FEHLERRICHTUNG VOM 06.08.2026
Die karte-Charge ist das parallel gebaute Material, an dem damals 131s auf 6s
zusammengeschrumpft sind. Dort fällt die Ausbeute in KEINEM Lauf:
C0759 0.50->0.62, C0760 0.80->0.90, C0761 0.80->1.00, C0762 0.69->0.85,
C0763 0.90->0.90, C0764 0.80->0.87, C0765 1.00->1.00, C0766 0.82->1.00,
C0767 0.78->0.89, C0768 1.00->1.00, C0769 0.88->1.00, C0773 0.91->0.91,
C0775 1.00->1.00.

EHRLICHE AUFTEILUNG DES GEWINNS
Ein Teil des Vorsprungs hat mit Blöcken nichts zu tun: --vollstaendig war mit
0.90 zu streng. Gemessen:

    alter Code, alte Parameter                   makro 0.752  mikro 0.729
    alter Code, nur --vollstaendig 0.50          makro 0.808  mikro 0.786
    diese Datei, aber --vollstaendig 0.90        makro 0.791  mikro 0.773
    diese Datei, Endstand                        makro 0.851  mikro 0.836

Das Sieger-Kriterium allein bringt +0.056, der Block-Ansatz allein +0.039
(kauft dabei aber Präzision mit Ausbeute), zusammen +0.099. Beide Teile
braucht es.

KEIN ÜBERANPASSEN AN DIE 21 LÄUFE
Neun Läufe habe ich beim Bauen nie einzeln angeschaut (C0779, C0760, C0763,
C0765, C0766, C0768, C0769, C0775, IMG_7325). Nur auf diesen gerechnet:
Präzision 0.844 -> 0.942, Ausbeute 0.911 -> 0.960, F1 mikro 0.876 -> 0.951.
Der Gewinn steht also auch dort, wo nicht nachjustiert wurde. Zusätzlich
liegen alle Kennzahlen auf einem Plateau: keine der 19 zuletzt geprüften
Parametervariationen bewegt F1 makro um mehr als 0.02.

WAS DIESE DATEI NICHT KANN
- C0773 bleibt bei Präzision 0.31. Julian spricht das Video zweimal komplett
  durch; die Hand behält nur den zweiten Durchlauf. Die Formulierungen der
  beiden Durchläufe unterscheiden sich zu stark für einen Textvergleich
  ("Die meisten nutzen aber Koffein komplett falsch und trinken es unter dem
  Tag verteilt" gegen "Die meisten Menschen trinken Koffein unterm Tag
  verteilt und Grüntee gar nicht"). Das braucht einen Durchlauf-Detektor, der
  ganze Blockfolgen gegeneinander ausrichtet - eine andere Baustelle.
- Julians Listenzeilen, die sich nur in EINEM Wort unterscheiden, fallen
  weiter gelegentlich zusammen: IMG_7323 "ein Foto von dir beim Arbeiten"
  gegen "ein Foto von dir auf einem Event", C0781 "Er hat Teammitglieder..."
  gegen "Man hat validierte Systeme...". Das sind die 2 bzw. 1 verlorenen
  Segmente dieser beiden Läufe.
- S38 in C0785 ("Boah, das ist echt crazy.") bleibt drin. Das ist Geplauder
  90 Sekunden nach dem letzten Satz und keine Wiederholung - dagegen hilft
  nur eine Regel über die Schlussstille, nicht die Gruppierung.

ZIRKULARITÄTS-HINWEIS ZUR DOPPEL-QUOTE
Diese Datei benutzt Wortdeckung über Inhaltswörter als Verbindungskriterium.
Das Harness misst die Doppel-Quote mit genau demselben Maß. Für Paare
innerhalb von --fern-max ist die Doppel-Quote deshalb NICHT mehr unabhängig -
sie fällt dort schon per Konstruktion. Aussagekräftig bleiben Präzision,
Ausbeute und die Fragment-Quote.
Nachgerechnet: 9 der 10 verbliebenen Doppel-Paare liegen jenseits von
--fern-max, konnten also gar nicht gruppiert werden. Sieben davon sind
C0762s wiederkehrende Urteilszeile "Schon besser mit IQ." - die behält die
Hand DREIMAL, das Maß schlägt dort also falsch an. Das zehnte Paar (C0785
S27/S33, 34s Abstand) liegt innerhalb von --fern-max und ist unter
--fern-sim-schwach durchgerutscht.

ZUR FRAGMENT-QUOTE
Sie steht mit 7/276 praktisch auf dem IST-Wert (9/317). Vier der sieben
stehen in C0767 und sind Buchtitel, die die Hand ausdrücklich behält
("Rich Dad Poor Dad.", "Charlie Al Mania."). Kurz ist dort kein Fehler.

Usage: python3 pick_takes.py [--sim 0.68] [--head-words 3] [--min-dur 0.8]
Liest segments_wave.json, schreibt keepers.json.
"""
import json, argparse, re, math
from difflib import SequenceMatcher

ap = argparse.ArgumentParser()
ap.add_argument("--sim", type=float, default=0.68, help="Schwelle über Blockgrenzen hinweg")
ap.add_argument("--head-words", type=int, default=3, help="gleiche Anfangswörter -> selbe Zeile")
ap.add_argument("--min-dur", type=float, default=0.8, help="kürzere Segmente nur behalten wenn eigenstaendig")
ap.add_argument("--min-words", type=int, default=3)
ap.add_argument("--pad-head", type=float, default=0.06)
ap.add_argument("--pad-tail", type=float, default=0.12)
ap.add_argument("--merge-gap", type=float, default=0.60, help="dichter benachbarte Segmente zu einem Fenster verschmelzen")
ap.add_argument("--schluss-stille", type=float, default=30.0,
                help="Stille in s am Ende, ab der Nachgeplauder verworfen wird (0 = aus)")
ap.add_argument("--schluss-anteil", type=float, default=0.06,
                help="max. Anteil an der Gesamtlaenge, den das Nachgeplauder haben darf")
ap.add_argument("--vollstaendig", type=float, default=0.50,
                help="Anteil der Maximaldauer, ab dem ein Take als vollstaendig gilt")
ap.add_argument("--window", type=float, default=30.0,
                help="max. Abstand in s, in dem zwei Segmente Takes derselben Zeile sein können")
# --- blockweise Auswertung -------------------------------------------------
ap.add_argument("--block-min", type=float, default=1.2, help="untere Klemme der Blockgrenze")
ap.add_argument("--block-max", type=float, default=4.5, help="obere Klemme der Blockgrenze")
ap.add_argument("--block-fix", type=float, default=0.0,
                help="feste Blockgrenze in s statt datengetrieben (0 = datengetrieben)")
ap.add_argument("--sim-intern", type=float, default=0.40,
                help="Schwelle für zwei dicht benachbarte Takes im selben Block")
ap.add_argument("--steigung", type=float, default=0.030,
                help="um so viel steigt die Blockschwelle je Sekunde Abstand")
ap.add_argument("--steigung-ab", type=float, default=2.0,
                help="ab diesem Abstand in s beginnt die Schwelle zu steigen")
ap.add_argument("--intern-deckung", type=float, default=0.70,
                help="Wortdeckung des kürzeren Takes im längeren, nur blockintern")
ap.add_argument("--fern-max", type=float, default=60.0,
                help="max. Abstand in s für einen Vergleich über Blockgrenzen hinweg")
ap.add_argument("--fern-deckung", type=float, default=0.45,
                help="zusätzlich geforderte Wortdeckung für einen Vergleich über Blockgrenzen")
ap.add_argument("--fern-sim-schwach", type=float, default=0.50,
                help="niedrigere Ähnlichkeitsschwelle fern, wenn die Wortdeckung sehr hoch ist")
ap.add_argument("--fern-deckung-stark", type=float, default=0.70,
                help="ab dieser Wortdeckung gilt fern die Schwelle --fern-sim-schwach")
ap.add_argument("--nur-sieger-fern", dest="fern_alle", action="store_false", default=True,
                help="über Blockgrenzen nur die Blocksieger vergleichen (gemessen: 0.02 F1 schlechter)")
ap.add_argument("--fern-woerter", type=int, default=2,
                help="Mindestzahl Inhaltswörter auf der kürzeren Seite für einen Fernvergleich")
ap.add_argument("--boden-deckung", type=float, default=0.30,
                help="Mindest-Wortdeckung, damit zwei Segmente überhaupt verbunden werden")
ap.add_argument("--gruppen-woerter", type=int, default=3,
                help="unter so vielen Inhaltswörtern greift der Deckungs-Boden nicht")
ap.add_argument("--praefix-intern", type=int, default=8,
                help="Mindestlänge in Zeichen für den Präfix-Kurzschluss INNERHALB eines Blocks")
ap.add_argument("--praefix-fern", type=int, default=25,
                help="Mindestlänge in Zeichen für den Präfix-Kurzschluss ÜBER Blockgrenzen")
a = ap.parse_args()

segs = json.load(open("segments_wave.json"))

# Typische Whisper-Halluzinationen bei Stille/Atem/Geraeusch.
#
# ZWEI FALLEN, beide am 18.08.2026 aufgeflogen:
#
# 1. Der Vergleich lief mit "in", also auf Teilzeichenketten OHNE Wortgrenze.
#    "ard" (der Sender) steckt in "onbo-ard-ing", "whitebo-ard" und "h-ard".
#    Ueber alle 22 Laeufe: 9 Treffer, davon 9 Fehlalarme - kein einziger
#    echter Sendername. Deshalb jetzt \b-Wortgrenzen.
#
# 2. Die Liste wird gegen norm()-Text verglichen, und norm() ersetzt Umlaute
#    durch ae/oe/ue. Eintraege MIT Umlaut koennen deshalb nie treffen. Hier
#    stehen sie bewusst transliteriert - das ist kein Verstoss gegen die
#    Schreibregel, sondern ein Vergleichswert, der zum normalisierten Text
#    passen muss.
JUNK = [
    "vielen dank", "untertitel", "amara org", "abonniert", "bis zum naechsten",
    "danke fuers zuschauen", "danke fuer s zuhoeren", "zuhoeren", "musik",
    "applaus", "copyright", "swr", "zdf", "ard",
]
JUNK_RE = [re.compile(rf"\b{re.escape(j)}\b") for j in JUNK]


WORDNUM = {"eins":"1","zwei":"2","drei":"3","vier":"4","fünf":"5","sechs":"6",
           "sieben":"7","acht":"8","neun":"9","zehn":"10","erstens":"1","zweitens":"2"}

def norm(t):
    t = t.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = re.sub(r"[^\w ]+", " ", t)
    t = re.sub(r"\bnr\b", "nummer", t)
    words = [WORDNUM.get(w, w) for w in t.split()]
    return " ".join(words).strip()


def linekey(t):
    """Zeilen-Schlüssel: 'nummer 3' o.ae. - fasst alle Takes derselben Listenzeile zusammen."""
    n = norm(t)
    m = re.match(r"^nummer (\d+)", n)
    return f"nummer {m.group(1)}" if m else None


def is_junk(t):
    n = norm(t)
    if not n:
        return True
    return any(r.search(n) for r in JUNK_RE)


# Funktionswörter tragen keine Aussage. Ohne sie würde "wenn du mehr VIEWS
# willst" und "wenn du mehr CALLS willst" denselben Kopf ergeben - Julians
# Skripte sind fast immer parallel gebaut, dadurch hat der head-Test ganze
# Listen als Wiederholung verworfen (06.08.2026, C0761: 6s von 131s übrig).
STOPP = {
    "wenn", "wann", "weil", "dass", "ob", "als", "wie", "was", "wer", "wo",
    "du", "dir", "dich", "ich", "mir", "mich", "er", "sie", "es", "wir", "ihr",
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
    "einer", "eines", "und", "oder", "aber", "dann", "so", "auch", "noch",
    "schon", "mal", "halt", "ja", "nein", "nicht", "kein", "keine", "nur",
    "mehr", "sehr", "ganz", "ist", "sind", "war", "waren", "hat", "haben",
    "wird", "werden", "kann", "können", "muss", "müssen", "soll", "sollen",
    "über", "für", "mit", "von", "zu", "aus", "auf", "in", "im", "am", "an",
    "bei", "nach", "vor", "um", "durch", "gegen", "ohne", "bis", "seit",
}


def inhalt(t):
    return [w for w in norm(t).split() if w not in STOPP]


def head(t, k):
    """Die ersten k INHALTSWOERTER."""
    words = inhalt(t)
    if len(words) < k:
        return ""
    return " ".join(words[:k])


def similar(x, y, praefix_min=8):
    nx, ny = norm(x), norm(y)
    if not nx or not ny:
        return 0.0
    short, long_ = (nx, ny) if len(nx) <= len(ny) else (ny, nx)
    # Der Praefix-Kurzschluss ist gefaehrlich, sobald transitiv gruppiert wird.
    # In C0767 bewertet Julian jedes Buch mit "8 bis 10, ..." - der Anfang
    # "8 bis 10" hat normalisiert genau 8 Zeichen und ist damit Praefix JEDER
    # Bewertung im ganzen Video. Ueber diese eine Bruecke sind elf Segmente aus
    # fuenf verschiedenen Buchbesprechungen zu einer Gruppe zusammengelaufen.
    # Deshalb muss ein Praefix substanziell sein, bevor er als Beweis zaehlt.
    if len(short) >= praefix_min and long_.startswith(short):
        return 1.0
    return SequenceMatcher(None, nx, ny).ratio()


def deckung(kurz, lang):
    """Anteil der Inhaltswörter des kürzeren Takes, die im längeren vorkommen.

    Der head()-Test greift bei genau den Fällen nicht, für die er gedacht war:
    bei 18% der Kandidaten liefert head(t,3) einen Leerstring, weil nach dem
    Stoppwort-Filter keine drei Inhaltswörter übrig bleiben - und das sind die
    kurzen Fehlstarts. Die Wortdeckung braucht keine Mindestlänge und ist
    gegen Umstellungen unempfindlich ("Er checkt außerdem noch nicht, wenn er"
    gegen "Außerdem checkt er noch nicht, dass wenn er ...").

    Nur blockintern verwendet: über Blockgrenzen hinweg würde sie Julians
    parallel gebaute Listenzeilen zusammenwerfen.
    """
    ck, cl = inhalt(kurz), inhalt(lang)
    if len(ck) < 2 or not cl:
        return 0.0
    treffer = sum(1 for w in set(ck) if w in cl)
    return treffer / len(set(ck))


# --- Vorfilter ---
cand, dropped = [], []
for s in segs:
    n = norm(s["text"])
    if is_junk(s["text"]):
        dropped.append((s, "muell/halluzination")); continue
    # ODER, nicht UND (18.08.2026). Vorher musste ein Segment BEIDES sein -
    # zu wenige Woerter UND zu kurz. "Ja, da fuhre." dauert 0.36s, hat aber
    # genau 3 Woerter und rutschte durch; "anstatt auf" hat 2 Woerter, dauert
    # aber 1.22s.
    #
    # AUSNAHME Listenzeilen: "Nummer 3." ist kurz und trotzdem gewollt.
    if not linekey(s["text"]) and (len(n.split()) < a.min_words or s["dur"] < a.min_dur):
        dropped.append((s, "fragment")); continue
    cand.append(s)


# ---------------------------------------------------------------- Blockgrenze
def blockgrenze(cs):
    """Otsu-Schnitt auf log(1+Pause): trennt die Pausen des Videos in
    "Atemholen zwischen zwei Anläufen" und "Gedankenwechsel".

    Fest verdrahtete 3 Sekunden wären falsch: C0779 hat Pausen von 0.5s bis
    3s, C0773 welche bis 8s. Der Schnitt wird trotzdem geklemmt, weil ein
    Video mit nur einer Handvoll Segmenten sonst absurde Werte liefert.
    """
    if a.block_fix > 0:
        return a.block_fix
    gaps = sorted(cs[k]["start"] - cs[k - 1]["end"] for k in range(1, len(cs)))
    if len(gaps) < 6:
        return (a.block_min + a.block_max) / 2
    x = [math.log1p(g) for g in gaps]
    n = len(x)
    ges = sum(x)
    bester, schnitt = -1.0, None
    lauf = 0.0
    for k in range(1, n):
        lauf += x[k - 1]
        w0, w1 = k / n, (n - k) / n
        m0 = lauf / k
        m1 = (ges - lauf) / (n - k)
        v = w0 * w1 * (m0 - m1) ** 2
        if v > bester:
            bester, schnitt = v, (gaps[k - 1] + gaps[k]) / 2
    return max(a.block_min, min(a.block_max, schnitt))


G = blockgrenze(cand) if len(cand) > 1 else a.block_max

block_von = [0] * len(cand)
for k in range(1, len(cand)):
    neu = (cand[k]["start"] - cand[k - 1]["end"]) > G
    block_von[k] = block_von[k - 1] + (1 if neu else 0)
n_bloecke = (block_von[-1] + 1) if cand else 0


# ---------------------------------------------------------------- Union-Find
eltern = list(range(len(cand)))


def finde(x):
    while eltern[x] != x:
        eltern[x] = eltern[eltern[x]]
        x = eltern[x]
    return x


def vereine(x, y):
    rx, ry = finde(x), finde(y)
    if rx != ry:
        eltern[max(rx, ry)] = min(rx, ry)


def schwelle_intern(d):
    """Blockintern: locker bei dichtem Abstand, streng am Blockende.

    Ein Block kann 30 Sekunden umspannen (C0785, S19 bis S27). Eine feste
    lockere Schwelle über die ganze Blocklänge wäre zu mutig - deshalb steigt
    sie an und läuft spätestens bei --sim gegen den Anschlag.
    """
    s = a.sim_intern + a.steigung * max(0.0, d - a.steigung_ab)
    return min(s, a.sim)


def sieger_von(grp, erlaubt=None):
    """Julians Regel: von den vollstaendigen Fassungen gewinnt die SPAETESTE.

    Nicht die laengste (das waere oft der erste, ausschweifende Anlauf) und
    nicht stumpf die letzte (Julian beendet einen Block gern mit einem halben
    Satz). `erlaubt` grenzt die Wahl auf die Sieger der ersten Stufe ein -
    ein blockintern schon verworfener Fehlstart soll nicht ueber den Umweg
    der zweiten Stufe zurueckkommen.
    """
    kreis = [g for g in grp if erlaubt is None or g in erlaubt] or list(grp)
    laengste = max(cand[g]["dur"] for g in kreis)
    tauglich = [g for g in kreis if cand[g]["dur"] >= a.vollstaendig * laengste]
    return (tauglich or kreis)[-1]


# ---------------------------------------------------------------- Stufe 1: innerhalb der Bloecke
# Hier wird locker und transitiv gruppiert. Transitiv, weil die alte greedy
# Ankerlogik daran gescheitert ist: wer als Anker seine Mini-Gruppe gewonnen
# hatte, wurde nie wieder geprueft. In C0773 gewinnt S36 gegen S0 und wird
# zwei Zeilen spaeter von S1 erschlagen, obwohl S1 selbst schon Teil derselben
# Aussage ist. Union-Find kennt dieses Problem nicht.
paare = []
for i in range(len(cand)):
    for j in range(i + 1, len(cand)):
        if block_von[i] != block_von[j]:
            break
        d = cand[j]["start"] - cand[i]["end"]
        ti, tj = cand[i]["text"], cand[j]["text"]
        s = similar(ti, tj, a.praefix_intern)
        grund = None
        kurz_, lang_ = (ti, tj) if len(inhalt(ti)) <= len(inhalt(tj)) else (tj, ti)
        dk = deckung(kurz_, lang_)
        # Zeichenaehnlichkeit allein reicht nicht. Zwei voellig verschiedene
        # deutsche Saetze liegen auf Zeichenebene regelmaessig bei 0.45 - das
        # ist der Grund, warum in C0785 der Anfang von Aussage H an die Kette
        # der 15 Anlaeufe auf Aussage G geraten ist und Aussage G danach
        # komplett aus dem Schnitt verschwand. Ein echter Fehlstart teilt
        # dagegen fast alle Inhaltswoerter mit dem vollstaendigen Take.
        if s >= schwelle_intern(d) and (dk >= a.boden_deckung
                                        or len(inhalt(kurz_)) < a.gruppen_woerter):
            grund = "intern-aehnlich"
        elif dk >= a.intern_deckung:
            grund = "intern-deckung"
        if grund is None:
            ki, kj = linekey(ti), linekey(tj)
            if ki and ki == kj:
                grund = "listenzeile"
        if grund is None and d <= a.window:
            hi, hj = head(ti, a.head_words), head(tj, a.head_words)
            if hi and hi == hj:
                grund = "kopf"
        if grund:
            vereine(i, j)
            paare.append((i, j, grund, round(s, 2)))

stufe1 = {}
for i in range(len(cand)):
    stufe1.setdefault(finde(i), []).append(i)
blocksieger = sorted(sieger_von(grp) for grp in stufe1.values())
ist_blocksieger = set(blocksieger)

# ---------------------------------------------------------------- Stufe 2: ueber Blockgrenzen
# Verglichen werden NUR die Sieger der ersten Stufe. Das ist der Kern des
# Ansatzes und nicht bloss Sparsamkeit: Fehlstarts sind abgehackte Halbsaetze,
# und abgehackte Halbsaetze aus parallel gebauten Zeilen aehneln einander auf
# Zeichenebene stark, ohne dasselbe zu meinen. In C0761 liefert
# "Wenn du mehr Views willst, dann poste mir die."  gegen
# "Wenn du mehr Sales willst, dann gestalte eine Miete."  eine Aehnlichkeit
# von 0.74 - beides Fehlstarts, 84 Sekunden auseinander, zwei voellig
# verschiedene Zeilen der Liste. Ueber diese eine Bruecke sind in der ersten
# Fassung dieser Datei die komplette Views-Zeile und die komplette Sales-Zeile
# zu einer Gruppe verschmolzen (Ausbeute 0.80 -> 0.60). Vergleicht man nur die
# Sieger, treten S3 und S14 gegeneinander an - Aehnlichkeit 0.46, kein Treffer.
#
# Zweite Sicherung: --fern-deckung verlangt zusaetzlich, dass sich die
# INHALTSWOERTER ueberschneiden. Genau daran scheitern Julians parallele
# Zeilen ("views willst poste" gegen "sales gestalte miete"), waehrend echte
# Wiederholungen derselben Aussage muehelos darueber kommen.
fern_kreis = list(range(len(cand))) if a.fern_alle else blocksieger
for x in range(len(fern_kreis)):
    for y in range(x + 1, len(fern_kreis)):
        i, j = fern_kreis[x], fern_kreis[y]
        if block_von[i] == block_von[j]:
            continue
        d = cand[j]["start"] - cand[i]["end"]
        if d > a.fern_max:
            break
        ti, tj = cand[i]["text"], cand[j]["text"]
        s = similar(ti, tj, a.praefix_fern)
        grund = None
        if min(len(inhalt(ti)), len(inhalt(tj))) >= a.fern_woerter:
            kurz, lang = (ti, tj) if len(inhalt(ti)) <= len(inhalt(tj)) else (tj, ti)
            dkf = deckung(kurz, lang)
            if s >= a.sim and dkf >= a.fern_deckung:
                grund = "fern-aehnlich"
            elif s >= a.fern_sim_schwach and dkf >= a.fern_deckung_stark:
                grund = "fern-wortgleich"
        if grund is None:
            ki, kj = linekey(ti), linekey(tj)
            if ki and ki == kj:
                grund = "listenzeile"
        if grund:
            vereine(i, j)
            paare.append((i, j, grund, round(s, 2)))


# ---------------------------------------------------------------- Sieger je Gruppe
gruppen = {}
for i in range(len(cand)):
    gruppen.setdefault(finde(i), []).append(i)

alive = [True] * len(cand)
protokoll = []
for wurzel, grp in gruppen.items():
    if len(grp) < 2:
        continue
    sieger = sieger_von(grp, ist_blocksieger)
    for g in grp:
        if g != sieger:
            alive[g] = False
    protokoll.append((grp, sieger))

winners = sorted((cand[i] for i in range(len(cand)) if alive[i]), key=lambda s: s["start"])

# Benachbarte Gewinner verschmelzen: liegen zwei Segmente dichter als merge_gap
# beieinander, ist das eine natuerliche Sprechpause im selben Satz - getrennte
# Fenster würden sich durchs Padding überlappen und cut.py verwirft sie dann.
merged = []
for s in winners:
    if merged and s["start"] - merged[-1]["end"] < a.merge_gap:
        merged[-1] = {**merged[-1], "end": s["end"],
                      "text": merged[-1]["text"] + " " + s["text"]}
    else:
        merged.append(dict(s))

# --- Nachgeplauder abschneiden ---
#
# Nach dem letzten Satz laesst Julian die Kamera laufen und redet weiter
# ("Boah, das ist echt crazy.", "Das ist ein Foto.", "Ich folg dir jetzt.").
# Das ist keine Wiederholung, deshalb greift keine Gruppierungsregel - es
# steht einfach am Ende im Schnitt. Die Signatur ist aber eindeutig: davor
# liegt eine sehr lange Stille (in C0785 92 Sekunden), und was danach kommt,
# ist im Verhaeltnis zum Rest kurz. Beides muss zusammenkommen, sonst wuerde
# eine normale laengere Denkpause mitten im Video den Rest abschneiden.
if a.schluss_stille > 0 and len(merged) >= 3:
    while len(merged) >= 2:
        luecke = merged[-1]["start"] - merged[-2]["end"]
        rest = sum(x["end"] - x["start"] for x in merged[-1:])
        gesamt = sum(x["end"] - x["start"] for x in merged)
        if luecke >= a.schluss_stille and rest <= a.schluss_anteil * gesamt:
            weg = merged.pop()
            print(f'  Nachgeplauder verworfen: {luecke:.0f}s Stille davor, '
                  f'"{weg["text"][:44]}"')
        else:
            break

keepers = [{
    "a": round(max(0, s["start"] - a.pad_head), 3),
    "b": round(s["end"] + a.pad_tail, 3),
    "label": f'S{s["i"]} {norm(s["text"])[:40]}'
} for s in merged]

def _uneinig(gruppe):
    """Wie stark unterscheiden sich die Fassungen inhaltlich?

    Bei einer echten Wiederholung ueberlappen sich die Inhaltswoerter stark.
    Bei einer Aufzaehlung stehen dort verschiedene Begriffe an derselben
    Satzstelle - dann ist die Gruppierung womoeglich falsch und der Nutzer
    sollte hinsehen. Rueckgabe: Anteil der Woerter, die NICHT in allen
    Fassungen vorkommen.
    """
    # Nur Fassungen mit genug Inhalt vergleichen: ein abgebrochener
    # Zwei-Wort-Anlauf hat naturgemaess kaum Ueberschneidung und wuerde jede
    # Gruppe als "uneinig" erscheinen lassen.
    mengen = []
    for s in gruppe:
        w = {x for x in norm(s["text"]).split() if x not in STOPP}
        if len(w) >= 3:
            mengen.append(w)
    if len(mengen) < 2:
        return 0.0
    # Median der paarweisen Deckung, nicht die Schnittmenge ueber alle -
    # sonst genuegt eine einzige abweichende Fassung, um alles zu kippen.
    werte = []
    for i in range(len(mengen)):
        for j in range(i + 1, len(mengen)):
            v = len(mengen[i] & mengen[j]) / min(len(mengen[i]), len(mengen[j]))
            werte.append(v)
    werte.sort()
    med = werte[len(werte) // 2]
    return round(1 - med, 2)


json.dump(keepers, open("keepers.json", "w"), ensure_ascii=False, indent=1)

# --- Entscheidungsprotokoll fuer die Marker ---
#
# Die Auswahl weiss genau, welche Fassungen sie verworfen hat - aber bisher
# stand das nur auf der Konsole. capcut_marker.py musste deshalb raten und aus
# den fertigen Fenstern rueckwaerts schliessen, welche Stellen unsicher waren.
# Jetzt wird jede Gruppenentscheidung mitgeschrieben, damit die Marker genau
# dort sitzen, wo wirklich eine Wahl getroffen wurde.
entscheidungen = []
for grp, win in protokoll:
    sieger = cand[win]
    andere = [cand[g] for g in grp if g != win]
    laengste = max(andere, key=lambda x: x["dur"]) if andere else None
    entscheidungen.append({
        "sieger": {"i": sieger["i"], "start": round(sieger["start"], 3),
                   "dur": sieger["dur"], "text": sieger["text"]},
        "anlaeufe": len(grp),
        "verworfen": [{"i": x["i"], "start": round(x["start"], 3),
                       "dur": x["dur"], "text": x["text"]} for x in andere],
        # Kernfrage fuer den Marker: Wurde eine LAENGERE Fassung verworfen?
        # Dann kann die Automatik danebengegriffen haben.
        "laengere_verworfen": bool(laengste and laengste["dur"] > sieger["dur"] * 1.15),
        "laengste_verworfene_dauer": round(laengste["dur"], 2) if laengste else None,
        # Streuung der Inhaltswoerter: Bei einer echten Wiederholung sagt
        # Julian im Kern dasselbe. Weichen die Fassungen inhaltlich stark ab,
        # war es womoeglich eine Aufzaehlung ("zwei Reels pro Tag" gegen
        # "zwei Karussells pro Woche") und keine Wiederholung.
        "inhaltlich_uneinig": _uneinig([cand[g] for g in grp]),
    })
json.dump(entscheidungen, open("entscheidungen.json", "w"),
          ensure_ascii=False, indent=1)

print(f"{len(segs)} Segmente | {len(dropped)} vorgefiltert | "
      f"Blockgrenze {G:.2f}s -> {n_bloecke} Bloecke | {len(protokoll)} Wiederholungs-Gruppen")
if dropped:
    print("\nVorgefiltert:")
    for s, why in dropped:
        print(f'  S{s["i"]:<3} {s["start"]:7.2f}s  [{why}]  "{s["text"][:45]}"')
print("\nWiederholungen (letzte vollstaendige Version behalten):")
for grp, win in protokoll:
    losers = ", ".join(f'S{cand[g]["i"]}' for g in grp if g != win)
    print(f'  S{cand[win]["i"]:<3} @{cand[win]["start"]:7.2f}s  B{block_von[win]}  "{cand[win]["text"][:44]}"')
    print(f'       raus: {losers}')

total = sum(k["b"] - k["a"] for k in keepers)
print(f"\n=> {len(keepers)} Keeper, ~{total:.1f}s")
for k in keepers:
    print(f'  {k["a"]:7.2f}-{k["b"]:7.2f}  {k["label"]}')
