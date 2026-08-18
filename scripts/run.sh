#!/usr/bin/env bash
# AutoDM Video-Pipeline: Rohmaterial rein -> fertiges Video raus.
#
# Kette:  Wellenform-Segmentierung -> Take-Auswahl -> Schnitt -> Verify
#         -> Transkription -> Captions -> Render -> Zielordner
#
# Usage:
#   run.sh <rohvideo> [--auto] [--stop-nach-cut] [--ziel <pfad>]
#
#   --auto            Take-Auswahl ohne Rueckfrage übernehmen (sonst Stopp zur Freigabe)
#   --stop-nach-cut   Nur schneiden, keine Captions (wenn du in CapCut weiterarbeiten willst)
#   --ziel            Zielordner überschreiben (Default: automatisch nach Orientierung)
set -euo pipefail

export PATH="$HOME/bin:$PATH"          # ffmpeg/ffprobe liegen dort, nicht im PATH
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUT_SKILL="$HIER/.."
EDIT_SKILL="$HIER/.."
GX="$HOME/Videos"

INPUT=""; AUTO=0; STOP_NACH_CUT=0; ZIEL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --auto) AUTO=1; shift;;
    --stop-nach-cut) STOP_NACH_CUT=1; shift;;
    --ziel) ZIEL="$2"; shift 2;;
    *) INPUT="$1"; shift;;
  esac
done

[ -z "$INPUT" ] && { echo "usage: run.sh <rohvideo> [--auto] [--stop-nach-cut] [--ziel <pfad>]"; exit 2; }
[ -f "$INPUT" ] || { echo "FEHLER: '$INPUT' nicht gefunden"; exit 1; }
# Absolut machen - später wird ins Arbeitsverzeichnis gewechselt
INPUT="$(cd "$(dirname "$INPUT")" && pwd)/$(basename "$INPUT")"

command -v ffmpeg >/dev/null || { echo "FEHLER: ffmpeg fehlt (erwartet in ~/bin)"; exit 1; }

NAME="$(basename "${INPUT%.*}")"
WORK="$(cd "$(dirname "$INPUT")" && pwd)/${NAME}_edit"
mkdir -p "$WORK"
cd "$WORK"

echo "=== AutoDM Video-Pipeline ==="
echo "Quelle:      $INPUT"
echo "Arbeitsordner: $WORK"

# --- Orientierung + Format (Rotation beachten!) ---
read -r W H < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$INPUT" | tr ',' ' ')
# ffprobe gibt hier je nach Datei MEHRERE Zeilen aus (z.B. "90" + "0"). Ein
# blosses head -1 reichte nicht, der Stringvergleich schlug fehl und hochkant
# gefilmtes Sony-Material (3840x2160 + rotation=90) galt als longform
# (06.08.2026, C0759-C0761). Deshalb die erste ZAHL herausfiltern.
# `|| true`, weil Querformat-Material GAR KEINEN Rotationseintrag hat: grep
# faende dann nichts, gaebe 1 zurück, und `set -e pipefail` würde die
# Pipeline wortlos abbrechen (06.08.2026, C0768/C0769).
ROT=$(ffprobe -v error -select_streams v:0 -show_entries stream_side_data=rotation \
      -of default=nw=1:nk=1 "$INPUT" 2>/dev/null | grep -Eo '^-?[0-9]+' | head -1 || true)
ROT=${ROT:-0}
case "${ROT#-}" in 90|270) TMP=$W; W=$H; H=$TMP;; esac
if [ "$H" -gt "$W" ]; then FORMAT="shortform"; else FORMAT="longform"; fi
echo "Format:      $FORMAT (${W}x${H}, rotation=$ROT)"

if [ -z "$ZIEL" ]; then
  if [ "$FORMAT" = "shortform" ]; then ZIEL="$GX/FERTIG ZU POSTEN/Fertig IG"; else ZIEL="$GX/FERTIG ZU POSTEN/Fertig YT"; fi
fi
mkdir -p "$ZIEL"

# --- 1. Audio ---
echo ""; echo "[1/6] Audio extrahieren ..."
ffmpeg -y -v error -i "$INPUT" -vn -ac 1 -ar 16000 -c:a pcm_s16le audio16k.wav

# --- 2. Wellenform-Segmente + Transkription pro Segment ---
# Whisper-Wort-Timestamps sind bei Multi-Take unbrauchbar (Wörter werden über
# Pausen gestreckt). Deshalb Segmente aus der Energie des Audios ableiten.
if [ "$AUTO" = "1" ] && [ -f keepers.json ]; then
  echo "[2/6] Vorhandene keepers.json gefunden - Auswahl wird NICHT überschrieben."
  echo "      ($(python3 -c "import json;print(len(json.load(open('keepers.json'))))") Fenster)"
  echo "[3/6] übersprungen"
