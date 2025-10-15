# APISearch
··
🔍 Was macht dieses Tool?
Dieses Tool durchsucht die öffentlichen Ausbildungsangebote der Bundesagentur für Arbeit (BA)
über die offizielle API und wertet sie strukturiert aus.··
Es eignet sich ideal zur Analyse von Anbietern, Kursen und Standorten bei Umschulungen und Ausbildungen.··
··
✅ Funktionen im Überblick:··
• Automatisiertes Abrufen von Ausbildungsangeboten über Link oder manuelle Eingabe··
• Verarbeitung einzelner oder mehrerer Links (je Zeile ein Link)··
• Entfernung von Duplikaten und Filterung ungültiger Angebote··
• Gruppierung und Zählung der Angebote pro Bildungsanbieter··
• Export als Excel (.xlsx) oder optional als JSON··
··
🛠️ So funktioniert's:··
1. Öffne die Website der BA-Ausbildungssuche und kopiere einen vollständigen Link··
   (z. B. mit 'beruf=1234&ort=Berlin_...')··
2. Wähle aus:··
   • ✅ 'URL für Parameter verwenden' – für einen einzelnen Link··
   • ✅ 'Mehrere Links verarbeiten' – für mehrere Links (je Zeile ein Link)··
   • ❌ Beides deaktivieren – um manuell Stadt, ID, Radius etc. einzugeben··
3. Klicke auf 'Start', um die Suche zu starten··
4. Exportiere Ergebnisse per Button in Excel und/oder JSON··
··
⚠️ Wichtige Hinweise & Einschränkungen:··
• Nur Links mit einer konkreten Job-ID ('beruf=...') funktionieren··
• Implizite Suchanfragen ohne ID werden nicht unterstützt··
• Wenn mehr als 50 Angebote im Radius liegen, können nicht alle Ergebnisse··
  von der API zurückgegeben werden (API-Beschränkung)··
• Anbieter wie 'WBS TRAINING AG' oder 'karriere tutor' liefern über die API··
  manchmal mehr Angebote als auf der Website sichtbar sind··
• Ungültige Einträge (z. B. ohne ID oder Anbietername) werden übersprungen··
• Dieses Tool arbeitet asynchron und parallelisiert, dennoch ist mit Ladezeiten··
  bei vielen Treffern zu rechnen.··
··
📁 Empfehlung:··
• Verwende den JSON-Export für tiefere Auswertungen und für eigene Analysen.··
• Nutze die Excel-Datei zur schnellen Übersicht oder Weitergabe··
··
🛠️ Dokumentation der API:··
• https://ausbildungssuche.api.bund.dev/ ··
• https://github.com/AndreasFischer1985/ausbildungssuche-api ··
··

# Python Skript als .exe installieren:
··
Dafür müssen alle Python Dependencies bereits in der selben Python Version heruntergeladen sein:··

| Modul         | Installationspaket        | Zweck                                   |
| ------------- | ------------------------- | --------------------------------------- |
| `requests`    | `pip install requests`    | HTTP-Requests an die Arbeitsagentur-API |
| `pandas`      | `pip install pandas`      | Datenanalyse, Export in Excel           |
| `openpyxl`    | `pip install openpyxl`    | Excel-Schreibunterstützung für pandas   |
| `pyinstaller` | `pip install pyinstaller` | Zum Erstellen der `.exe`                |

··
Dann im Python Ordner der richtigen Version den Befehl ausführen:··
(Ich habe Python 3.11.7 verwendet)··
··
```python
pyinstaller --onefile --noconsole --icon=icon.ico APISearch.py
```

··
··
Bildungsarten: ··
100=Allgemeinbildung, 101=Teilqualifizierung, 102=Berufsausbildung, ··
103=Gesetzlich/gesetzesähnlich geregelte Fortbildung/Qualifizierung, ··
104=Fortbildung/Qualifizierung, 105=Abschluss nachholen, 106=Rehabilitation, ··
107108=Studienangebot - grundständig, 109=Umschulung··
