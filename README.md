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
| **Mac** | Apple Silicon (M1-M4) oder Intel. Auf M-Chips läuft die Transkription rund zehnmal schneller. |
| **CapCut** | Installiert und **mindestens einmal gestartet**. Beim ersten Start legt es den Projektordner an, den dieses Werkzeug braucht. |
| **Claude Code** | Im Terminal (`claude`). Die Web-Version reicht nicht - es müssen Programme auf deinem Rechner laufen. |
| **Google-Drive-Ordner** | Freigegeben für „Jeder mit dem Link". |
| **Platz** | Rechne mit dem Doppelten deiner Rohmaterial-Größe. |

Du brauchst **keine** Programmierkenntnisse. Du kopierst Befehle und drückst Enter.

---

## 2. Einrichtung

Einmalig, dauert etwa 15 Minuten - davon 12 Minuten Warten.

### Schritt 1: Terminal öffnen

`Cmd + Leertaste` → „Terminal" tippen → Enter.

### Schritt 2: Paket laden

```bash
git clone https://github.com/gxrtner/autodm-videoeditor.git ~/.claude/skills/autodm-videoeditor
```

### Schritt 3: Einrichtung starten

```bash
bash ~/.claude/skills/autodm-videoeditor/SETUP.sh
```

Das Skript prüft deinen Rechner und installiert, was fehlt - alles im
Benutzerverzeichnis, ohne Systemänderung und ohne Passwort:

- **ffmpeg** (~80 MB) - schneidet Video und Ton
- **numpy** - für die Tonanalyse
- **mlx-whisper** oder **faster-whisper** - erkennt gesprochene Sprache
- **rclone** (~20 MB) - lädt aus Google Drive

Am Ende fragt es, ob das Sprachmodell (~1,5 GB) gleich geladen werden soll.
**Sag ja**, wenn du gerade Zeit hast - sonst passiert es beim ersten Schnitt
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
2. ordnet Tonaufnahmen den Videos zu - auch eine zweite Kamera, wenn du so
   filmst; genommen wird die Spur mit dem besseren Ton
3. schneidet und schlägt je Aussage einen Take vor
4. **liest die Auswahl gegen und korrigiert sie** - das ist der Schritt, der
   den Unterschied macht, siehe unten
5. zeigt dir, was es geändert hat
6. legt pro Video ein CapCut-Projekt an, mit Markern auf den Reststellen

**Du:** öffnest CapCut und feilst nach.

### Warum Claude die Auswahl gegenliest

Die Skripte entscheiden auf Textähnlichkeit und Dauer. Was ein Satz *bedeutet*,
sehen sie nicht. Gemessen an 21 von Hand korrigierten Läufen trifft der
Vorschlag rund 85 Prozent der richtigen Takes - die fehlenden 15 Prozent sind
der Unterschied zwischen einem Video, das du posten kannst, und einem, das
mitten im Satz aufhört.

Deshalb hält die Pipeline nach dem Schnitt an. Claude liest den Schnitt als
durchgehenden Text, sucht Fragmente, Wiederholungen, falsch gewählte Takes und
fehlende Aussagen, korrigiert `keepers.json` und sagt dir, was es geändert hat.
Erst danach entsteht das Projekt.

Das ist kein optionaler Zwischenschritt, den man überspringen kann. Es ist der
Grund, warum das Ergebnis brauchbar wird.

### Beim ersten Mal: Google Drive verbinden

Claude führt dich durch `rclone config`. Wichtig dabei:

- Typ: **`drive`**
- `client_id` und `client_secret`: **leer lassen** (rclone bringt eigene mit)
- Scope: **`2`** (nur lesen - sicherer)
- Auto-Config: **`y`** - dann öffnet sich der Browser für den Google-Login

Das ist einmalig. Danach kennt rclone deinen Drive.

### Wie lange dauert es?

| Schritt | Zeit |
|---|---|
| Download | je nach Leitung, bei 3 GB etwa 5-10 Min |
| Tonzuordnung | wenige Sekunden je Video |
| Schnitt | ~15 Sek je Video auf M-Chip, deutlich länger auf Intel |
| Auswahl gegenlesen | 1-2 Min je Video |
| Projekt anlegen | wenige Sekunden mit `--original`, sonst 1-2 Min |

### Wichtig: CapCut muss geschlossen sein

Bevor Claude Projekte anlegt, muss CapCut mit **Cmd + Q** beendet sein - Fenster
schließen reicht nicht.

Der Grund: CapCut hält ein geöffnetes Projekt im Arbeitsspeicher und schreibt es
beim Beenden zurück auf die Festplatte. Läuft es währenddessen, überschreibt es
das neu angelegte Projekt wieder. Die Skripte brechen deshalb ab, statt still
ins Leere zu arbeiten.

