# Der Text zum Einfügen

Öffne Claude Code im Terminal (`claude`) und füge den Text zwischen den Linien
ein. Alles Weitere fragt Claude dich.

---

```
Ich habe das Paket "autodm-videoeditor" in ~/.claude/skills/autodm-videoeditor
liegen. Lies dort SKILL.md und führe mich Schritt für Schritt durch.

Mein Ziel: Ich gebe dir einen Google-Drive-Link mit Rohmaterial (Videos, evtl.
dazu getrennt aufgenommene Tonspuren). Du lädst das herunter, schneidest es
und legst mir pro Video ein fertiges CapCut-Projekt an.

Bitte:
- Prüfe zuerst, ob alles eingerichtet ist. Wenn nicht, sag mir was zu tun ist.
- Erklär mir kurz, was du gerade machst - ich bin kein Entwickler.
- Sag mir vorher Bescheid, wenn ich CapCut schließen muss.
- Zeig mir am Ende, was du gefunden hast und wo ich nachschauen sollte.
```

---

## Vorher: einmalige Einrichtung

```bash
git clone https://github.com/gxrtner/autodm-videoeditor.git ~/.claude/skills/autodm-videoeditor
bash ~/.claude/skills/autodm-videoeditor/SETUP.sh
```

Danach Claude Code einmal neu starten, damit das Paket erkannt wird.

## Was du brauchst

- **Mac** (Apple Silicon oder Intel)
- **CapCut** installiert und einmal gestartet
- **Claude Code** im Terminal
- Einen **Google-Drive-Link** auf einen Ordner, freigegeben für "Jeder mit dem Link"

## Was danach passiert

Du bekommst pro Video ein CapCut-Projekt mit:

- den guten Takes aneinandergereiht, Pausen und Fehlstarts raus
- deinem Mikro-Ton als eigener Spur, synchron zum Bild
- **Markern auf den Stellen, an denen der Schnitt unsicher war**

Die Marker sind wichtig: Der Schnitt läuft vollautomatisch und liegt nicht
immer richtig. Statt das ganze Video zu prüfen, springst du in CapCut von
Marker zu Marker - meist sind es drei bis sieben Stellen. Was jeder Marker
bedeutet, steht in SKILL.md.
