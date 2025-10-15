import requests
import json
import time
import warnings
from math import radians, cos, sin, sqrt, atan2
from collections import defaultdict
import pandas as pd
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import tkinter.font as tkFont
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from tkinter import filedialog
import os
import threading
import openpyxl
import traceback
import re
from concurrent.futures import ThreadPoolExecutor
from tkinter import font
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter("ignore", InsecureRequestWarning)


# ============================================
# 🔍 API Anbindung
# ============================================
# ============================================
# Anzupassen, falls neue API Anbindung verfügbar
# ============================================
session = requests.Session()
session.headers.update({
    'User-Agent': 'Ausbildungssuche/1.0 (de.arbeitsagentur.ausbildungssuche)',
    'Host': 'rest.arbeitsagentur.de',
    'X-API-Key': 'infosysbub-absuche',
    'Connection': 'keep-alive',
})

# ============================================
# 📍 GEO- und API-Hilfsfunktionen
# ============================================
def haversine(lat1, lon1, lat2, lon2):
    """
    🌍 Berechnet die Entfernung zwischen zwei geografischen Punkten (in km).
    Nutzt die Haversine-Formel, um die Distanz auf einer Kugel (Erde) zu bestimmen.
    Wird verwendet, um zu prüfen, ob ein Ausbildungsangebot im gewünschten Radius liegt.
    """
    R = 6378 # Erdradius in Kilometern
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

def is_within_radius(offer, center_lat, center_lon, radius_km):
    """
    📏 Prüft, ob ein Angebot innerhalb eines bestimmten Umkreises liegt.
    Die Koordinaten werden aus dem Datensatz entnommen und mit der Haversine-Formel verglichen.
    Enthält Schutzmechanismen gegen fehlende oder ungültige Daten.
    """
    try:
        # 🔍 Stelle sicher, dass alle notwendigen Felder vorhanden sind
        if 'adresse' not in offer or \
           'ortStrasse' not in offer['adresse'] or \
           'koordinaten' not in offer['adresse']['ortStrasse']:
            return False

        coords = offer['adresse']['ortStrasse']['koordinaten']

        # 🧭 Überprüfe, ob lat/lon existieren und gültig sind
        if 'lat' not in coords or coords['lat'] is None or \
           'lon' not in coords or coords['lon'] is None:
            print(f"Warning: Missing or None 'lat' or 'lon' in coordinates for offer: {offer.get('id', 'N/A')}")
            return False

        # Attempt to convert to float. If this fails, it's a TypeError/ValueError
        offer_lat = float(coords['lat'])
        offer_lon = float(coords['lon'])
        
        # ✅ Prüfe Distanz – nur innerhalb des Radius akzeptieren
        return haversine(center_lat, center_lon, offer_lat, offer_lon) <= radius_km

    except (ValueError, TypeError) as e:
        # 🛑 Koordinaten konnten nicht konvertiert werden
        # Catch errors if 'lat' or 'lon' values are not convertible to float
        #some offers doesnt have coords, these are catched here
        #print(f"Error processing coordinates for offer: {offer.get('id', 'N/A')}. Error: {e}")
        return False
    except Exception as e:
        # 🚨 Unerwarteter Fehler – sollte nur selten auftreten
        # Catch any other unexpected errors, although the checks above should prevent most
        print(f"An unexpected error occurred in is_within_radius for offer {offer.get('id', 'N/A')}: {e}")
        return False
    
    
# ============================================
# 🔍 Datenabruf & API-Kommunikation
# ============================================
# ============================================
# Anzupassen, falls neue API Anbindung verfügbar
# ============================================
def search(page, where, job_id, radius, bart):
    """
    📡 Führt einen API-Request an die Ausbildungsstellen-API der BA aus.
    Holt eine einzelne Seite von Ausbildungsangeboten (20 Einträge pro Seite).
    Enthält robustes Fehlerhandling bei Netzwerk- oder API-Problemen.
    """
    url = "https://rest.arbeitsagentur.de/infosysbub/absuche/pc/v1/ausbildungsangebot"
    params = {'page': page, 'size': 20, 'ort': where, 'uk': radius, 'ids': job_id, 'bart': bart}
    try:
        response = session.get(url, params=params, verify=False)
        return response.json()
    except requests.exceptions.Timeout as e:
        print(f"Request timed out: {e}")
        # You might want to log this or notify the user
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network error or HTTP error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON response: {e}")
        return None
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred in search: {e}")
        return None


# ============================================
# ⚙️ Parallele Datensammlung (alle Seiten)
# ============================================
def get_all_offers(where, job_id, radius, lat, lon, bart):
    """
    🚀 Ruft alle Seiten mit Ausbildungsangeboten parallel ab.
    Startet mit Seite 0, bestimmt die Gesamtseitenzahl und lädt den Rest asynchron.
    Nur Angebote im definierten Radius werden übernommen.
    """
    first = search(0, where, job_id, radius, bart)
    if not first or '_embedded' not in first or 'termine' not in first['_embedded']:
        return []
    
    total_pages = first['page']['totalPages']
    all_offers = [o for o in first['_embedded']['termine'] if is_within_radius(o, lat, lon, radius)]

    def fetch_page(p):
        result = search(p, where, job_id, radius, bart)
        if not result or '_embedded' not in result:
            return []
        return [o for o in result['_embedded']['termine'] if is_within_radius(o, lat, lon, radius)]

    # 🧵 Lade weitere Seiten parallel (ThreadPoolExecutor)
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch_page, p) for p in range(1, total_pages)]
        for f in futures:
            try:
                all_offers.extend(f.result())
            except Exception as e:
                print(f"Fehler bei Seite: {e}")

    return all_offers