---

## 4. Die Marker

Nachdem Claude die Auswahl gegengelesen hat, bleiben Stellen übrig, die auch
Claude nicht entscheiden kann - etwa welche von zwei gleichwertigen Fassungen
dir besser gefällt. Dort sitzen die Marker. Du springst in CapCut von Marker zu
Marker, normalerweise vier bis acht Stellen.

**Sie sind ein Hinweis, keine vollständige Fehlerliste.** Sieh dir das Video
einmal ganz an, bevor du postest.

Marker siehst du in CapCut als kleine Fähnchen über der Zeitleiste. Sie heißen
`! grund: info`.

| Marker | Was er bedeutet | Was du prüfst |
|---|---|---|
| `! wahl` | Aus mehreren Anläufen wurde gewählt, und eine deutlich längere Fassung flog raus | Der bessere Take liegt noch im Rohmaterial - reinziehen |
| `! echo` | Innerhalb eines Fensters wird derselbe Satz zweimal gesprochen | Ohne Pause neu angesetzt - hier von Hand trennen |
| `! ungeprüft` | Das Fenster hatte keine Vergleichsfassung, die Auswahl konnte nichts abwägen | Sieht nach Bruchstück aus - gehört das rein? |
| `! abbruch` | Der Satz bricht mitten drin ab | Fehlt hinten etwas? |
| `! dicht` | Kurz vorher lag ein sehr ähnlicher Take | Ist der behaltene wirklich der bessere? |
| `! aufzählung` | Mehrere Fassungen wurden zusammengefasst, unterscheiden sich aber inhaltlich | Waren das eigene Punkte statt Wiederholungen? |
| `! lücke` | Davor wurde viel Sprache verworfen | Fehlt eine ganze Aussage? |
| `! kurz` | Fenster unter 0,8 Sekunden | Ist das eine Aussage oder nur ein Fragment? |

Alles zwischen den Markern hat die Automatik als eindeutig eingestuft. Das
stimmt meistens - aber „meistens" ist nicht „immer". Wenn dir beim Ansehen etwas
auffällt, korrigier es einfach auf der Zeitleiste.

---

## 5. Wie es funktioniert

Kurz erklärt, damit du die Ergebnisse einordnen kannst.

### Tonzuordnung über den Klang

Filmst du Bild und Ton getrennt (Kamera + Ansteckmikro), muss das Werkzeug
wissen, welche Aufnahme zu welchem Video gehört. Es rät **nicht** anhand der
Dateilänge - das führt in die Irre. Stattdessen vergleicht es den
Lautstärkeverlauf beider Spuren: Wo beide gleichzeitig laut und leise werden,
gehören sie zusammen.

Richtige Paare erreichen einen Wert um 0,85, falsche bleiben unter 0,15. Unter
0,4 bricht das Werkzeug ab und meldet, dass die Aufnahme nicht passt.

Nebenbei fällt der zeitliche Versatz ab - ob das Mikro schon lief, als die
Kamera startete. Damit sitzt der Ton auf dem Bild.

### Schnitt nach Wellenform, nicht nach Transkript

Zuerst wird an der Tonspur gemessen, wo gesprochen wird und wo Pause ist. Nur
diese Sprechblöcke werden einzeln transkribiert.

Der Umweg hat einen Grund: Spracherkennung liefert bei mehrfach wiederholten
Sätzen unbrauchbare Zeitangaben - sie überspringt Wiederholungen oder dehnt
einzelne Wörter über die Pausen. Die Wellenform sagt die Wahrheit darüber, wann
jemand spricht.

Damit leise Satzenden nicht abgeschnitten werden, arbeitet die Erkennung mit
zwei Schwellen: Sie steigt bei normaler Lautstärke ein und erst deutlich später
wieder aus.

### Take-Auswahl: blockweise, der letzte brauchbare gewinnt

Du nimmst in Blöcken auf: mehrfach ansetzen, dann eine längere Pause, dann der
nächste Gedanke. Genau so wertet das Werkzeug aus - es bestimmt die Blockgrenze
aus deinen eigenen Pausenlängen und sucht innerhalb eines Blocks die beste
Fassung, statt global Textpaare zu vergleichen.

Innerhalb eines Blocks gewinnt der **letzte Take, der noch vollständig ist**.
Ein Fehlstart am Ende kann also nicht gewinnen, nur weil er der letzte war -
das war früher die häufigste Fehlerquelle. Erkannt wird das über Textähnlichkeit
und gleiche
Satzanfänge - Letzteres aber nur innerhalb von 30 Sekunden.

