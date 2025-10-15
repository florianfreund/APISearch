# APISearch
<br>
🔍 Was macht dieses Tool?<br>
Dieses Tool durchsucht die öffentlichen Ausbildungsangebote der Bundesagentur für Arbeit (BA)<br>
über die offizielle API und wertet sie strukturiert aus.<br>
Es eignet sich ideal zur Analyse von Anbietern, Kursen und Standorten bei Umschulungen und Ausbildungen.<br>
<br>
✅ Funktionen im Überblick:<br>
• Automatisiertes Abrufen von Ausbildungsangeboten über Link oder manuelle Eingabe<br>
• Verarbeitung einzelner oder mehrerer Links (je Zeile ein Link)<br>
• Entfernung von Duplikaten und Filterung ungültiger Angebote<br>
• Gruppierung und Zählung der Angebote pro Bildungsanbieter<br>
• Export als Excel (.xlsx) oder optional als JSON<br>
<br>
🛠️ So funktioniert's:<br>
1. Öffne die Website der BA-Ausbildungssuche und kopiere einen vollständigen Link<br>
   (z. B. mit 'beruf=1234&ort=Berlin_...')<br>
2. Wähle aus:<br>
   • ✅ 'URL für Parameter verwenden' – für einen einzelnen Link<br>
   • ✅ 'Mehrere Links verarbeiten' – für mehrere Links (je Zeile ein Link)<br>
   • ❌ Beides deaktivieren – um manuell Stadt, ID, Radius etc. einzugeben<br>
3. Klicke auf 'Start', um die Suche zu starten<br>
4. Exportiere Ergebnisse per Button in Excel und/oder JSON<br>
<br>
⚠️ Wichtige Hinweise & Einschränkungen:<br>
• Nur Links mit einer konkreten Job-ID ('beruf=...') funktionieren<br>
• Implizite Suchanfragen ohne ID werden nicht unterstützt<br>
• Wenn mehr als 50 Angebote im Radius liegen, können nicht alle Ergebnisse<br>
  von der API zurückgegeben werden (API-Beschränkung)<br>
• Anbieter wie 'WBS TRAINING AG' oder 'karriere tutor' liefern über die API<br>
  manchmal mehr Angebote als auf der Website sichtbar sind<br>
• Ungültige Einträge (z. B. ohne ID oder Anbietername) werden übersprungen<br>
• Dieses Tool arbeitet asynchron und parallelisiert, dennoch ist mit Ladezeiten<br>
  bei vielen Treffern zu rechnen.<br>
<br>
📁 Empfehlung:<br>
• Verwende den JSON-Export für tiefere Auswertungen und für eigene Analysen.<br>
• Nutze die Excel-Datei zur schnellen Übersicht oder Weitergabe<br>
<br>
🛠️ Dokumentation der API:<br>
• https://ausbildungssuche.api.bund.dev/ <br>
• https://github.com/AndreasFischer1985/ausbildungssuche-api <br>
<br>

# Python Skript als .exe installieren:
<br>
Dafür müssen alle Python Dependencies bereits in der selben Python Version heruntergeladen sein:<br>

| Modul         | Installationspaket        | Zweck                                   |
| ------------- | ------------------------- | --------------------------------------- |
| `requests`    | `pip install requests`    | HTTP-Requests an die Arbeitsagentur-API |
| `pandas`      | `pip install pandas`      | Datenanalyse, Export in Excel           |
| `openpyxl`    | `pip install openpyxl`    | Excel-Schreibunterstützung für pandas   |
| `pyinstaller` | `pip install pyinstaller` | Zum Erstellen der `.exe`                |

<br>
Dann im Python Ordner der richtigen Version den Befehl ausführen:<br>
(Ich habe Python 3.11.7 verwendet)<br>

```python
pyinstaller --onefile --noconsole --icon=icon.ico APISearch.py
```

<br>
Bildungsarten: <br>
100=Allgemeinbildung, 101=Teilqualifizierung, 102=Berufsausbildung, <br>
103=Gesetzlich/gesetzesähnlich geregelte Fortbildung/Qualifizierung, <br>
104=Fortbildung/Qualifizierung, 105=Abschluss nachholen, 106=Rehabilitation, <br>
107108=Studienangebot - grundständig, 109=Umschulung