# ============================================
# 📊 Anbieteranalyse & -auswertung
# ============================================
def count_offers_by_provider(data):
    """
    🧮 Gruppiert Angebote nach Bildungsanbieter.
    Zählt eindeutige Angebote pro Anbieter, erfasst Standorte und Kurstitel.
    Dient als Grundlage für die spätere Excel-Auswertung.
    """
    provider_data = defaultdict(lambda: {'ids': set(), 'locations': set(), 'titles': set()})
    for offer in data:
        try:
            name = offer["angebot"]["bildungsanbieter"]["name"]
            location = offer["adresse"]["ortStrasse"]["name"]
            offer_id = offer["id"]
            title = offer["angebot"]["titel"]
            provider_data[name]['ids'].add(offer_id)
            provider_data[name]['locations'].add(location)
            provider_data[name]['titles'].add(title)
        except Exception as e: # Catch other unexpected errors
            print(f"An unexpected error occurred processing offer ID {offer.get('id', 'N/A')}: {e}")
            continue
        
    # 🔢 Anzahl eindeutiger Angebote pro Anbieter zählen
    for provider in provider_data:
        provider_data[provider]['count'] = len(provider_data[provider]['ids'])
    return provider_data


# ============================================
# 📤 Export der Ergebnisse nach Excel
# ============================================
def export_to_excel(data, search_url, filename='anbieter_stats.xlsx'):
    """
    📁 Exportiert die zusammengefassten Anbieter-Daten in eine Excel-Datei.
    Enthält Anbietername, Anzahl Angebote, Titel und den genutzten Suchlink.
    Ideal für Auswertungen und Vergleiche in Teams.
    """
    rows = []
    for provider, info in data.items():
        title = ""
        if 'titles' in info and info['titles']:
            title = next(iter(info['titles']), "")
        else:
            print(f"Skipping {provider} due to missing or empty titles")

        rows.append({
            "Anbieter": provider,
            "Anzahl Angebote": info['count'],
            "Titel": title,
            "für Suche verwendeter Link (wiederholend)": search_url
        })

    if not rows:
        print("No data to export.")
    else:
        df = pd.DataFrame(rows)
        df.to_excel(filename, index=False)
        print(f"Exported {len(rows)} providers to {filename}")

