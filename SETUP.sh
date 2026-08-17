#!/usr/bin/env bash
# Einmalige Einrichtung. Prueft, was fehlt, und installiert es.
# Alles landet im Benutzerverzeichnis — kein sudo, keine Systemaenderung.
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== AutoDM Videoeditor — Einrichtung ==="
echo

FEHLT=0
ok()   { printf "  \033[32mok\033[0m    %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m     %s\n" "$1"; }
fehl() { printf "  \033[31mfehlt\033[0m %s\n" "$1"; FEHLT=1; }

# --- 1. Grundlagen ---
echo "1. Rechner pruefen"
if [ "$(uname)" != "Darwin" ]; then
  fehl "Dieses Paket ist fuer macOS gebaut. Windows wird noch nicht unterstuetzt."
  exit 1
fi
ok "macOS $(sw_vers -productVersion), $(uname -m)"

command -v python3 >/dev/null && ok "python3 $(python3 -V 2>&1 | cut -d' ' -f2)" || fehl "python3"

if command -v ffmpeg >/dev/null; then ok "ffmpeg"
elif [ -x "$HOME/bin/ffmpeg" ]; then ok "ffmpeg (~/bin)"; export PATH="$HOME/bin:$PATH"
else fehl "ffmpeg"; fi

CAPCUT_DIR="$HOME/Movies/CapCut/User Data/Projects/com.lveditor.draft"
[ -d "$CAPCUT_DIR" ] && ok "CapCut gefunden" || warn "CapCut-Ordner nicht gefunden — CapCut einmal starten und ein leeres Projekt anlegen"

echo

# --- 2. Fehlendes installieren ---
if [ "$FEHLT" = "1" ]; then
  echo "2. Fehlendes installieren"
  if ! command -v ffmpeg >/dev/null && [ ! -x "$HOME/bin/ffmpeg" ]; then
    echo "   ffmpeg wird geladen (ca. 80 MB) ..."
    mkdir -p "$HOME/bin"
    ARCH=$([ "$(uname -m)" = "arm64" ] && echo "arm64" || echo "amd64")
    curl -fsSL -o /tmp/ffmpeg.zip "https://www.osxexperts.net/ffmpeg8${ARCH}.zip" 2>/dev/null \
      || curl -fsSL -o /tmp/ffmpeg.zip "https://evermeet.cx/ffmpeg/getrelease/zip"
    unzip -o -q /tmp/ffmpeg.zip -d "$HOME/bin" && chmod +x "$HOME/bin/ffmpeg"
    xattr -d com.apple.quarantine "$HOME/bin/ffmpeg" 2>/dev/null
    "$HOME/bin/ffmpeg" -version >/dev/null 2>&1 && ok "ffmpeg installiert" \
      || { fehl "ffmpeg-Installation fehlgeschlagen — bitte manuell: brew install ffmpeg"; exit 1; }
    export PATH="$HOME/bin:$PATH"
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

# --- 4. rclone fuer Google Drive ---
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
echo "   Beim ersten Schnitt laedt das Modell (ca. 1.5 GB). Jetzt vorladen? [j/N]"
read -r -t 30 ANTWORT || ANTWORT="n"
if [ "${ANTWORT:-n}" = "j" ]; then
  python3 - <<'PY' || echo "   Vorladen fehlgeschlagen — passiert dann beim ersten Schnitt."
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
  echo "   Uebersprungen."
fi
echo

echo "=== Fertig ==="
echo "Naechster Schritt: den Text aus START.md in Claude Code einfuegen."
