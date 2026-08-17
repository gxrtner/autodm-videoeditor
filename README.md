# AutoDM Videoeditor

Rohmaterial aus einem Google-Drive-Link wird automatisch geschnitten und als
fertiges CapCut-Projekt abgelegt. Mehrfach aufgenommene Sätze werden auf den
letzten vollständigen Take reduziert, Pausen und Fehlstarts fliegen raus.
Getrennt aufgenommener Mikro-Ton wird zugeordnet und synchronisiert.

**Nur macOS.** Windows folgt später.

---

## Inhalt

1. [Was du brauchst](#1-was-du-brauchst)
2. [Einrichtung](#2-einrichtung)
3. [Ein Video schneiden](#3-ein-video-schneiden)
4. [Die Marker](#4-die-marker)
5. [Wie es funktioniert](#5-wie-es-funktioniert)
6. [Worauf du achten musst](#6-worauf-du-achten-musst)
7. [Wenn etwas klemmt](#7-wenn-etwas-klemmt)
8. [Für Fortgeschrittene](#8-für-fortgeschrittene)

---

## 1. Was du brauchst

| | |
|---|---|
| **Mac** | Apple Silicon (M1–M4) oder Intel. Auf M-Chips läuft die Transkription rund zehnmal schneller. |
| **CapCut** | Installiert und **mindestens einmal gestartet**. Beim ersten Start legt es den Projektordner an, den dieses Werkzeug braucht. |
| **Claude Code** | Im Terminal (`claude`). Die Web-Version reicht nicht — es müssen Programme auf deinem Rechner laufen. |
| **Google-Drive-Ordner** | Freigegeben für „Jeder mit dem Link". |
| **Platz** | Rechne mit dem Doppelten deiner Rohmaterial-Größe. |

Du brauchst **keine** Programmierkenntnisse. Du kopierst Befehle und drückst Enter.

---

## 2. Einrichtung

Einmalig, dauert etwa 15 Minuten — davon 12 Minuten Warten.

### Schritt 1: Terminal öffnen

`Cmd + Leertaste` → „Terminal" tippen → Enter.

### Schritt 2: Paket laden

```bash
git clone <REPO-URL> ~/.claude/skills/autodm-videoeditor
```

### Schritt 3: Einrichtung starten

```bash
bash ~/.claude/skills/autodm-videoeditor/SETUP.sh
```

Das Skript prüft deinen Rechner und installiert, was fehlt — alles im
Benutzerverzeichnis, ohne Systemänderung und ohne Passwort:

- **ffmpeg** (~80 MB) — schneidet Video und Ton
- **numpy** — für die Tonanalyse
- **mlx-whisper** oder **faster-whisper** — erkennt gesprochene Sprache
- **rclone** (~20 MB) — lädt aus Google Drive

Am Ende fragt es, ob das Sprachmodell (~1,5 GB) gleich geladen werden soll.
**Sag ja**, wenn du gerade Zeit hast — sonst passiert es beim ersten Schnitt
und wirkt dort wie ein Hänger.

### Schritt 4: Claude neu starten

Claude Code einmal beenden und neu öffnen, damit es das Paket findet.

### Schritt 5: Loslegen

Öffne `START.md` im Paketordner, kopiere den Text im Kasten und füge ihn in
Claude Code ein. Ab hier führt Claude dich.

---

## 3. Ein Video schneiden

### Der Ablauf

**Du:** gibst Claude den Drive-Link.

**Claude:**

1. lädt das Rohmaterial herunter
2. ordnet Tonaufnahmen den Videos zu
3. schneidet
4. zeigt dir die Auswahl und fragt, ob es weitermachen soll
5. legt pro Video ein CapCut-Projekt an

**Du:** öffnest CapCut und feilst nach.

### Beim ersten Mal: Google Drive verbinden

Claude führt dich durch `rclone config`. Wichtig dabei:

- Typ: **`drive`**
- `client_id` und `client_secret`: **leer lassen** (rclone bringt eigene mit)
- Scope: **`2`** (nur lesen — sicherer)
- Auto-Config: **`y`** — dann öffnet sich der Browser für den Google-Login

Das ist einmalig. Danach kennt rclone deinen Drive.

### Wie lange dauert es?

| Schritt | Zeit |
|---|---|
| Download | je nach Leitung, bei 3 GB etwa 5–10 Min |
| Tonzuordnung | wenige Sekunden je Video |
| Schnitt | ~15 Sek je Video auf M-Chip, deutlich länger auf Intel |
| Projekt anlegen | 1–2 Min je Video (die Arbeitsfassung wird berechnet) |

### Wichtig: CapCut muss geschlossen sein

Bevor Claude Projekte anlegt, muss CapCut mit **Cmd + Q** beendet sein — Fenster
schließen reicht nicht.

Der Grund: CapCut hält ein geöffnetes Projekt im Arbeitsspeicher und schreibt es
beim Beenden zurück auf die Festplatte. Läuft es währenddessen, überschreibt es
das neu angelegte Projekt wieder. Die Skripte brechen deshalb ab, statt still
ins Leere zu arbeiten.

---

## 4. Die Marker

**Das ist der wichtigste Abschnitt.** Der Schnitt läuft vollautomatisch und
liegt nicht immer richtig. Statt das ganze Video zu prüfen, springst du in
CapCut von Marker zu Marker — normalerweise drei bis sieben Stellen.

Marker siehst du in CapCut als kleine Fähnchen über der Zeitleiste. Sie heißen
`! grund: info`.

| Marker | Was er bedeutet | Was du prüfst |
|---|---|---|
| `! dicht` | Kurz vorher lag ein sehr ähnlicher Take | Ist der behaltene wirklich der bessere? |
| `! abbruch` | Der Satz bricht mitten drin ab | Fehlt hinten etwas? |
| `! luecke` | Davor wurde viel Rohmaterial verworfen | Fehlt eine ganze Aussage? |
| `! kurz` | Fenster unter 0,8 Sekunden | Ist das eine Aussage oder nur ein Fragment? |
| `! doppelt` | Zwei Fenster beginnen fast gleich | Steht etwas doppelt drin? |

Alles zwischen den Markern hat die Automatik als eindeutig eingestuft. Das
stimmt meistens — aber „meistens" ist nicht „immer". Wenn dir beim Ansehen etwas
auffällt, korrigier es einfach auf der Zeitleiste.

---

## 5. Wie es funktioniert

Kurz erklärt, damit du die Ergebnisse einordnen kannst.

### Tonzuordnung über den Klang

Filmst du Bild und Ton getrennt (Kamera + Ansteckmikro), muss das Werkzeug
wissen, welche Aufnahme zu welchem Video gehört. Es rät **nicht** anhand der
Dateilänge — das führt in die Irre. Stattdessen vergleicht es den
Lautstärkeverlauf beider Spuren: Wo beide gleichzeitig laut und leise werden,
gehören sie zusammen.

Richtige Paare erreichen einen Wert um 0,85, falsche bleiben unter 0,15. Unter
0,4 bricht das Werkzeug ab und meldet, dass die Aufnahme nicht passt.

Nebenbei fällt der zeitliche Versatz ab — ob das Mikro schon lief, als die
Kamera startete. Damit sitzt der Ton auf dem Bild.

### Schnitt nach Wellenform, nicht nach Transkript

Zuerst wird an der Tonspur gemessen, wo gesprochen wird und wo Pause ist. Nur
diese Sprechblöcke werden einzeln transkribiert.

Der Umweg hat einen Grund: Spracherkennung liefert bei mehrfach wiederholten
Sätzen unbrauchbare Zeitangaben — sie überspringt Wiederholungen oder dehnt
einzelne Wörter über die Pausen. Die Wellenform sagt die Wahrheit darüber, wann
jemand spricht.

Damit leise Satzenden nicht abgeschnitten werden, arbeitet die Erkennung mit
zwei Schwellen: Sie steigt bei normaler Lautstärke ein und erst deutlich später
wieder aus.

### Take-Auswahl: der letzte vollständige gewinnt

Sprichst du einen Satz mehrfach, behält das Werkzeug den **letzten
vollständigen**. Erkannt wird das über Textähnlichkeit und gleiche
Satzanfänge — Letzteres aber nur innerhalb von 30 Sekunden.

Diese Zeitgrenze ist wichtig: Parallel gebaute Sätze („Wenn du mehr *Views*
willst…", „Wenn du mehr *Calls* willst…") beginnen identisch, sind aber
verschiedene Aussagen. Ohne die Grenze würden sie fälschlich als Wiederholungen
zusammenfallen.

### Das CapCut-Projekt

CapCuts Projektformat ist nicht dokumentiert. Ein einzelnes Video-Segment hat
rund 49 Felder, ein Material 63 — die meisten sind belanglos, fehlen dürfen sie
trotzdem nicht.

Das Werkzeug erfindet das Format deshalb nicht, sondern **klont** ein echtes,
von CapCut geschriebenes Objekt und tauscht nur Pfade und Zeiten. Als Quelle
dient eines deiner vorhandenen Projekte, oder — wenn du noch keines hast — ein
mitgeliefertes Gerüst.

Alle Medien landen **im Projektordner**. Das ist nicht Ordnungsliebe: macOS gibt
CapCut keinen Zugriff auf beliebige Ordner, extern liegende Dateien erscheinen
als „Kein Zugriff auf die Datei möglich".

Das Video wird als 1080p-Arbeitsfassung abgelegt, nicht in 4K — zum Nachfeilen
reicht das und spart erheblich Platz.

---

## 6. Worauf du achten musst

### CapCut schließen (Cmd + Q)

Siehe oben. Häufigste Fehlerquelle.

### Der Schnitt ist eine Rohfassung

Er nimmt dir den Großteil ab, ersetzt aber nicht das Draufschauen. Die
markierten Stellen sind Pflicht, der Rest ist Kür.

Ein Muster, das die Automatik zuverlässig falsch macht: Wenn du dasselbe Video
**zweimal komplett** durchziehst — erst ein Anlauf mit Abbrüchen, dann sauber —
mischt sie manchmal beide Durchläufe. Sag Claude in dem Fall, dass es den
zweiten Durchlauf nehmen soll.

### Externe Festplatte oder Speicherkarte

Liegt dein Rohmaterial auf einer Karte, muss sie bis zum Ende gesteckt bleiben.
Die fertigen Projekte sind danach unabhängig.

### Platz auf der Festplatte

4K-Material ist groß: eine Minute belegt rund 400 MB. Bei 30 Minuten Rohmaterial
sind das 12 GB, plus Arbeitsfassungen. Prüf vorher mit `df -h ~`.

### Bestehende Projekte

Es werden immer **neue** Projekte angelegt. Deine vorhandenen bleiben
unangetastet.

---

## 7. Wenn etwas klemmt

| Meldung / Symptom | Ursache und Lösung |
|---|---|
| `CapCut laeuft — bitte mit Cmd+Q beenden` | Genau das. Fenster schließen reicht nicht. |
| `Kein CapCut-Projekt mit Video-Segment gefunden` | CapCut starten, irgendein Video auf die Zeitleiste ziehen, speichern, CapCut beenden. Danach nochmal. |
| `Mikro passt nicht zum Video (Guete 0.2x)` | Die Aufnahme gehört zu einem anderen Video, oder eine der Spuren ist stumm. |
| In CapCut: „Kein Zugriff auf die Datei möglich" | Eine Datei liegt außerhalb des Projektordners. Claude sagen, dass er sie hineinkopieren soll. |
| Schnitt ist viel zu kurz | Vermutlich parallel gebaute Sätze. Claude bitten, die Take-Auswahl zu prüfen. |
| Modell lädt „ewig" | Beim ersten Mal ~1,5 GB. Danach liegt es im Cache und startet sofort. |
| `command not found: python3` | Xcode-Kommandozeilenwerkzeuge fehlen: `xcode-select --install` |
| Projekt taucht in CapCut nicht auf | CapCut war beim Anlegen offen. Beenden, Schritt wiederholen. |

---

## 8. Für Fortgeschrittene

### Direkt auf der Kommandozeile

```bash
S=~/.claude/skills/autodm-videoeditor/scripts

bash $S/voredit.sh ~/Videos/mein-ordner            # schneiden, dann Stopp
bash $S/voredit.sh ~/Videos/mein-ordner --auto     # Projekte anlegen
```

### Die Zwischendateien

Je Video entsteht ein Ordner `<name>_edit`:

| Datei | Inhalt |
|---|---|
| `audio16k.wav` | die extrahierte Tonspur |
| `segments_wave.json` | alle Sprechblöcke mit Text und Zeiten |
| `keepers.json` | die ausgewählten Fenster — **hier korrigierst du von Hand** |

Willst du den Schnitt ändern, bearbeite `keepers.json` (jeder Eintrag ist ein
Fenster mit `a` = Start und `b` = Ende in Sekunden) und lass `--auto` erneut
laufen.

### Stellschrauben

```bash
python3 $S/segment.py audio16k.wav --gap 0.35 --thr 0.005
```

- `--gap` — wie lange eine Pause sein muss, damit ein neuer Block beginnt
- `--thr` — ab welcher Lautstärke etwas als Sprache gilt

```bash
python3 $S/pick_takes.py --sim 0.68 --window 30
```

- `--sim` — ab welcher Textähnlichkeit zwei Takes als derselbe Satz gelten
- `--window` — in welchem Zeitfenster gleiche Satzanfänge als Wiederholung zählen

### Marker nachträglich setzen

```bash
python3 $S/capcut_marker.py "<projektname>" --edit <name>_edit --trocken
```

`--trocken` zeigt nur an, was es finden würde, ohne zu schreiben.

---

## Was dieses Werkzeug **nicht** macht

Untertitel, Text-Einblendungen, B-Roll, Musik, Farbkorrektur, Export. Es
liefert einen sauberen Rohschnitt als Ausgangspunkt — der Rest ist deine
Handschrift in CapCut.
