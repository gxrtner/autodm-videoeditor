---
name: autodm-videoeditor
description: Schneidet Rohmaterial aus einem Google-Drive-Link automatisch und legt daraus ein fertiges CapCut-Projekt an. Mehrfach aufgenommene Sätze werden auf den besten Take reduziert, Pausen, Fehlstarts und Regie-Ansagen fliegen raus. Getrennt aufgenommener Ton (Ansteckmikro oder zweite Kamera) wird automatisch zugeordnet und synchronisiert. TRIGGER wenn der Nutzer Rohmaterial schneiden lassen will - "schneide mein Video", "hier ist der Drive-Link", "mach mir ein CapCut-Projekt", "Rohmaterial cutten", oder wenn er einfach einen Drive-Link schickt.
---

# AutoDM Videoeditor

Drive-Link rein, geschnittenes CapCut-Projekt raus. Nur macOS.

## Das Wichtigste zuerst

**Die Take-Auswahl wird geprüft, bevor das Projekt gebaut wird. Immer.**

Die Skripte liefern einen Vorschlag, keine fertige Auswahl. Sie entscheiden auf
Textähnlichkeit und Dauer - was ein Satz bedeutet, sehen sie nicht. Gemessen an
21 von Hand korrigierten Läufen trifft der Vorschlag rund 85 Prozent der
richtigen Takes. Die fehlenden 15 Prozent sind der Unterschied zwischen einem
Video, das man posten kann, und einem, das mitten im Satz aufhört.

Diesen Schritt gab es früher auch schon - er fand nur im Kopf statt und wurde
beim Verpacken vergessen. Er steht jetzt hier, weil er der Grund ist, warum das
Ergebnis gut wird.

## Ablauf

### 1. Material holen

Der Nutzer gibt einen Drive-Link. Ordner-ID ist der Teil zwischen `/folders/`
und `?`.

```bash
rclone lsl gdrive: --drive-root-folder-id "<ID>"          # erst schauen
rclone copy gdrive: ~/Videos/<name> --drive-root-folder-id "<ID>" -P
```

Ist `gdrive:` noch nicht eingerichtet, den Nutzer durch `rclone config` führen:
neues Remote, Typ `drive`, client_id und client_secret **leer lassen** (rclone
bringt eigene mit), scope `2` (drive.readonly), Auto-Config `y` - dann öffnet
sich der Browser für den Google-Login.

### 2. Schneiden lassen

```bash
bash <paket>/scripts/voredit.sh "~/Videos/<name>"
```

Das ordnet Tonspuren zu, findet Sprechblöcke, transkribiert sie und schlägt je
Aussage einen Take vor. Danach hält es an - das ist Absicht.

**Zwei Kameras:** Wird der Ton mit einer zweiten Kamera aufgenommen, erkennt
das Skript das selbst und nimmt die Spur mit dem besseren Pegel. Nur wenn die
Pegel weniger als 6 dB auseinanderliegen, gilt es als zwei gleichwertige
Perspektiven und beide bleiben eigene Videos.

### 3. Auswahl prüfen - der eigentliche Schritt

Je Video liegen in `<name>_edit/` diese Dateien:

| Datei | Inhalt |
|---|---|
| `segments_wave.json` | ALLE Rohsegmente mit Text und Zeiten |
| `keepers.json` | die vorgeschlagene Auswahl |
| `entscheidungen.json` | je Gruppe: welcher Take gewann, welche verworfen wurden |
| `verworfen_vorfilter.json` | was schon vor der Auswahl aussortiert wurde |

**Lies den Schnitt als durchgehenden Text.** Ordne die Keeper nach Zeit, sammle
je Fenster die enthaltenen Rohsegmente und setze deren Text aneinander. Genau
das hört der Nutzer später. Wenn es sich nicht flüssig liest, stimmt etwas
nicht.

Dann gezielt suchen:

1. **Fragmente** - Bruchstücke ohne Aussage ("anstatt auf", "und Leads dann").
2. **Wiederholungen** - zwei Fenster sagen dasselbe. Prüfe besonders den
   Anfang: Hook-Varianten liegen oft weit auseinander und werden deshalb nicht
   als Wiederholung erkannt.
3. **Falscher Take** - ein Fenster enthält einen Versprecher oder Abbruch,
   obwohl im Rohmaterial eine saubere Fassung derselben Aussage liegt. Dafür
   ist `entscheidungen.json` da: das Feld `laengere_verworfen` markiert genau
   diese Fälle. Aber verlass dich nicht darauf - durchsuche
   `segments_wave.json` selbst nach ähnlichen Formulierungen.
4. **Fehlende Aussagen** - steht in `verworfen_vorfilter.json` etwas, das ins
   Video gehört? Ein kurzer Call-to-Action ("Folge mir für mehr") sieht für
   den Filter aus wie ein Fragment.
5. **Verdrehte Reihenfolge** - ein Nebensatz, der vor seinem Hauptsatz steht.
   Die Fenster sind nach Aufnahmezeit sortiert, nicht nach Sinn.