Diese Zeitgrenze ist wichtig: Parallel gebaute Sätze („Wenn du mehr *Views*
willst…", „Wenn du mehr *Calls* willst…") beginnen identisch, sind aber
verschiedene Aussagen. Ohne die Grenze würden sie fälschlich als Wiederholungen
zusammenfallen.

### Das CapCut-Projekt

CapCuts Projektformat ist nicht dokumentiert. Ein einzelnes Video-Segment hat
rund 49 Felder, ein Material 63 - die meisten sind belanglos, fehlen dürfen sie
trotzdem nicht.

Das Werkzeug erfindet das Format deshalb nicht, sondern **klont** ein echtes,
von CapCut geschriebenes Objekt und tauscht nur Pfade und Zeiten. Als Quelle
dient eines deiner vorhandenen Projekte, oder - wenn du noch keines hast - ein
mitgeliefertes Gerüst.

Alle Medien landen **im Projektordner**. Das ist nicht Ordnungsliebe: macOS gibt
CapCut keinen Zugriff auf beliebige Ordner, extern liegende Dateien erscheinen
als „Kein Zugriff auf die Datei möglich".

Das Video wird als 1080p-Arbeitsfassung abgelegt, nicht in 4K - zum Nachfeilen
reicht das und spart erheblich Platz.

---

## 6. Worauf du achten musst

### CapCut schließen (Cmd + Q)

Siehe oben. Häufigste Fehlerquelle.

### Der Schnitt ist eine Rohfassung

Er nimmt dir den Großteil ab, ersetzt aber nicht das Draufschauen. Die
markierten Stellen sind Pflicht, der Rest ist Kür.

Ein Muster, das die Automatik zuverlässig falsch macht: Wenn du dasselbe Video
**zweimal komplett** durchziehst - erst ein Anlauf mit Abbrüchen, dann sauber -
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
| `CapCut läuft - bitte mit Cmd+Q beenden` | Genau das. Fenster schließen reicht nicht. |
| `Kein CapCut-Projekt mit Video-Segment gefunden` | CapCut starten, irgendein Video auf die Zeitleiste ziehen, speichern, CapCut beenden. Danach nochmal. |
| `Mikro passt nicht zum Video (Güte 0.2x)` | Die Aufnahme gehört zu einem anderen Video, oder eine der Spuren ist stumm. |
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
bash $S/voredit.sh ~/Videos/mein-ordner --auto --original   # Projekte anlegen

# --original referenziert das Quellvideo direkt statt es als 1080p-Arbeits-
# fassung zu kopieren: volle Aufloesung, kein Speicherplatz, und das ganze
# Rohmaterial bleibt im Projekt greifbar. Weglassen nur, wenn das Material
# auf einer externen Platte liegt, auf die CapCut keinen Zugriff hat.
```

### Die Zwischendateien

Je Video entsteht ein Ordner `<name>_edit`:

| Datei | Inhalt |
|---|---|
| `audio16k.wav` | die extrahierte Tonspur |
| `segments_wave.json` | alle Sprechblöcke mit Text und Zeiten |
| `keepers.json` | die ausgewählten Fenster - **hier korrigierst du von Hand** |
| `entscheidungen.json` | je Gruppe: welcher Take gewann, welche verworfen wurden |
| `verworfen_vorfilter.json` | was schon vor der Auswahl aussortiert wurde |

Willst du den Schnitt ändern, bearbeite `keepers.json` (jeder Eintrag ist ein
Fenster mit `a` = Start und `b` = Ende in Sekunden) und lass `--auto --original` erneut
laufen.

### Stellschrauben

```bash
python3 $S/segment.py audio16k.wav --gap 0.35 --thr 0.005
```

- `--gap` - wie lange eine Pause sein muss, damit ein neuer Block beginnt
- `--thr` - ab welcher Lautstärke etwas als Sprache gilt

```bash
python3 $S/pick_takes.py --sim 0.62
```

- `--sim` - ab welcher Textähnlichkeit zwei Takes als derselbe Satz gelten
- `--window` - in welchem Zeitfenster gleiche Satzanfänge als Wiederholung zählen

### Marker nachträglich setzen

```bash
python3 $S/capcut_marker.py "<projektname>" --edit <name>_edit --trocken
```

`--trocken` zeigt nur an, was es finden würde, ohne zu schreiben.

---

## Was dieses Werkzeug **nicht** macht

Untertitel, Text-Einblendungen, B-Roll, Musik, Farbkorrektur, Export. Es
liefert einen sauberen Rohschnitt als Ausgangspunkt - der Rest ist deine
Handschrift in CapCut.
