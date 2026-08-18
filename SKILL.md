---
name: autodm-videoeditor
description: Schneidet Rohmaterial aus einem Google-Drive-Link automatisch und legt daraus ein fertiges CapCut-Projekt an. Mehrfach aufgenommene Sätze werden auf den letzten vollständigen Take reduziert, Pausen und Fehlstarts fliegen raus. Getrennt aufgenommener Mikro-Ton wird automatisch zugeordnet und synchronisiert. TRIGGER wenn der Nutzer Rohmaterial schneiden lassen will - "schneide mein Video", "hier ist der Drive-Link", "mach mir ein CapCut-Projekt", "Rohmaterial cutten", oder wenn er einfach einen Drive-Link schickt.
---

# AutoDM Videoeditor

Drive-Link rein, geschnittenes CapCut-Projekt raus. Nur macOS.

## Ablauf

**1. Material holen**

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

**2. Schneiden**

```bash
bash <paket>/scripts/voredit.sh "~/Videos/<name>"
```

Das ordnet Tonspuren zu, findet Sprechblöcke, transkribiert sie und wählt je
Aussage den letzten vollständigen Take. Danach steht ein Freigabe-Gate.

**3. Projekt anlegen**

```bash
bash <paket>/scripts/voredit.sh "~/Videos/<name>" --auto
```

Je Video ein CapCut-Projekt mit Mikro-Ton als eigener Spur und Markern auf den
unsicheren Stellen. **CapCut muss dabei geschlossen sein.**

**4. Übergeben**

Dem Nutzer sagen: CapCut starten, das Projekt öffnen, und die Marker
abklappern. Die Marker heißen `! grund: info` und stehen genau dort, wo der
automatische Schnitt unsicher war.

## Die Marker verstehen

| Marker | Was prüfen |
|---|---|
| `! dicht` | Kurz davor lag ein sehr ähnlicher Take. Möglicherweise wurde der falsche behalten. |
| `! abbruch` | Der Satz bricht mitten drin ab. |
| `! lücke` | Davor wurde viel Rohmaterial verworfen - dort könnte eine Aussage fehlen. |
| `! kurz` | Sehr kurzes Fenster, oft nur ein Fragment. |
| `! doppelt` | Zwei Fenster beginnen fast gleich - evtl. eine Wiederholung im Schnitt. |

## Regeln

- **CapCut schließen, bevor geschrieben wird.** Es hält das Projekt im
  Speicher und überschreibt beim Beenden. Die Skripte brechen sonst ab.
- **Nichts löschen.** Erzeugt werden immer NEUE Projekte, bestehende bleiben
  unangetastet.
- **Der Schnitt ist eine Rohfassung.** Er nimmt dem Nutzer 90 % der Arbeit ab,
  aber die markierten Stellen muss er ansehen.
- **Ohne externen Ton** funktioniert alles genauso, nur entfällt die
  Ton-Zuordnung. Nicht abbrechen, wenn keine Audiodateien dabei sind.

## Wenn etwas klemmt

| Problem | Ursache |
|---|---|
| "CapCut läuft" | CapCut mit Cmd+Q beenden, nicht nur Fenster schließen |
| "Kein CapCut-Projekt gefunden" | CapCut einmal starten, leeres Projekt anlegen, speichern |
| Schnitt viel zu kurz | Rohmaterial hat parallel gebaute Sätze - Take-Auswahl in `<name>_edit/keepers.json` prüfen |
| Mikro passt nicht | Güte unter 0.4 - vermutlich gehört die Aufnahme zu einem anderen Video |
| Modell lädt ewig | Beim ersten Mal ca. 1.5 GB. Danach liegt es im Cache. |
