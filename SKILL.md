---
name: autodm-videoeditor
description: Schneidet Rohmaterial aus einem Google-Drive-Link automatisch und legt daraus ein fertiges CapCut-Projekt an. Mehrfach aufgenommene Saetze werden auf den letzten vollstaendigen Take reduziert, Pausen und Fehlstarts fliegen raus. Getrennt aufgenommener Mikro-Ton wird automatisch zugeordnet und synchronisiert. TRIGGER wenn der Nutzer Rohmaterial schneiden lassen will — "schneide mein Video", "hier ist der Drive-Link", "mach mir ein CapCut-Projekt", "Rohmaterial cutten", oder wenn er einfach einen Drive-Link schickt.
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

Ist `gdrive:` noch nicht eingerichtet, den Nutzer durch `rclone config` fuehren:
neues Remote, Typ `drive`, client_id und client_secret **leer lassen** (rclone
bringt eigene mit), scope `2` (drive.readonly), Auto-Config `y` — dann oeffnet
sich der Browser fuer den Google-Login.

**2. Schneiden**

```bash
bash <paket>/scripts/voredit.sh "~/Videos/<name>"
```

Das ordnet Tonspuren zu, findet Sprechbloecke, transkribiert sie und waehlt je
Aussage den letzten vollstaendigen Take. Danach steht ein Freigabe-Gate.

**3. Projekt anlegen**

```bash
bash <paket>/scripts/voredit.sh "~/Videos/<name>" --auto
```

Je Video ein CapCut-Projekt mit Mikro-Ton als eigener Spur und Markern auf den
unsicheren Stellen. **CapCut muss dabei geschlossen sein.**

**4. Uebergeben**

Dem Nutzer sagen: CapCut starten, das Projekt oeffnen, und die Marker
abklappern. Die Marker heissen `! grund: info` und stehen genau dort, wo der
automatische Schnitt unsicher war.

## Die Marker verstehen

| Marker | Was pruefen |
|---|---|
| `! dicht` | Kurz davor lag ein sehr aehnlicher Take. Moeglicherweise wurde der falsche behalten. |
| `! abbruch` | Der Satz bricht mitten drin ab. |
| `! luecke` | Davor wurde viel Rohmaterial verworfen — dort koennte eine Aussage fehlen. |
| `! kurz` | Sehr kurzes Fenster, oft nur ein Fragment. |
| `! doppelt` | Zwei Fenster beginnen fast gleich — evtl. eine Wiederholung im Schnitt. |

## Regeln

- **CapCut schliessen, bevor geschrieben wird.** Es haelt das Projekt im
  Speicher und ueberschreibt beim Beenden. Die Skripte brechen sonst ab.
- **Nichts loeschen.** Erzeugt werden immer NEUE Projekte, bestehende bleiben
  unangetastet.
- **Der Schnitt ist eine Rohfassung.** Er nimmt dem Nutzer 90 % der Arbeit ab,
  aber die markierten Stellen muss er ansehen.
- **Ohne externen Ton** funktioniert alles genauso, nur entfaellt die
  Ton-Zuordnung. Nicht abbrechen, wenn keine Audiodateien dabei sind.

## Wenn etwas klemmt

| Problem | Ursache |
|---|---|
| "CapCut laeuft" | CapCut mit Cmd+Q beenden, nicht nur Fenster schliessen |
| "Kein CapCut-Projekt gefunden" | CapCut einmal starten, leeres Projekt anlegen, speichern |
| Schnitt viel zu kurz | Rohmaterial hat parallel gebaute Saetze — Take-Auswahl in `<name>_edit/keepers.json` pruefen |
| Mikro passt nicht | Guete unter 0.4 — vermutlich gehoert die Aufnahme zu einem anderen Video |
| Modell laedt ewig | Beim ersten Mal ca. 1.5 GB. Danach liegt es im Cache. |
