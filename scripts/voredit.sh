#!/usr/bin/env bash
# Voredit: Ordner rein -> geschnittene CapCut-Projekte mit Untertiteln raus.
#
# Julian legt Rohvideos und (optional) die Mikro-Aufnahmen in einen Ordner.
# Alles Weitere läuft hier durch:
#   1. Mikro je Video per Tonkorrelation zuordnen
#   2. Wellenform-Segmentierung + Take-Auswahl
#   3. STOPP zur Freigabe  <- hier prüft Claude die Auswahl
#   4. --auto: CapCut-Projekt je Video + Untertitel in Julians Stil
#
# Usage:
#   voredit.sh <ordner>          Schneiden und Auswahl zeigen (Gate)
#   voredit.sh <ordner> --auto   Nach der Freigabe: Export ins CapCut-Projekt
#   --original                   Quellvideo direkt referenzieren statt es als
#                                1080p-Arbeitsfassung zu kopieren
set -euo pipefail
export PATH="$HOME/bin:$PATH"

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORDNER=""; AUTO=0
ORIGINAL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --auto) AUTO=1; shift;;
    --original) ORIGINAL=1; shift;;
    *) ORDNER="$1"; shift;;
  esac
done
[ -z "$ORDNER" ] && { echo "usage: voredit.sh <ordner> [--auto] [--original]"; exit 2; }
[ -d "$ORDNER" ] || { echo "FEHLER: '$ORDNER' ist kein Ordner"; exit 1; }
ORDNER="$(cd "$ORDNER" && pwd)"

if [ "$AUTO" = "1" ] && pgrep -x CapCut >/dev/null; then
  echo "FEHLER: CapCut läuft. Mit Cmd+Q beenden - sonst überschreibt es die"
  echo "        erzeugten Projekte beim Beenden."; exit 1
fi

PAARE="$ORDNER/.voredit-paare.json"
echo "=== Voredit: $(basename "$ORDNER") ==="
if [ ! -f "$PAARE" ]; then
  python3 "$SKILL/paare_finden.py" "$ORDNER" --json "$PAARE"
else
  echo "Zuordnung liegt vor ($(basename "$PAARE")) - zum Neuermitteln löschen."
fi
echo

VOREDIT_SKRIPTE="$SKILL" python3 - "$ORDNER" "$PAARE" "$AUTO" "$ORIGINAL" <<'PY'
import json, os, subprocess, sys
from pathlib import Path

ordner, paare_datei, auto = Path(sys.argv[1]), sys.argv[2], sys.argv[3] == "1"
original = len(sys.argv) > 4 and sys.argv[4] == "1"
skill = Path(os.environ["VOREDIT_SKRIPTE"])
paare = json.load(open(paare_datei))

for eintrag in paare:
    video = Path(eintrag["video"])
    arbeit = video.parent / f"{video.stem}_edit"
    keepers = arbeit / "keepers.json"
    name = video.stem

    if not keepers.exists():
        print(f"--- {video.name}: schneiden ---")
        r = subprocess.run(["bash", str(skill / "run.sh"), str(video)],
                           capture_output=True, text=True)
        for zeile in r.stdout.splitlines():
            if any(k in zeile for k in ("Format:", "Sprech-Segmente", "Transkription:", "FEHLER")):
                print("   " + zeile.strip())
        if not keepers.exists():
            print(f"   !! kein Schnitt entstanden - {r.stdout.splitlines()[-3:]}")
            continue

    k = json.load(open(keepers))
    dauer = sum(x["b"] - x["a"] for x in k)
    print(f"{video.name}: {len(k)} Fenster, {dauer:.1f}s")

    if not auto:
        continue

    # --- Export ins CapCut-Projekt ---
    cmd = ["python3", str(skill / "capcut_export.py"), str(video), str(keepers),
           "--name", f"{name} - Schnitt"]
    if eintrag.get("audio"):
        # Stimme als EIGENE Spur unter dem Bild, Kameraton stumm - so kann der
        # Nutzer den Ton in CapCut getrennt bearbeiten (Julian 11.08.2026).
        cmd += ["--audio", eintrag["audio"], "--audio-spur"]
    if original:
        # Quellvideo direkt referenzieren statt als 1080p-Arbeitsfassung zu
        # kopieren: volle Aufloesung, kein Speicherplatz, und das ungeschnittene
        # Rohmaterial bleibt im Projekt greifbar - wichtig, weil die Marker auf
        # verworfene Takes zeigen, die der Nutzer dann noch reinziehen kann.
        cmd += ["--original"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    projekt = None
    for zeile in r.stdout.splitlines():
        if zeile.strip().startswith("->"):
            projekt = zeile.split("->", 1)[1].strip()
        if any(x in zeile for x in ("Mikro-Sync", "Hauptspur")):
            print("   " + zeile.strip())
    if not projekt:
        print(f"   !! Export fehlgeschlagen: {r.stdout[-300:]} {r.stderr[-300:]}")
        continue

    # --- Marker auf brenzlige Stellen ---
    r = subprocess.run(["python3", str(skill / "capcut_marker.py"), projekt,
                        "--edit", str(arbeit)], capture_output=True, text=True)
    for zeile in r.stdout.splitlines():
        if zeile.strip().startswith("->") or "Stellen" in zeile:
            print("   " + zeile.strip())
    print(f"   -> {os.path.basename(projekt)}")
PY

echo
if [ "$AUTO" = "1" ]; then
  echo ">>> Fertig. CapCut starten."
else
  cat <<EOF
>>> STOPP zur Freigabe.
    Take-Auswahl je Video liegt in <name>_edit/keepers.json,
    die Segment-Texte in <name>_edit/segments_wave.json.
    Prüfen, bei Bedarf korrigieren, dann:

      bash $SKILL/voredit.sh "$ORDNER" --auto
EOF
fi