**Korrekturen einarbeiten:** `keepers.json` neu schreiben. Format ist eine
Liste von `{"a": start, "b": ende, "label": "..."}` in Sekunden auf der
Zeitachse des Videos. Ein Fenster darf frei gesetzt werden - es muss nicht auf
einer Segmentgrenze liegen. Polster: 0,06s vorne, 0,14s hinten.

```python
import json
segs = json.load(open("<name>_edit/segments_wave.json"))
KEEP = [5, 8, 10, 11, 16]          # die gewählten Segment-Nummern
s = {x["i"]: x for x in segs}
json.dump([{"a": round(s[i]["start"] - 0.06, 3),
            "b": round(s[i]["end"] + 0.14, 3),
            "label": f'S{i} {s[i]["text"][:40]}'} for i in KEEP],
          open("<name>_edit/keepers.json", "w"), ensure_ascii=False, indent=1)
```

**Dem Nutzer zeigen, was du geändert hast** - kurz, mit Begründung. Er soll
sehen, dass geprüft wurde, und widersprechen können.

### 4. Projekt anlegen

```bash
bash <paket>/scripts/voredit.sh "~/Videos/<name>" --auto --original
```

Eine vorhandene `keepers.json` wird dabei **nicht** überschrieben - die
geprüfte Auswahl bleibt also erhalten. `--original` referenziert das Quellvideo
direkt statt es als 1080p-Arbeitsfassung zu kopieren: volle Auflösung, kein
Speicherplatz, und das ungeschnittene Rohmaterial bleibt im Projekt greifbar.
Weglassen, wenn das Material auf einer externen Platte liegt, auf die CapCut
keinen Zugriff hat.

**CapCut muss dabei geschlossen sein.**

### 5. Übergeben

Dem Nutzer sagen: CapCut starten, Projekt öffnen, Marker abklappern. Und
ehrlich dazusagen, was die Marker sind - Hinweise auf Stellen, an denen die
Automatik unsicher war, keine vollständige Fehlerliste.

## Die Marker

| Marker | Was prüfen |
|---|---|
| `wahl` | Aus mehreren Anläufen wurde gewählt, und eine deutlich längere Fassung flog raus. Der bessere Take liegt noch im Rohmaterial. |
| `echo` | Innerhalb eines Fensters wird derselbe Satz zweimal gesprochen. Ohne Pause neu angesetzt - muss von Hand getrennt werden. |
| `ungeprüft` | Das Fenster hatte keine Vergleichsfassung, die Auswahl konnte hier nichts abwägen. Sieht nach Bruchstück aus. |
| `abbruch` | Der Satz bricht mitten drin ab. |
| `dicht` | Kurz davor lag ein sehr ähnlicher Take. Möglicherweise wurde der falsche behalten. |
| `aufzählung` | Mehrere Fassungen wurden zusammengefasst, unterscheiden sich aber inhaltlich - womöglich waren es eigene Punkte, keine Wiederholung. |
| `lücke` | Davor wurde viel Sprache verworfen. Dort könnte eine Aussage fehlen. |
| `kurz` | Sehr kurzes Fenster, oft nur ein Fragment. |

## Regeln

- **CapCut schließen, bevor geschrieben wird.** Es hält das Projekt im
  Speicher und überschreibt beim Beenden. Die Skripte brechen sonst ab.
- **Nichts löschen.** Erzeugt werden immer NEUE Projekte, bestehende bleiben
  unangetastet.
- **Am Bild wird nichts verändert.** Kein Zoom, kein Ausschnitt, keine
  Verschiebung - der Rohschnitt liefert das Bild so, wie es gefilmt wurde.
  Bildgestaltung ist Sache des Nutzers.
- **Ohne externen Ton** funktioniert alles genauso, nur entfällt die
  Ton-Zuordnung. Nicht abbrechen, wenn keine Audiodateien dabei sind.

## Wenn etwas klemmt

| Problem | Ursache |
|---|---|
| "CapCut läuft" | CapCut mit Cmd+Q beenden, nicht nur Fenster schließen |
| "Kein CapCut-Projekt gefunden" | CapCut einmal starten, leeres Projekt anlegen, speichern |
| Schnitt viel zu kurz | Rohmaterial hat parallel gebaute Sätze - Auswahl in `<name>_edit/keepers.json` prüfen |
| Ton passt nicht | Güte unter 0.4 - vermutlich gehört die Aufnahme zu einem anderen Video |
| Satzenden fehlen | Aufnahme zu leise. Die Meldung "[1/6] Pegel: Sprachmedian ..." in der Ausgabe prüfen - liegt der Wert unter 0.005, ist der Ton für die Analyse zu schwach |
| Modell lädt ewig | Beim ersten Mal ca. 1.5 GB. Danach liegt es im Cache. |
| "Kein Zugriff auf die Datei" in CapCut | `--original` weglassen, dann werden die Medien ins Projekt kopiert |