# ============================================
# 🔗 URL-Parser (Ausbildungsagentur-Links)
# ============================================
def parse_url(url):
    """
    🔍 Zerlegt einen Link der Arbeitsagentur-Ausbildungssuche in seine Einzelparameter.
    Extrahiert Stadt, Koordinaten, Radius, Beruf-ID und Kategorie (bart-Code).
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    job_id = int(qs.get('beruf', ['0'])[0])
    radius = int(qs.get('uk', ['0'])[0])
    kat = qs.get('kat', [''])[0]

    # 🏙️ Beispiel: 'Berlin_13.386738_52.531976' → Stadt, Längengrad, Breitengrad
    ort_parts = qs.get('ort', [''])[0].split('_')
    if len(ort_parts) == 3:
        city, lon, lat = ort_parts
    else:
        raise ValueError("Ungültiges 'ort'-Feld im Link.")

    # 🔁 Umwandlung der 'kat'-Kategorie in den passenden BART-Code
    reverse_bart_map = {
        "0": 102,
        "1": 109,
        "2": 101,
        "3": 105
    }

    bart = reverse_bart_map.get(kat, -1)

    return {
        'where': city,
        'job_id': job_id,
        'radius': radius,
        'lat': float(lat),
        'lon': float(lon),
        'bart': bart
    }


# ============================================
# 🔗 Eingabefelder automatisch aus Link befüllen
# ============================================
def populate_fields_from_link():
    """
    Liest eine BA-Such-URL aus und trägt die enthaltenen Suchparameter
    automatisch in die Eingabefelder ein.
    
    Typischer Anwendungsfall:
    - Du kopierst einen kompletten Suchlink aus der Ausbildungsbörse der BA
    - Das Tool extrahiert automatisch Stadt, Koordinaten, Radius und Berufs-ID
    - Die Felder werden befüllt (und danach wieder deaktiviert)
    
    Beispiel-URL:
    https://...beruf=1234&ort=Berlin_13.4_52.5&uk=50&kat=1
    """
    if not use_url_mode.get():
        messagebox.showwarning("Hinweis", "Bitte aktiviere zuerst die Link-Eingabe-Option.")
        return

    try:
        # ------------------------------------------------------------
        # 🔍 URL einlesen & Parameter auswerten
        # ------------------------------------------------------------
        url = url_entry.get()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Extrahiere Werte aus URL-Parametern
        city = params.get("ort", [""])[0].split("_")[0]
        lon = float(params.get("ort", [""])[0].split("_")[1])
        lat = float(params.get("ort", [""])[0].split("_")[2])
        radius = int(params.get("uk", [50])[0])
        job_id = int(params.get("beruf", [0])[0])
        kat = int(params.get("kat", [1])[0])

        # 🧭 Übersetze Kategorie (kat) in Bildungsart-ID (bart)
        bart_map = {1: 109, 0: 102, 2: 101, 3: 105}
        bart = bart_map.get(kat, 109)

        # ------------------------------------------------------------
        # ✏️ Felder temporär aktivieren & befüllen
        # ------------------------------------------------------------
        for field in [city_entry, job_id_entry, radius_entry, lat_entry, lon_entry, bart_entry]:
            field.config(state="normal")

        city_entry.delete(0, tk.END)
        city_entry.insert(0, city)

        lon_entry.delete(0, tk.END)
        lon_entry.insert(0, lon)

        lat_entry.delete(0, tk.END)
        lat_entry.insert(0, lat)

        radius_entry.delete(0, tk.END)
        radius_entry.insert(0, radius)

        job_id_entry.delete(0, tk.END)
        job_id_entry.insert(0, job_id)
        
        bart_entry.delete(0, tk.END)
        bart_entry.insert(0, bart)

        # ------------------------------------------------------------
        # 🔒 Felder wieder deaktivieren, falls URL-Modus aktiv bleibt
        # ------------------------------------------------------------
        if use_url_mode.get():
            for field in [city_entry, job_id_entry, radius_entry, lat_entry, lon_entry, bart_entry]:
                field.config(state="disabled")

    except Exception as e:
        messagebox.showerror("Fehler beim Auslesen des Links", str(e))

# ============================================
# 🔄 Eingabemodus umschalten (URL ↔ manuell)
# ============================================
def toggle_input_mode():
    """
    Schaltet zwischen den beiden Eingabemodi um:
    - URL-Modus: Felder sind deaktiviert, nur Link-Eingabe aktiv
    - Manueller Modus: Felder sind frei editierbar
    """
    if use_url_mode.get():
        # URL-Modus aktiv → manuelle Felder sperren
        for entry in [city_entry, job_id_entry, radius_entry, lat_entry, lon_entry, bart_entry]:
            entry.config(state="disabled")
        parse_button.config(state="normal")
        url_entry.config(state="normal")
    else:
        # Manueller Modus → Felder freigeben
        for entry in [city_entry, job_id_entry, radius_entry, lat_entry, lon_entry, bart_entry]:
            entry.config(state="normal")
        parse_button.config(state="disabled")
        url_entry.config(state="disabled")


# ============================================
# 🪟 Fortschrittsfenster (Statusanzeige)
# ============================================
def show_progress_window():
    """
    Erstellt ein separates Fenster zur Anzeige des Suchfortschritts.
    
    - Zeigt Live-Statusmeldungen während der API-Abfrage
    - Scrollbare Liste für einzelne Meldungen
    - Button zum Starten des Exports wird am Ende aktiviert
    """
    progress_win = tk.Toplevel(root)
    progress_win.title("Lade Angebote...")
    progress_win.geometry("600x300")
    progress_win.resizable(False, False)
    
    # progress_win.attributes('-topmost', True) # das hier wäre dauerhaft ganz oben
    progress_win.lift()  # Bringt das Fenster in den Vordergrund

    ttk.Label(progress_win, text="Suche läuft...", font=("Arial", 12, "bold")).pack(pady=(10, 5))

    # Rahmen für Liste + Scrollbar
    frame = ttk.Frame(progress_win)
    frame.pack(padx=10, pady=5, fill="both", expand=True)

    scrollbar = ttk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")

    listbox = tk.Listbox(frame, height=10, yscrollcommand=scrollbar.set)
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=listbox.yview)

    # Buttonbereich unten
    button_frame = ttk.Frame(progress_win)
    button_frame.pack(pady=10)

    # Export-Button (zunächst deaktiviert)
    ok_button = tk.Button(progress_win, text="Export starten", state="disabled", bg="lightgreen", fg="black")
    ok_button.pack(side="right", padx=10, pady=10)

    return progress_win, listbox, ok_button

# ============================================
# 📁 Export-Verzeichnis auswählen
# ============================================
def select_export_directory():
    """
    Öffnet einen Dialog zur Auswahl des Zielordners
    für Excel- und JSON-Exporte.
    """
    directory = filedialog.askdirectory()
    if directory:
        export_directory.set(directory)

# ============================================
# ✅ Eingabevalidierung
# ============================================
def validate_inputs():
    """
    Prüft, ob alle Eingabefelder gültige Werte enthalten.
    - Alle Zahlenfelder müssen konvertierbar sein (int / float)
    - Gibt True zurück, wenn alles in Ordnung ist
    - Zeigt eine Fehlermeldung bei ungültiger Eingabe
    """
    try:
        int(job_id_entry.get())
        int(radius_entry.get())
        float(lat_entry.get())
        float(lon_entry.get())
        int(bart_entry.get())

        return True
    except ValueError:
        messagebox.showerror("Eingabefehler", "Bitte stellen Sie sicher, dass alle numerischen Felder gültige Zahlen enthalten.")
        return False
    
# ============================================
# 🧹 Datensicherung & Bereinigung
# ============================================
def safeback(offers):
    """
    Filtert und dedupliziert Angebotsdaten anhand ihrer ID.

    - Entfernt Einträge ohne gültige ID
    - Überspringt doppelte Angebote
    - Gibt ein Dictionary mit eindeutigen Datensätzen zurück
    - Loggt Anzahl der übersprungenen oder doppelten Einträge in der Konsole
    """
    new_offers = {}
    missing_ids = 0
    duplicate_ids = 0

    for offer in offers:
        # Skip any malformed or missing IDs
        offer_id = offer.get("id")
        if not offer_id:
            missing_ids += 1
            print("⚠️ Offer skipped (missing ID):", offer.get("angebot", {}).get("titel", "Kein Titel"))
            continue

        if offer_id in new_offers:
            duplicate_ids += 1
            continue

        new_offers[offer_id] = offer

    print(f"✅ safeback: {len(new_offers)} eindeutige Angebote gespeichert")
    print(f"⚠️ {missing_ids} Angebote ohne ID übersprungen")
    print(f"🔁 {duplicate_ids} doppelte Angebote ignoriert")

    return new_offers


# ============================================
# ============================================
# ⚙️ Hauptfunktion für Datenerhebung & Export
# ============================================
# ============================================

def run_main_logic():
    """
    Führt den kompletten Analyse-Prozess aus:
    - Liest Suchparameter (entweder aus URL oder manueller Eingabe)
    - Fragt passende Ausbildungsangebote von der BA-API ab
    - Bereinigt und prüft alle Ergebnisse
    - Erstellt eine Auswertung nach Bildungsanbietern
    - Exportiert die Ergebnisse in Excel und ggf. JSON
    - Zeigt währenddessen Fortschritte live im Fenster an
    """
    
    # Neues Fenster für Fortschrittsanzeige öffnen
    progress_win, progress_listbox, ok_button = show_progress_window()

    # ------------------------------------------------------------
    # 🧩 Hilfsfunktion: Fortschrittsanzeige aktualisieren
    # ------------------------------------------------------------
    def add_progress(msg):
        """
        Fügt eine neue Zeile in der Fortschrittsliste ein und scrollt automatisch nach unten.
        (Keine .update()-Aufrufe, da das in Tkinter zu Darstellungsproblemen führen kann.)
        """
        progress_listbox.insert(tk.END, msg)
        progress_listbox.yview_moveto(1)
        # Do NOT call .update(), it can cause GUI issues; Tk handles it
        
        
    # ------------------------------------------------------------
    # 🧠 Hintergrundprozess: führt eigentliche Logik aus
    # ------------------------------------------------------------
    def task():
        try:
            # ============================================
            # 🔧 Parameter einlesen
            # ============================================
            if use_url_mode.get():
                # Wenn URL-Modus aktiv: Parameter aus Link parsen
                params = parse_url(url_entry.get())
            else:
                # Wenn manuelle Eingabe aktiv: Werte direkt aus Eingabefeldern übernehmen
                params = {
                    'where': city_entry.get(),
                    'job_id': int(job_id_entry.get()),
                    'radius': int(radius_entry.get()),
                    'lat': float(lat_entry.get()),
                    'lon': float(lon_entry.get()),
                    'bart': int(bart_entry.get())
                }

            # Container für alle gefundenen Angebote & Statistiken
            all_offers = {}
            all_stats = []
            total_raw = 0     # Gesamtanzahl aller eingelesenen Datensätze
            
            root.after(0, lambda: add_progress(f"Suche starten..."))
            
            
            # Übersichtliche Beschriftungen für Parameter
            param_labels = {
                'where': 'Ort',
                'job_id': 'Job ID',
                'radius': 'Radius (km)',
                'lat': 'Breitengrad',
                'lon': 'Längengrad',
                'bart': 'Bildungsart-ID'
            }
            
            # ============================================
            # 📋 Suchparameter im Fortschrittsfenster anzeigen
            # ============================================
            formatted_params = "\n".join(
                f"{param_labels[k]}: {v}" for k, v in params.items()
            )
            root.after(0, add_progress, "===========================")
            time.sleep(0.1)
            root.after(0, add_progress, "Suchparameter:")
            time.sleep(0.1)
            root.after(0, add_progress, "")
            for line in formatted_params.split("\n"):
                root.after(0, add_progress, line)
            root.after(0, add_progress, "")
            
            # ============================================
            # 💾 Aktuelle Exporteinstellungen anzeigen
            # ============================================
            def show_export_setting():
                value = export_json_var.get()
                directory = export_directory.get()
                time.sleep(0.1)
                add_progress(f"als JSON exportieren: {'Ja' if value else 'Nein'}")
                time.sleep(0.1)
                add_progress("Export Verzeichnis:")
                time.sleep(0.1)
                add_progress(f"{directory}")
                time.sleep(0.1)
            root.after(0, show_export_setting)
            time.sleep(0.1)
            root.after(0, add_progress, "===========================")
            time.sleep(0.1)
            root.after(0, lambda:add_progress("Such - Durchlauf läuft..."))
        
            # ============================================
            # 🌐 Ausbildungsangebote über BA-API abrufen
            # ============================================
            offers = get_all_offers(
                params['where'], params['job_id'], params['radius'],
                params['lat'], params['lon'], params['bart']
            )
            
            total_raw += len(offers)
            
            # ------------------------------------------------------------
            # 🧹 Ungültige Einträge entfernen
            # ------------------------------------------------------------
            def is_valid_offer(offer):
                try:
                    # Must have an ID
                    if not offer.get("id"):
                        return False
                    # Must have a title
                    if not offer.get("angebot", {}).get("titel"):
                        return False
                    # Should have a provider
                    if not offer.get("angebot", {}).get("bildungsanbieter", {}).get("name"):
                        return False
                    return True
                except:
                    return False
                
            offers = [o for o in offers if is_valid_offer(o)]

            # ============================================
            # 🧾 Duplikate bereinigen
            # ============================================
        
            unique = {o.get("id"): o for o in offers if o.get("id")}
            new_unique_offers = {
                k: v for k, v in unique.items() if k not in all_offers
            }
        
            # Save only new offers
            all_offers.update(new_unique_offers)
        
            initial_count = len(offers)
            deduped_count = len(unique)
            duplicates_removed = initial_count - deduped_count

            time.sleep(0.1)
            root.after(0, lambda: add_progress(f"{duplicates_removed} doppelte Angebote entfernt"))
            
            # ============================================
            # 📊 Auswertung nach Bildungsanbietern
            # ============================================
            if new_unique_offers:
                stats = count_offers_by_provider(new_unique_offers.values())
                all_stats.append(stats)
        
                total_in_stats = sum(p["count"] for p in stats.values())
                root.after(0, lambda: add_progress(f"{total_in_stats} neue Angebote gefunden"))
        
                # Warnung, falls ein Anbieter auffällig viele Angebote liefert
                for provider_name, p in stats.items():
                    if p.get("count", 0) > params['radius']:
                        root.after(0, lambda pn=provider_name, c=p["count"]: 
                            add_progress(f"⚠️Warnung: Anbieter '{pn}' hat {c} Angebote in diesem Lauf, bitte Anzahl überprüfen!"))
        
            else:
                root.after(0, lambda: add_progress(f"ℹ️ Keine neuen Angebote im Such - Durchlauf."))
        
            root.after(0, lambda n=len(new_unique_offers): add_progress(f"✅ Such - Durchlauf abgeschlossen – {n} neue Angebote gefunden"))
            
            # ============================================
            # 📦 Ergebnisse zusammenfassen & exportieren
            # ============================================
            unique_offers = safeback(all_offers.values())
            merged_stats = count_offers_by_provider(unique_offers.values())


                
            total_offers_final = len(all_offers)
            
            time.sleep(0.1)
            root.after(0, lambda: add_progress(f"Insgesamt {total_offers_final} Angebote gefunden."))
            
            time.sleep(0.1)
            total_removed = total_raw - total_offers_final
            root.after(0, lambda: add_progress(f"Insgesamt {total_removed} doppelte Angebote entfernt ({total_raw} → {total_offers_final})"))
        
            
            unique_offers = safeback(all_offers.values())
            
            time.sleep(0.1)
            root.after(0, add_progress("Fertig!"))
            time.sleep(0.1)
            root.after(0, lambda: add_progress("==========================="))
            time.sleep(0.1)
            root.after(0, lambda: add_progress("✅ Suche abgeschlossen."))
            merged_stats = count_offers_by_provider(unique_offers.values())
            time.sleep(0.1)
            root.after(0, lambda: add_progress(f"{len(unique_offers)} Angebote von {len(merged_stats)} Anbietern können exportiert werden."))
            
            
            # Dateinamen dynamisch anhand Datum, Stadt und Job-ID erzeugen
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            date_time = now.strftime("%H-%M-%S")
            safe_city = params['where']
            # Replace common problematic characters
            safe_city = re.sub(r'[\\/:*?"<>|; ]', '-', safe_city)
            # You might also want to remove leading/trailing underscores
            safe_city = safe_city.strip('_')
            # Ensure it's not empty, or provide a default if it becomes empty
            if not safe_city:
                safe_city = "default_city"
            filename = os.path.join(
                export_directory.get(),
                f"{date_str}_{params['job_id']}_{safe_city}_Arbeitsagentur_Ausbildungssuche_{date_time}.xlsx"
            )

            # ------------------------------------------------------------
            # 💾 Export in Excel + optional JSON
            # ------------------------------------------------------------
            def finalize_export():
                """
                Erstellt die Exportdateien (Excel, optional JSON)
                und zeigt eine Erfolgsmeldung an.
                """
                try:
                    # Get the directory path and ensure it exists
                    export_dir_path = export_directory.get()
                    os.makedirs(export_dir_path, exist_ok=True)
                    
                    export_to_excel(merged_stats, search_url=url_entry.get(), filename=filename)
                    add_progress(f"Excel gespeichert als:\n{filename}")
            
                    if export_json_var.get():
                        json_path = filename.replace(".xlsx", ".json")
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(unique_offers, f, ensure_ascii=False, indent=4)
                        add_progress(f"JSON gespeichert als:\n{json_path}")
            
                    add_progress("Export abgeschlossen.")
                    messagebox.showinfo(
                        "Fertig",
                        f"{len(all_offers)} Angebote von {len(merged_stats)} Anbietern wurden exportiert."
                    )
                    progress_win.destroy()
            
                except Exception as e:
                    messagebox.showerror("Fehler beim Export", str(e))

        
            root.after(0, lambda: ok_button.config(state="normal", command=finalize_export))
            
            # Export-Button aktivieren, sobald alles fertig ist
            ok_button.config(state="normal", command=finalize_export)

        except Exception as e:
            print("Fehler aufgetreten:", str(e))
            traceback.print_exc()
            root.after(0, lambda e=e: messagebox.showerror("Fehler", str(e)))


    # ============================================
    # 🧵 Startet den Prozess in einem separaten Thread
    # ============================================
    threading.Thread(target=task, daemon=True).start()



# ============================================
# 📘 GUI
# ============================================
# 📘 Hier beginnt der GUI Abschnitt
# ============================================
root = tk.Tk()
def on_close():
    # Optionally confirm with the user
    if messagebox.askokcancel("Beenden", "Möchten Sie die Anwendung wirklich schließen?"):
        root.quit()     # Exit the Tkinter mainloop
        root.destroy()  # Destroy all widgets and properly clean up

def clear_placeholder(event):
    if url_entry.get() == placeholder:
        url_entry.delete(0, tk.END)
        url_entry.configure(style="Normal.TEntry")

def restore_placeholder(event):
    if not url_entry.get():
        url_entry.insert(0, placeholder)
        url_entry.configure(style="Placeholder.TEntry")
        
root.protocol("WM_DELETE_WINDOW", on_close)

root.title("Ausbildungsangebote-Analyse v1")
root.geometry("800x650")  # Adjusted to fit long link and spacing

use_url_mode = tk.BooleanVar(value=True)
export_json_var = tk.BooleanVar(value=False)

# ============================================
# 📘 Guide- und Readme Text
# ============================================

guide_text = (
    "👋 Willkommen! Dieses Tool zeigt dir, wie viele Wettbewerber in deiner Stadt\n "
    "für unsere Umschulungen aktiv sind – z. B. KABÜ, KITS, FISI oder FIAE.\n\n"
    "Du kannst es auch für andere Ausbildungsangebote nutzen, etwa um neue Themen\n "
    "oder Standorte zu prüfen.\n\n"
    "👉 Wähle einfach, wie du suchen möchtest:\n"
    "• über einen vollständigen Link von der BA-Seite,\n"
    "• über mehrere Links gleichzeitig, oder\n"
    "• manuell mit Stadt, Berufs-ID und Radius.\n"
)
tk.Label(root, text=guide_text, justify="left", wraplength=880, fg="gray25").grid(row=0, column=0, columnspan=3, pady=(10, 5), padx=(20,0), sticky="w")

readme_text = (
    "📘 **Anleitung & Hintergrund**\n\n"
    "Dieses Tool hilft dir dabei, die Ausbildungsangebote der Bundesagentur für Arbeit (BA) "
    "zu analysieren – speziell mit Blick auf unsere Umschulungen wie KABÜ, KITS, FISI oder FIAE.\n"
    "So kannst du schnell erkennen, welche Wettbewerber in einer Region aktiv sind, "
    "und Trends bei neuen Bildungsangeboten einschätzen.\n\n"
    "Dieses Tool durchsucht die öffentlichen Ausbildungsangebote der Bundesagentur für Arbeit (BA)\n" 
    "über die offizielle API und wertet sie strukturiert aus.\n" 
    "Es eignet sich ideal zur Analyse von Anbietern, Kursen und Standorten bei Umschulungen und Ausbildungen.\n\n"

    "✅ **Was das Tool für dich macht:**\n"
    "• Automatisiertes Abrufen von Ausbildungsangeboten über Link oder manuelle Eingabe\n" 
    "• Verarbeitung einzelner oder mehrerer Links (je Zeile ein Link)\n" 
    "• Entfernung von Duplikaten und Filterung ungültiger Angebote\n" 
    "• Gruppierung und Zählung der Angebote pro Bildungsanbieter\n" 
    "• Export als Excel (.xlsx) oder optional als JSON\n\n"

    "🚀 **So nutzt du das Tool Schritt für Schritt:**\n"
    "1. Öffne die Website der BA-Ausbildungssuche und kopiere einen vollständigen Link "
    "(z. B. mit 'beruf=1234&ort=Berlin_...')\n"
    "2. Wähle, wie du arbeiten möchtest:\n"
    " • ✅ 'URL für Parameter verwenden' – für einen einzelnen Link\n" 
    " • ✅ 'Mehrere Links verarbeiten' – für mehrere Links (je Zeile ein Link)\n" 
    " • ❌ Beides deaktivieren – um manuell Stadt, ID, Radius etc. einzugeben\n"
    "3. Klicke auf 'Start' – das Tool liest die Daten aus und zeigt dir die Ergebnisse.\n"
    "4. Du kannst die Ergebnisse danach exportieren – als Excel (Übersicht) oder JSON (Detaildaten).\n\n"


    "⚠️ Wichtige Hinweise & Einschränkungen:\n" 
    "• Nur Links mit einer konkreten Job-ID ('beruf=...') funktionieren\n" 
    "• Implizite Suchanfragen ohne ID werden nicht unterstützt\n" 
    "• Wenn mehr als 50 Angebote im Radius liegen, können nicht alle Ergebnisse\n" 
    " von der API zurückgegeben werden (API-Beschränkung)\n" 
    "• Anbieter wie 'WBS TRAINING AG' oder 'karriere tutor' liefern über die API\n" 
    " manchmal mehr Angebote als auf der Website sichtbar sind\n" 
    "• Ungültige Einträge (z. B. ohne ID oder Anbietername) werden übersprungen\n" 
    "• Dieses Tool arbeitet asynchron und parallelisiert, dennoch ist mit Ladezeiten\n" 
    " bei vielen Treffern zu rechnen.\n\n"

    "📁 **Empfehlung für die Auswertung:**\n"
    "• Verwende die Excel-Datei für eine schnelle Übersicht oder zur Weitergabe im Team.\n"
    "• Nutze den JSON-Export für tiefergehende Analysen oder zur internen Weiterverarbeitung.\n\n"

    "🧩 **Technischer Hintergrund:**\n"
    "Das Tool nutzt die öffentliche API der Bundesagentur für Arbeit, um Ausbildungsangebote "
    "automatisiert abzufragen und strukturiert auszuwerten.\n\n"
    "• API-Dokumentation: https://ausbildungssuche.api.bund.dev/\n"
    "• GitHub-Projekt (open source): https://github.com/florianfreund/APISearch\n"
)



# Textfeld mit möglichen Bildungsarten
bart_text = (
    "Bildungsarten: \n"
    "100=Allgemeinbildung, 101=Teilqualifizierung, 102=Berufsausbildung, \n"
    "103=Gesetzlich/gesetzesähnlich geregelte Fortbildung/Qualifizierung, \n"
    "104=Fortbildung/Qualifizierung, 105=Abschluss nachholen, 106=Rehabilitation, \n"
    "107108=Studienangebot - grundständig, 109=Umschulung"
)

# ============================================
# 📘 GUI-Abschnitt für "README / Anleitung"
# ============================================


def show_readme_window():
    """
    Öffnet ein neues Fenster mit einer Anleitung oder Beschreibung des Programms.
    Der Text (readme_text + bart_text) wird in einem scrollbaren Textfeld angezeigt.
    """
    readme_win = tk.Toplevel(root) # Neues Unterfenster neben dem Hauptfenster
    readme_win.title("📖 Anleitung und Hinweise")
    readme_win.geometry("780x500")
    readme_win.resizable(True, True)

    # Container-Frame für einheitliche ttk-Gestaltung
    container = ttk.Frame(readme_win, padding=10)
    container.pack(fill="both", expand=True)

    # Vertikale Scrollbar für das Textfeld
    scrollbar = ttk.Scrollbar(container, orient="vertical")
    scrollbar.pack(side="right", fill="y")

    # Textfeld, in das der Hilfetext eingefügt wird
    text_widget = tk.Text(
        container,
        wrap="word",             # Zeilenumbruch nach Wörtern
        yscrollcommand=scrollbar.set,
        bg="white",
        fg="black",
        font=("Segoe UI", 10),
        relief="solid",
        borderwidth=1,
        padx=10,
        pady=10
    )
    text_widget.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=text_widget.yview)

    # Anleitungstext einfügen und Schreibschutz aktivieren
    text_widget.insert("1.0", readme_text + "\n\n\n" + bart_text)
    text_widget.config(state="disabled")


readme_button = tk.Button(
    root,
    text="📖 read Me",
    command=show_readme_window,
    bg="#d0e4f7",       # light blue background
    fg="black",         # text color
    font=("Segoe UI", 10, "bold"),
    padx=10,
    pady=5,
    relief="raised",
    borderwidth=2
)
readme_button.grid(row=0, column=1, sticky="e", padx=10, pady=10)


# ============================================
# 🔗 Eingabefeld für URL (Einzeln oder Mehrfach)
# ============================================

# ttk-Stile für Platzhalter- und normale Eingaben
style = ttk.Style()
style.configure("Placeholder.TEntry", foreground="gray")
style.configure("Normal.TEntry", foreground="black")

# Beschriftung des URL-Felds
ttk.Label(root, text="Vollständiger Link:").grid(row=1, column=0, sticky="e", padx=5, pady=5)

# Platzhaltertext für das URL-Feld
placeholder = "https://web.arbeitsagentur.de/ausbildungssuche/......beispiellink......."

# URL-Eingabefeld (einzelner Link)
url_entry = ttk.Entry(root, width=80, style="Placeholder.TEntry")
url_entry.insert(0, placeholder)
url_entry.grid(row=1, column=1, columnspan=2, sticky="we", padx=5, pady=5)

# Platzhalter-Funktionalität aktivieren
url_entry.bind("<FocusIn>", clear_placeholder)
url_entry.bind("<FocusOut>", restore_placeholder)

# Variable zur Steuerung, ob Mehrfach-URL-Modus aktiv ist
multi_url_mode = tk.BooleanVar(value=False)


# ============================================
# 🔁 Funktion zum Umschalten zwischen Einzel- und Mehrfach-Link-Modus
# ============================================


def toggle_multi_url_mode():
    """
    Aktiviert/Deaktiviert den Mehrfach-Link-Modus.
    - Wenn aktiv: Einzelnes URL-Feld wird gesperrt, Mehrzeilenfeld wird aktiv.
    - Wenn inaktiv: Umgekehrt.
    """
    if multi_url_mode.get():
        # Mehrfachmodus aktiv → Einzel-URL-Feld sperren
        url_entry.config(state='disabled')
        checkbox_url.config(state='disabled')
        multi_url_text.config(state='normal')
        use_url_mode.set(True)
        toggle_input_mode()
        parse_button.config(state='disabled')
        url_entry.config(state='disabled')
    else:
        # Einzelmodus aktiv → Textfeld sperren
        url_entry.config(state='normal')
        multi_url_text.config(state='disabled')
        checkbox_url.config(state='normal')
        parse_button.config(state='normal')
        url_entry.config(state='normal')

# Checkbox zur Aktivierung des Mehrfach-Link-Modus
ttk.Checkbutton(
    root,
    text="Mehrere Links verarbeiten",
    variable=multi_url_mode,
    command=toggle_multi_url_mode
).grid(row=4, column=1, sticky="w", padx=5, pady=5)

# Beschriftung für das Mehrzeilenfeld
ttk.Label(root, text="Mehrere Links (je Zeile ein Link):").grid(row=3, column=0, sticky="e")

# Frame als Container für das Textfeld (optisch wie ein Entry-Feld)
multi_url_frame = ttk.Frame(root)
multi_url_frame.grid(row=3, column=1, columnspan=2, sticky="we", padx=5, pady=5)

# Standard-Schriftart aus ttk übernehmen
default_font = ttk.Style().lookup("TEntry", "font")

# Mehrzeilen-Textfeld für mehrere URLs
multi_url_text = tk.Text(
    multi_url_frame,
    height=5,
    width=80,
    wrap="none",
    font=default_font,
    relief="solid",
    borderwidth=1,
    background="white",
    highlightthickness=0,
    state="disabled"
)


multi_url_text.grid(row=3, column=1, columnspan=2, sticky="we", padx=5)


# ============================================
# 🧭 Optionen und Parameter-Eingabefelder
# ============================================

# Checkbox: Soll die URL direkt für Parameter verwendet werden?
checkbox_url = ttk.Checkbutton(root, text="URL für Parameter verwenden", variable=use_url_mode, command=toggle_input_mode)
checkbox_url.grid(row=2, column=1, columnspan=2, sticky="w", pady=(5, 10))

# Button, um aus der URL Parameter automatisch auszulesen
parse_button = ttk.Button(root, text="🔍 Link auslesen", command=populate_fields_from_link)
parse_button.grid(row=2, column=2, sticky="e", padx=(5, 10))

# ============================================
# 📥 MANUELLE PARAMETER-EINGABE
# ============================================

# Diese Felder werden verwendet, wenn keine URL geparst wird
# (also im manuellen Modus)
ttk.Label(root, text="Stadt (z.B. Berlin):").grid(row=5, column=0, sticky="e")
city_entry = ttk.Entry(root)
city_entry.insert(0, "Berlin")
city_entry.grid(row=5, column=1)

ttk.Label(root, text="Berufs-ID:").grid(row=6, column=0, sticky="e")
job_id_entry = ttk.Entry(root)
job_id_entry.insert(0, "7856")
job_id_entry.grid(row=6, column=1)

ttk.Label(root, text="Radius (km):").grid(row=7, column=0, sticky="e")
radius_entry = ttk.Entry(root)
radius_entry.insert(0, "50")
radius_entry.grid(row=7, column=1)

ttk.Label(root, text="Breitengrad (lat):").grid(row=8, column=0, sticky="e")
lat_entry = ttk.Entry(root)
lat_entry.insert(0, "52.531976")
lat_entry.grid(row=8, column=1)

ttk.Label(root, text="Längengrad (lon):").grid(row=9, column=0, sticky="e")
lon_entry = ttk.Entry(root)
lon_entry.insert(0, "13.386738")
lon_entry.grid(row=9, column=1)

ttk.Label(root, text="Bildungsart (Umschulung = 109):").grid(row=10, column=0, sticky="e")
bart_entry = ttk.Entry(root)
bart_entry.insert(0, "109")
bart_entry.grid(row=10, column=1)


# ============================================
# 💾 EXPORT-EINSTELLUNGEN
# ============================================

# Variable speichert das aktuelle Exportverzeichnis
export_directory = tk.StringVar(value=os.getcwd())

# Button: Benutzer kann Exportverzeichnis auswählen
ttk.Button(root, text="📁 Exportverzeichnis auswählen", command=select_export_directory).grid(
    row=11, column=0, pady=(5, 0), padx=(30, 0), sticky="e"
)

# Label zeigt das aktuell gewählte Verzeichnis an
export_path_label = tk.Label(root, textvariable=export_directory, fg="gray30", anchor="w", wraplength=500)
export_path_label.grid(row=11, column=1, sticky="w", padx=(20, 10), pady=(5, 0))

# Checkbox: Soll das komplette Suchergebnis als JSON-Datei exportiert werden?
export_json_checkbox = ttk.Checkbutton(root, text="komplettes Suchergebnis als JSON exportieren", variable=export_json_var)
export_json_checkbox.grid(row=12, column=1, sticky="w", pady=(5, 0), padx=(30, 0))


# ============================================
# ▶️ START-BUTTON UND HAUPTAKTION
# ============================================

def on_start_button_click():
    """
    Wird aufgerufen, wenn der Benutzer auf 'Start' klickt.
    - Prüft Eingaben
    - Startet die Hauptlogik (einzeln oder mehrfach)
    """
    # Eingaben überprüfen
    if not validate_inputs():
        return
    
    # Wenn Mehrfach-Link-Modus aktiv ist
    if multi_url_mode.get():
        urls = multi_url_text.get("1.0", tk.END).strip().splitlines()
        urls = [url.strip() for url in urls if url.strip()]
        
        # Wenn keine gültigen Links eingegeben wurden → Warnung
        if not urls:
            messagebox.showwarning("Keine Links", "Bitte geben Sie mindestens einen gültigen Link ein.")
            return

        # Funktion, um alle Links nacheinander zu verarbeiten
        def run_all_links():
            for url in urls:
                url_entry.config(state="normal")
                url_entry.delete(0, tk.END)
                url_entry.insert(0, url)
                run_main_logic()
                time.sleep(2)  # kurze Pause zwischen den Ausführungen

        # Verarbeitung in separatem Thread starten (GUI bleibt reaktionsfähig)
        threading.Thread(target=run_all_links, daemon=True).start()

    else:
        # Einzel-Link-Modus: direkt Hauptlogik starten
        run_main_logic()

# Start-Button in der GUI
ttk.Button(root, text="Start", command=on_start_button_click).grid(row=13, column=0, columnspan=3, pady=15)

# ============================================
# 🔧 INITIALISIERUNG & PROGRAMMSTART
# ============================================

# Aktiviert oder deaktiviert Eingabefelder je nach aktivem Modus
toggle_input_mode()

# Startet die Haupt-Event-Schleife der Tkinter-GUI
root.mainloop()