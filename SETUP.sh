#!/usr/bin/env bash
# Einmalige Einrichtung. Prüft, was fehlt, und installiert es.
# Alles landet im Benutzerverzeichnis - kein sudo, keine Systemänderung.
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== AutoDM Videoeditor - Einrichtung ==="
echo

FEHLT=0
ok()   { printf "  \033[32mok\033[0m    %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m     %s\n" "$1"; }
fehl() { printf "  \033[31mfehlt\033[0m %s\n" "$1"; FEHLT=1; }

# --- 1. Grundlagen ---
echo "1. Rechner prüfen"
if [ "$(uname)" != "Darwin" ]; then
  fehl "Dieses Paket ist für macOS gebaut. Windows wird noch nicht unterstützt."
  exit 1
fi
ok "macOS $(sw_vers -productVersion), $(uname -m)"

command -v python3 >/dev/null && ok "python3 $(python3 -V 2>&1 | cut -d' ' -f2)" || fehl "python3"

if command -v ffmpeg >/dev/null; then ok "ffmpeg"
elif [ -x "$HOME/bin/ffmpeg" ]; then ok "ffmpeg (~/bin)"; export PATH="$HOME/bin:$PATH"
else fehl "ffmpeg"; fi

CAPCUT_DIR="$HOME/Movies/CapCut/User Data/Projects/com.lveditor.draft"
[ -d "$CAPCUT_DIR" ] && ok "CapCut gefunden" || warn "CapCut-Ordner nicht gefunden - CapCut einmal starten und ein leeres Projekt anlegen"

echo

# --- 2. Fehlendes installieren ---
if [ "$FEHLT" = "1" ]; then
  echo "2. Fehlendes installieren"
  if ! command -v ffmpeg >/dev/null && [ ! -x "$HOME/bin/ffmpeg" ]; then
    # Quelle: ffmpeg.martin-riedl.de - liefert als einzige arm64 UND amd64
    # nativ, je ein Binary pro ZIP ohne __MACOSX-Beiwerk.
    # osxexperts (404/503 am 18.08.2026) und evermeet (Intel-only, laut
    # Betreiber ausdruecklich kein Apple Silicon) sind raus.
    # ffprobe kommt IMMER separat - kein Anbieter packt beide in ein Archiv,
    # und die Pipeline braucht beide.
    mkdir -p "$HOME/bin"
    case "$(uname -m)" in arm64) A=arm64;; *) A=amd64;; esac
    for WERKZEUG in ffmpeg ffprobe; do
      echo "   $WERKZEUG wird geladen (ca. 28 MB) ..."
      URL="https://ffmpeg.martin-riedl.de/redirect/latest/macos/$A/release/$WERKZEUG.zip"
      GELADEN=0
      # Der Redirect-Dienst antwortet kalt gelegentlich mit 404 - dreimal probieren
      for VERSUCH in 1 2 3; do
        if curl -fsSL --retry 2 -o "/tmp/$WERKZEUG.zip" "$URL" 2>/dev/null \
           && unzip -tq "/tmp/$WERKZEUG.zip" >/dev/null 2>&1; then
          GELADEN=1; break
        fi
        sleep 2
      done
      if [ "$GELADEN" != "1" ]; then
        fehl "$WERKZEUG konnte nicht geladen werden - bitte manuell: brew install ffmpeg"
        exit 1
      fi
      unzip -o -q -j "/tmp/$WERKZEUG.zip" -x '__MACOSX/*' -d "$HOME/bin"
      chmod +x "$HOME/bin/$WERKZEUG"
      xattr -cr "$HOME/bin/$WERKZEUG" 2>/dev/null
      # Apple Silicon startet unsignierte Binaries nur mit Ad-hoc-Signatur
      codesign -s - -f "$HOME/bin/$WERKZEUG" >/dev/null 2>&1
    done
    export PATH="$HOME/bin:$PATH"
    if "$HOME/bin/ffmpeg" -version >/dev/null 2>&1 && "$HOME/bin/ffprobe" -version >/dev/null 2>&1; then
      ok "ffmpeg und ffprobe installiert"
    else
      fehl "Installation fehlgeschlagen - bitte manuell: brew install ffmpeg"; exit 1
    fi
  fi
  echo
fi

# --- 3. Python-Pakete ---
echo "3. Python-Pakete"
python3 -c "import numpy" 2>/dev/null && ok "numpy" || {
  echo "   numpy wird installiert ..."; python3 -m pip install --user -q numpy && ok "numpy"; }

if python3 -c "import mlx_whisper" 2>/dev/null; then
  ok "mlx-whisper (schnell, Apple Silicon)"
elif python3 -c "import faster_whisper" 2>/dev/null; then
  ok "faster-whisper"
else
  if [ "$(uname -m)" = "arm64" ]; then
    echo "   mlx-whisper wird installiert (schnellste Variante auf M-Chips) ..."
    python3 -m pip install --user -q mlx-whisper && ok "mlx-whisper" || {
      warn "mlx-whisper ging nicht, versuche faster-whisper"
      python3 -m pip install --user -q faster-whisper && ok "faster-whisper"; }
  else
    echo "   faster-whisper wird installiert (ca. 200 MB) ..."
    python3 -m pip install --user -q faster-whisper && ok "faster-whisper" \
      || { fehl "faster-whisper"; exit 1; }
  fi
fi
echo

# --- 4. rclone für Google Drive ---
echo "4. Google Drive"
if command -v rclone >/dev/null || [ -x "$HOME/bin/rclone" ]; then
  ok "rclone"
else
  echo "   rclone wird geladen (ca. 20 MB) ..."
  mkdir -p "$HOME/bin"
  ARCH=$([ "$(uname -m)" = "arm64" ] && echo "osx-arm64" || echo "osx-amd64")
  curl -fsSL -o /tmp/rclone.zip "https://downloads.rclone.org/rclone-current-${ARCH}.zip"
  unzip -j -o -q /tmp/rclone.zip '*/rclone' -d "$HOME/bin" && chmod +x "$HOME/bin/rclone"
  xattr -d com.apple.quarantine "$HOME/bin/rclone" 2>/dev/null
  "$HOME/bin/rclone" version >/dev/null 2>&1 && ok "rclone installiert" || warn "rclone-Installation fehlgeschlagen"
fi
echo "   Noch NICHT verbunden. Das macht Claude beim ersten Video mit dir zusammen."
echo

# --- 5. Sprachmodell vorladen ---
echo "5. Sprachmodell"
echo "   Beim ersten Schnitt lädt das Modell (ca. 1.5 GB). Jetzt vorladen? [j/N]"
read -r -t 30 ANTWORT || ANTWORT="n"
if [ "${ANTWORT:-n}" = "j" ]; then
  python3 - <<'PY' || echo "   Vorladen fehlgeschlagen - passiert dann beim ersten Schnitt."
try:
    import mlx_whisper, numpy as np, tempfile, wave, os
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f: p=f.name
    w=wave.open(p,"wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes((np.zeros(16000, dtype=np.int16)).tobytes()); w.close()
    mlx_whisper.transcribe(p, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="de")
    os.unlink(p); print("   Modell geladen.")
except ImportError:
    from faster_whisper import WhisperModel
    WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    print("   Modell geladen.")
PY
else
  echo "   Übersprungen."
fi
echo

echo "=== Fertig ==="
echo "Nächster Schritt: den Text aus START.md in Claude Code einfügen."
