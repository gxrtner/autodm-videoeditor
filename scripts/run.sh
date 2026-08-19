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

INPUT=""; AUTO=0; STOP_NACH_CUT=0; ZIEL=""; TON=""; TON_VERSATZ="0"
while [ $# -gt 0 ]; do
  case "$1" in
    --auto) AUTO=1; shift;;
    --stop-nach-cut) STOP_NACH_CUT=1; shift;;
    --ziel) ZIEL="$2"; shift 2;;
    --ton) TON="$2"; shift 2;;
    --ton-versatz) TON_VERSATZ="$2"; shift 2;;
    *) INPUT="$1"; shift;;
  esac
done

[ -z "$INPUT" ] && { echo "usage: run.sh <rohvideo> [--auto] [--stop-nach-cut] [--ziel <pfad>] [--ton <datei> --ton-versatz <s>]"; exit 2; }
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
#
# ZWEI DINGE, beide am 19.08.2026 im Abnahmetest aufgeflogen:
#
# 1. QUELLE. Wird der Ton getrennt aufgenommen (Ansteckmikro oder zweite
#    Kamera), wurde er bisher nur an CapCut durchgereicht - die ANALYSE lief
#    weiter auf dem Kameramikro. Gemessen ueber fuenf Videos: audio16k.wav
#    korrelierte mit 1.0000 zur Kamera und mit 0.0067 zur guten Tonspur, die
#    15 dB lauter war. Die Pipeline hoerte mit dem schlechten Mikro zu und
#    lieferte mit dem guten aus. --ton schaltet die Analyse auf die gute
#    Quelle um; --ton-versatz schiebt sie auf die Bildzeitachse, damit alle
#    Fenster weiter in Videozeit liegen und nichts umgerechnet werden muss.
#
# 2. PEGEL. segment.py arbeitet mit absoluten RMS-Schwellen (0.005 / 0.002).
#    Bei den Testaufnahmen lag der Median der Sprache bei 0.0033 bis 0.0044 -
#    also UNTER der Einstiegsschwelle. Der Segmentierer stieg zu spaet ein und
#    zu frueh aus, Satzenden und leise Wortanfaenge fielen weg (9 Faelle in 5
#    Videos). Die Normalisierung auf einen festen Spitzenpegel bringt jede
#    Aufnahme in den Bereich, fuer den die Schwellen gedacht sind. Ohne sie
#    haengt die Schnittqualitaet daran, wie laut jemand aufgenommen hat.
echo ""; echo "[1/6] Audio extrahieren ..."
if [ -n "$TON" ] && [ ! -f "$TON" ]; then
  echo "        !! Tonquelle '$TON' nicht gefunden - es wird der Kameraton"
  echo "           verwendet. Das ist fast immer die schlechtere Spur."
fi
if [ -n "$TON" ] && [ -f "$TON" ]; then
  echo "        Tonquelle: $(basename "$TON") (Versatz ${TON_VERSATZ}s)"
  if [ "$(python3 -c "print(1 if float('$TON_VERSATZ') >= 0 else 0)")" = "1" ]; then
    # Tonaufnahme lief schon, als die Kamera startete -> vorne wegschneiden
    ffmpeg -y -v error -ss "$TON_VERSATZ" -i "$TON" -vn -ac 1 -ar 16000 \
           -c:a pcm_s16le roh16k.wav
  else
    # Tonaufnahme startete spaeter -> Stille voranstellen
    MS=$(python3 -c "print(int(round(-float('$TON_VERSATZ')*1000)))")
    ffmpeg -y -v error -i "$TON" -vn -ac 1 -ar 16000 \
           -af "adelay=${MS}:all=1" -c:a pcm_s16le roh16k.wav
  fi
else
  ffmpeg -y -v error -i "$INPUT" -vn -ac 1 -ar 16000 -c:a pcm_s16le roh16k.wav
fi

# STATISCHE Anhebung, ein fester Faktor fuer die ganze Datei.
#
# Wichtig: KEIN dynaudnorm und kein loudnorm. Die regeln pro Zeitfenster nach
# und ziehen damit auch die Pausen hoch - im Test wurden aus 46 Segmenten 33
# und aus 64s Schnitt 156s, weil Atmen und Raumton ueber die Sprachschwelle
# gehoben wurden. segment.py unterscheidet Sprache von Stille genau ueber
# diesen Abstand; er muss erhalten bleiben. Ein konstanter Faktor verschiebt
# beide Seiten gleich und laesst das Verhaeltnis unangetastet.
python3 - <<'PYNORM'
import wave, numpy as np
w = wave.open("roh16k.wav", "rb")
n, sr = w.getnframes(), w.getframerate()
a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
w.close()
hop = 160
r = np.sqrt(np.array([np.mean(a[i*hop:(i+1)*hop] ** 2) for i in range(len(a)//hop)]))
laut = r[r > np.percentile(r, 60)]
med = float(np.median(laut)) if len(laut) else 0.0
# Ziel: Sprachmedian bei 0.012, also gut ueber der Einstiegsschwelle 0.005.
# Nach oben gedeckelt, damit nichts uebersteuert.
faktor = 1.0
if med > 1e-6:
    faktor = min(0.012 / med, 0.95 / max(float(np.max(np.abs(a))), 1e-6))
    faktor = max(faktor, 1.0)
b = np.clip(a * faktor, -1.0, 1.0)
r2 = np.sqrt(np.array([np.mean(b[i*hop:(i+1)*hop] ** 2) for i in range(len(b)//hop)]))
laut2 = r2[r2 > np.percentile(r2, 60)]
print(f"        Pegel: Sprachmedian {med:.4f} -> {float(np.median(laut2)):.4f} "
      f"(Faktor {faktor:.1f}x, Schwelle 0.0050)")
o = wave.open("audio16k.wav", "wb")
o.setnchannels(1); o.setsampwidth(2); o.setframerate(sr)
o.writeframes((b * 32767).astype(np.int16).tobytes()); o.close()
PYNORM
rm -f roh16k.wav

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
  python3 "$HIER/pick_takes.py" --sim 0.62 --head-words 3
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