else
  echo "[2/6] Sprech-Segmente finden (das dauert am laengsten) ..."
  python3 "$HIER/segment.py" audio16k.wav --gap 0.35 --lang de
  echo "[3/6] Takes wählen (Wiederholungen -> letzte Version) ..."
  python3 "$HIER/pick_takes.py" --sim 0.68 --head-words 3
fi

if [ "$AUTO" = "0" ]; then
  echo ""
  echo ">>> STOPP zur Freigabe."
  echo "    Prüfe $WORK/keepers.json - besonders bei mehrteiligen Zeilen"
  echo "    (Titel + Erklärung getrennt gesprochen) wählt die Automatik zu streng."
  echo "    Segment-Texte zum Nachschlagen: $WORK/segments_wave.json"
  echo "    Weiter mit:  bash $0 \"$INPUT\" --auto"
  exit 0
fi

# --- 4. Schnitt ---
# words.json MUSS aus den Wellenform-Segmenten kommen. Sonst verwirft cut.py
# still Fenster, in denen laut kaputter Whisper-Wortliste keine Wörter liegen.
echo "[4/6] Schneiden ..."
python3 "$HIER/words_from_segments.py"
python3 "$HIER/cut.py" --input "$INPUT" --audio audio16k.wav \
  --words words.json --keepers keepers.json --out "cut.mp4" --head 0.03 --tail 0.12

echo "[5/6] Prüfen (Doppelungen + Datei-Integritaet) ..."
python3 "$HIER/verify.py" cut.mp4 || {
  echo ""
  echo "!! VERIFY FEHLGESCHLAGEN - Schnitt NICHT übernehmen."
  echo "   Bei Doppelungen: in keepers.json den doppelten Take entfernen,"
  echo "   dann erneut mit --auto starten."
  exit 1
}

if [ "$STOP_NACH_CUT" = "1" ]; then
  cp cut.mp4 "$ZIEL/${NAME}.mp4"
  echo ""; echo "FERTIG (nur Schnitt): $ZIEL/${NAME}.mp4"
  exit 0
fi

# --- 6. Captions + Render ---
echo "[6/6] Captions + Render ..."
EDIT_WORK=$(python3 -c "
import hashlib, pathlib
p = pathlib.Path('$WORK/cut.mp4').resolve()
print(pathlib.Path.home()/'.cache'/'video-edit'/f'{p.stem[:40]}_{hashlib.sha1(str(p).encode()).hexdigest()[:12]}')
")
mkdir -p "$EDIT_WORK"
# transcribe_de.py statt transcribe.py: whisperx ist nicht installiert, und der
# initial_prompt sorgt dafür, dass "Erstens" nicht zu "1." normalisiert wird.
python3 "$HIER/transcribe_de.py" cut.mp4 "$EDIT_WORK/words.json"
# QUALITY=max: echtes 4K (Julians Vorgabe 31.07.2026 "allerbeste Qualität").
# "final" wäre 1080p, "preview" 720p.
# Julians Library (gx-*) hat Vorrang vor den BuildLoop-Tracks
MUSIK="$(ls "$EDIT_SKILL/music/"gx-*.mp3 2>/dev/null | head -1)"
[ -z "$MUSIK" ] && MUSIK="$(ls "$EDIT_SKILL/music/"*.mp3 2>/dev/null | head -1)"
MUSIK="$(basename "${MUSIK:-}")"
CAPTIONS=1 QUALITY=max ${MUSIK:+MUSIC_TRACK="$MUSIK"} \
  bash "$HIER/render.sh" "$WORK/cut.mp4" || {
    echo "[warn] Render meldete einen Fehler - prüfe, ob trotzdem ein Ergebnis entstand"
  }

# Reihenfolge = aufsteigende Qualität; die letzte existierende gewinnt.
OUT=""
for kandidat in cut.preview.mp4 cut.enhanced.mp4 cut.scored.mp4 cut.final.mp4; do
  [ -f "$WORK/$kandidat" ] && OUT="$WORK/$kandidat"
done
[ -z "$OUT" ] && { echo "FEHLER: kein Render-Ergebnis gefunden"; exit 1; }
echo "Verwende: $(basename "$OUT")"

cp "$OUT" "$ZIEL/${NAME}.mp4"
echo ""
echo "=== FERTIG ==="
echo "Ergebnis:  $ZIEL/${NAME}.mp4"
echo "Zwischenstaende: $WORK"
