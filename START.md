# Der Text zum Einfügen

Öffne Claude Code im Terminal (`claude`) und füge den Text zwischen den Linien
ein. Alles Weitere fragt Claude dich.

---

```
Ich habe das Paket "autodm-videoeditor" in ~/.claude/skills/autodm-videoeditor
liegen. Lies dort SKILL.md und führe mich Schritt für Schritt durch.

Mein Ziel: Ich gebe dir einen Google-Drive-Link mit Rohmaterial (Videos, evtl.
dazu getrennt aufgenommene Tonspuren oder eine zweite Kamera). Du lädst das
herunter, schneidest es und legst mir pro Video ein fertiges CapCut-Projekt an.

Bitte:
- Prüfe zuerst, ob alles eingerichtet ist. Wenn nicht, sag mir was zu tun ist.
- Erklär mir kurz, was du gerade machst - ich bin kein Entwickler.
- Lies die Take-Auswahl gegen, bevor du die Projekte baust. Das steht so in
  SKILL.md und ist der Schritt, der über die Qualität entscheidet - bitte
  nicht überspringen. Zeig mir danach, was du korrigiert hast.
- Nimm beim Anlegen --original, damit meine Auflösung erhalten bleibt.
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

- den guten Takes aneinandergereiht, Pausen, Fehlstarts und Regie-Ansagen raus
- deinem Ton als eigener Spur, synchron zum Bild, Kameraton stumm
- deinem Bild **unverändert** - kein Zoom, kein anderer Ausschnitt
- **Markern auf den Stellen, an denen der Schnitt unsicher war**

Der Ablauf hat einen Zwischenschritt, der über die Qualität entscheidet: Nach
dem Schnitt hält die Pipeline an, und Claude liest die Auswahl gegen die
Transkripte, bevor die Projekte gebaut werden. Ohne diesen Schritt bekommst du
den Rohvorschlag - der trifft rund 85 Prozent der richtigen Takes, und die
fehlenden 15 Prozent sind genau die Stellen, die im fertigen Video auffallen.

Die Marker zeigen danach auf das, was auch Claude nicht entscheiden kann - etwa
welche von zwei gleichwertigen Fassungen dir besser gefällt. Meist sind es vier
bis acht Stellen. Was jeder Marker bedeutet, steht in SKILL.md.

**Sieh dir das Video trotzdem einmal ganz an, bevor du es postest.** Die Marker
sind ein Hinweis, keine vollständige Fehlerliste.
