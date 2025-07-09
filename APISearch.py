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
# API session
session = requests.Session()
session.headers.update({
    'User-Agent': 'Ausbildungssuche/1.0 (de.arbeitsagentur.ausbildungssuche)',
    'Host': 'rest.arbeitsagentur.de',
    'X-API-Key': 'infosysbub-absuche',
    'Connection': 'keep-alive',
})

def haversine(lat1, lon1, lat2, lon2):
    R = 6378
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

def is_within_radius(offer, center_lat, center_lon, radius_km):
    try:
        # Safely access coordinates, returning False if any key is missing
        if 'adresse' not in offer or \
           'ortStrasse' not in offer['adresse'] or \
           'koordinaten' not in offer['adresse']['ortStrasse']:
            return False

        coords = offer['adresse']['ortStrasse']['koordinaten']

        # Ensure lat and lon keys exist and their values are not None
        if 'lat' not in coords or coords['lat'] is None or \
           'lon' not in coords or coords['lon'] is None:
            print(f"Warning: Missing or None 'lat' or 'lon' in coordinates for offer: {offer.get('id', 'N/A')}")
            return False

        # Attempt to convert to float. If this fails, it's a TypeError/ValueError
        offer_lat = float(coords['lat'])
        offer_lon = float(coords['lon'])

        return haversine(center_lat, center_lon, offer_lat, offer_lon) <= radius_km

    except (ValueError, TypeError) as e:
        # Catch errors if 'lat' or 'lon' values are not convertible to float
        #some offers doesnt have coords, these are catched here
        #print(f"Error processing coordinates for offer: {offer.get('id', 'N/A')}. Error: {e}")
        return False
    except Exception as e:
        # Catch any other unexpected errors, although the checks above should prevent most
        print(f"An unexpected error occurred in is_within_radius for offer {offer.get('id', 'N/A')}: {e}")
        return False
    
    
def search(page, where, job_id, radius, bart):
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


# parallelized fetching of pages
def get_all_offers(where, job_id, radius, lat, lon, bart):
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

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch_page, p) for p in range(1, total_pages)]
        for f in futures:
            try:
                all_offers.extend(f.result())
            except Exception as e:
                print(f"Fehler bei Seite: {e}")

    return all_offers




def count_offers_by_provider(data):
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
    for provider in provider_data:
        provider_data[provider]['count'] = len(provider_data[provider]['ids'])
    return provider_data


def export_to_excel(data, search_url, filename='anbieter_stats.xlsx'):
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


def toggle_input_mode():
    """Enable/disable manual fields depending on checkbox."""
    state = 'disabled' if use_url_mode.get() else 'normal'
    for widget in [city_entry, job_id_entry, radius_entry, lat_entry, lon_entry, bart_entry]:
        widget.config(state=state)
    url_entry.config(state='normal' if use_url_mode.get() else 'disabled')

def parse_url(url):
    """Extract parameters from Arbeitsagentur Ausbildungssuche URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    job_id = int(qs.get('beruf', ['0'])[0])
    radius = int(qs.get('uk', ['0'])[0])
    kat = qs.get('kat', [''])[0]

    # 'Berlin_13.386738_52.531976' → Ort, lon, lat
    ort_parts = qs.get('ort', [''])[0].split('_')
    if len(ort_parts) == 3:
        city, lon, lat = ort_parts
    else:
        raise ValueError("Ungültiges 'ort'-Feld im Link.")

    # Reverse mapping: UI index → BART code
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



def populate_fields_from_link():
    if not use_url_mode.get():
        messagebox.showwarning("Hinweis", "Bitte aktiviere zuerst die Link-Eingabe-Option.")
        return

    try:
        url = url_entry.get()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        city = params.get("ort", [""])[0].split("_")[0]
        lon = float(params.get("ort", [""])[0].split("_")[1])
        lat = float(params.get("ort", [""])[0].split("_")[2])
        radius = int(params.get("uk", [50])[0])
        job_id = int(params.get("beruf", [0])[0])
        kat = int(params.get("kat", [1])[0])

        bart_map = {1: 109, 0: 102, 2: 101, 3: 105}
        bart = bart_map.get(kat, 109)

        # Temporarily enable fields
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

        # After populating, disable again
        if use_url_mode.get():
            for field in [city_entry, job_id_entry, radius_entry, lat_entry, lon_entry, bart_entry]:
                field.config(state="disabled")

    except Exception as e:
        messagebox.showerror("Fehler beim Auslesen des Links", str(e))

def toggle_input_mode():
    """Enable/disable manual fields depending on checkbox."""
    if use_url_mode.get():
        for entry in [city_entry, job_id_entry, radius_entry, lat_entry, lon_entry, bart_entry]:
            entry.config(state="disabled")
        parse_button.config(state="normal")
        url_entry.config(state="normal")  # Always enable this
    else:
        for entry in [city_entry, job_id_entry, radius_entry, lat_entry, lon_entry, bart_entry]:
            entry.config(state="normal")
        parse_button.config(state="disabled")
        url_entry.config(state="disabled")  # Always enable this


        

def show_progress_window():
    progress_win = tk.Toplevel(root)
    progress_win.title("Lade Angebote...")
    progress_win.geometry("600x300")
    progress_win.resizable(False, False)
    
    # Make sure this window stays on top
    # progress_win.attributes('-topmost', True)
    progress_win.lift()  # Bring it to the front

    ttk.Label(progress_win, text="Suche läuft...", font=("Arial", 12, "bold")).pack(pady=(10, 5))

    frame = ttk.Frame(progress_win)
    frame.pack(padx=10, pady=5, fill="both", expand=True)

    scrollbar = ttk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")

    listbox = tk.Listbox(frame, height=10, yscrollcommand=scrollbar.set)
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=listbox.yview)

    button_frame = ttk.Frame(progress_win)
    button_frame.pack(pady=10)


    ok_button = tk.Button(progress_win, text="Export starten", state="disabled", bg="lightgreen", fg="black")
    ok_button.pack(side="right", padx=10, pady=10)

    return progress_win, listbox, ok_button

def select_export_directory():
    directory = filedialog.askdirectory()
    if directory:
        export_directory.set(directory)

def validate_inputs():
    try:
        int(job_id_entry.get())
        int(radius_entry.get())
        float(lat_entry.get())
        float(lon_entry.get())
        int(bart_entry.get())

        # Add checks for city_entry and url_entry if needed (e.g., not empty)
        return True
    except ValueError:
        messagebox.showerror("Eingabefehler", "Bitte stellen Sie sicher, dass alle numerischen Felder gültige Zahlen enthalten.")
        return False
    
    
def safeback(offers):
    """
    Filters and deduplicates offers by their ID.
    Returns a new dictionary of unique offers.
    Offers without IDs are skipped.
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



def run_main_logic():
    progress_win, progress_listbox, ok_button = show_progress_window()

    def add_progress(msg):
        progress_listbox.insert(tk.END, msg)
        progress_listbox.yview_moveto(1)
        # Do NOT call .update(), it can cause GUI issues; Tk handles it

    def task():
        try:
            if use_url_mode.get():
                params = parse_url(url_entry.get())
            else:
                params = {
                    'where': city_entry.get(),
                    'job_id': int(job_id_entry.get()),
                    'radius': int(radius_entry.get()),
                    'lat': float(lat_entry.get()),
                    'lon': float(lon_entry.get()),
                    'bart': int(bart_entry.get())
                }


            all_offers = {}
            all_stats = []
            total_raw = 0
            
            root.after(0, lambda: add_progress(f"Suche starten..."))
            
            param_labels = {
                'where': 'Ort',
                'job_id': 'Job ID',
                'radius': 'Radius (km)',
                'lat': 'Breitengrad',
                'lon': 'Längengrad',
                'bart': 'Bildungsart-ID'
            }
            
            #Suchparameter debug
            formatted_params = "\n".join(
                f"{param_labels[k]}: {v}" for k, v in params.items()
            )
            root.after(20, add_progress, "===========================")
            root.after(20, add_progress, "Suchparameter:")
            root.after(20, add_progress, "")
            for line in formatted_params.split("\n"):
                root.after(10, add_progress, line)
            root.after(0, add_progress, "")
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
            root.after(10, show_export_setting)
            root.after(10, add_progress, "===========================")

            

            root.after(0, lambda:add_progress("Such - Durchlauf läuft..."))
        
            offers = get_all_offers(
                params['where'], params['job_id'], params['radius'],
                params['lat'], params['lon'], params['bart']
            )
            
            total_raw += len(offers)
            
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

    
        
            unique = {o.get("id"): o for o in offers if o.get("id")}
        
            # Determine new offers not already stored
            new_unique_offers = {
                k: v for k, v in unique.items() if k not in all_offers
            }
        
            # Save only new offers
            all_offers.update(new_unique_offers)
        
            initial_count = len(offers)
            deduped_count = len(unique)
            duplicates_removed = initial_count - deduped_count


            root.after(20, lambda: add_progress(f"{duplicates_removed} doppelte Angebote entfernt"))
            
            # Count stats ONLY for this round's new offers
            if new_unique_offers:
                stats = count_offers_by_provider(new_unique_offers.values())
                all_stats.append(stats)
        
                total_in_stats = sum(p["count"] for p in stats.values())
                root.after(10, lambda: add_progress(f"{total_in_stats} neue Angebote gefunden"))
        
                # Warn if any provider exceeds 50 in this run
                for provider_name, p in stats.items():
                    if p.get("count", 0) > params['radius']:
                        root.after(10, lambda pn=provider_name, c=p["count"]: 
                            add_progress(f"⚠️Warnung: Anbieter '{pn}' hat {c} Angebote in diesem Lauf, bitte Anzahl überprüfen!"))
        
            else:
                root.after(0, lambda: add_progress(f"Keine neuen Angebote im Such - Durchlauf."))
        
            root.after(0, lambda n=len(new_unique_offers): add_progress(f"Such - Durchlauf abgeschlossen – {n} neue Angebote gefunden"))
            unique_offers = safeback(all_offers.values())
            merged_stats = count_offers_by_provider(unique_offers.values())


                
            total_offers_final = len(all_offers)
                
            root.after(10, lambda: add_progress(f"Insgesamt {total_offers_final} Angebote gefunden."))
            
            total_removed = total_raw - total_offers_final
            root.after(10, lambda: add_progress(f"Insgesamt {total_removed} doppelte Angebote entfernt ({total_raw} → {total_offers_final})"))
        
            
            unique_offers = safeback(all_offers.values())

            root.after(10, add_progress("Fertig!"))
            merged_stats = count_offers_by_provider(unique_offers.values())
            root.after(10, lambda: add_progress(f"{len(unique_offers)} Angebote von {len(merged_stats)} Anbietern können exportiert werden."))

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

            def finalize_export():
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
            
            # Enable and show the export button
            ok_button.config(state="normal", command=finalize_export)

        except Exception as e:
            print("Fehler aufgetreten:", str(e))
            traceback.print_exc()
            root.after(0, lambda e=e: messagebox.showerror("Fehler", str(e)))

    # Run the background task in a thread
    threading.Thread(target=task, daemon=True).start()


# === GUI ===
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
root.geometry("800x600")  # Adjusted to fit long link and spacing

use_url_mode = tk.BooleanVar(value=True)
export_json_var = tk.BooleanVar(value=False)

# === Guide Text ===
guide_text = (
    "🔍 Dieses Tool analysiert Ausbildungsangebote der Bundesagentur für Arbeit.\n\n"
    "Sie haben drei Möglichkeiten zur Eingabe:\n"
    "• Fügen Sie einen vollständigen Link von der Website ein, oder\n"
    "• Fügen Sie einen Liste vollständiger Links von der Website ein \n"
    "  (entsprechende Checkbox aktivieren), oder\n"
    "• Geben Sie die Suchparameter manuell ein (entsprechende Checkbox deaktivieren).\n\n"
    )
tk.Label(root, text=guide_text, justify="left", wraplength=880, fg="gray25").grid(row=0, column=0, columnspan=3, pady=(10, 5), padx=(20,0), sticky="w")

readme_text = (
    "📘 Einführung & Anleitung (readMe)\n\n"
    "🔍 Was macht dieses Tool?\n"
    "Dieses Tool durchsucht die öffentlichen Ausbildungsangebote der Bundesagentur für Arbeit (BA)\n"
    "über die offizielle API und wertet sie strukturiert aus.\n"
    "Es eignet sich ideal zur Analyse von Anbietern, Kursen und Standorten bei Umschulungen und Ausbildungen.\n\n"

    "✅ Funktionen im Überblick:\n"
    "• Automatisiertes Abrufen von Ausbildungsangeboten über Link oder manuelle Eingabe\n"
    "• Verarbeitung einzelner oder mehrerer Links (je Zeile ein Link)\n"
    "• Entfernung von Duplikaten und Filterung ungültiger Angebote\n"
    "• Gruppierung und Zählung der Angebote pro Bildungsanbieter\n"
    "• Export als Excel (.xlsx) oder optional als JSON\n\n"

    "🛠️ So funktioniert's:\n"
    "1. Öffne die Website der BA-Ausbildungssuche und kopiere einen vollständigen Link\n"
    "   (z. B. mit 'beruf=1234&ort=Berlin_...')\n"
    "2. Wähle aus:\n"
    "   • ✅ 'URL für Parameter verwenden' – für einen einzelnen Link\n"
    "   • ✅ 'Mehrere Links verarbeiten' – für mehrere Links (je Zeile ein Link)\n"
    "   • ❌ Beides deaktivieren – um manuell Stadt, ID, Radius etc. einzugeben\n"
    "3. Klicke auf 'Start', um die Suche zu starten\n"
    "4. Exportiere Ergebnisse per Button in Excel und/oder JSON\n\n"

    "⚠️ Wichtige Hinweise & Einschränkungen:\n"
    "• Nur Links mit einer konkreten Job-ID ('beruf=...') funktionieren\n"
    "• Implizite Suchanfragen ohne ID werden nicht unterstützt\n"
    "• Wenn mehr als 50 Angebote im Radius liegen, können nicht alle Ergebnisse\n"
    "  von der API zurückgegeben werden (API-Beschränkung)\n"
    "• Anbieter wie 'WBS TRAINING AG' oder 'karriere tutor' liefern über die API\n"
    "  manchmal mehr Angebote als auf der Website sichtbar sind\n"
    "• Ungültige Einträge (z. B. ohne ID oder Anbietername) werden übersprungen\n"
    "• Dieses Tool arbeitet asynchron und parallelisiert, dennoch ist mit Ladezeiten\n"
    "  bei vielen Treffern zu rechnen.\n\n"

    "📁 Empfehlung:\n"
    "• Verwende den JSON-Export für tiefere Auswertungen und für eigene Analysen.\n"
    "• Nutze die Excel-Datei zur schnellen Übersicht oder Weitergabe\n\n"
    
    "🛠️ Dokumentation der API:\n"
    "• https://ausbildungssuche.api.bund.dev/ \n"
    "• https://github.com/AndreasFischer1985/ausbildungssuche-api \n\n"
    
    "🛠️Quellcode:\n"
    "• https://github.com/florianfreund/APISearch \n"
)


bart_text = (
    "Bildungsarten: \n"
    "100=Allgemeinbildung, 101=Teilqualifizierung, 102=Berufsausbildung, \n"
    "103=Gesetzlich/gesetzesähnlich geregelte Fortbildung/Qualifizierung, \n"
    "104=Fortbildung/Qualifizierung, 105=Abschluss nachholen, 106=Rehabilitation, \n"
    "107108=Studienangebot - grundständig, 109=Umschulung"
)

def show_readme_window():
    readme_win = tk.Toplevel(root)
    readme_win.title("📖 Anleitung und Hinweise")
    readme_win.geometry("780x500")
    readme_win.resizable(True, True)

    # Frame for consistent ttk styling
    container = ttk.Frame(readme_win, padding=10)
    container.pack(fill="both", expand=True)

    # Scrollbar
    scrollbar = ttk.Scrollbar(container, orient="vertical")
    scrollbar.pack(side="right", fill="y")

    # Text widget
    text_widget = tk.Text(
        container,
        wrap="word",
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

    # Insert content
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

# === Link Field ======
# === Styles ===
style = ttk.Style()
style.configure("Placeholder.TEntry", foreground="gray")
style.configure("Normal.TEntry", foreground="black")

# === Layout ===
ttk.Label(root, text="Vollständiger Link:").grid(row=1, column=0, sticky="e", padx=5, pady=5)

placeholder = "https://web.arbeitsagentur.de/ausbildungssuche/......beispiellink......."

url_entry = ttk.Entry(root, width=80, style="Placeholder.TEntry")
url_entry.insert(0, placeholder)
url_entry.grid(row=1, column=1, columnspan=2, sticky="we", padx=5, pady=5)

url_entry.bind("<FocusIn>", clear_placeholder)
url_entry.bind("<FocusOut>", restore_placeholder)

multi_url_mode = tk.BooleanVar(value=False)



def toggle_multi_url_mode():
    if multi_url_mode.get():
        url_entry.config(state='disabled')
        checkbox_url.config(state='disabled')
        multi_url_text.config(state='normal')
        use_url_mode.set(True)
        toggle_input_mode()
        parse_button.config(state='disabled')
        url_entry.config(state='disabled')
    else:
        url_entry.config(state='normal')
        multi_url_text.config(state='disabled')
        checkbox_url.config(state='normal')
        parse_button.config(state='normal')
        url_entry.config(state='normal')

# Checkbox to enable multi-link mode
ttk.Checkbutton(
    root,
    text="Mehrere Links verarbeiten",
    variable=multi_url_mode,
    command=toggle_multi_url_mode
).grid(row=4, column=1, sticky="w", padx=5, pady=5)

# === Label (same style as single link) ===
ttk.Label(root, text="Mehrere Links (je Zeile ein Link):").grid(row=3, column=0, sticky="e")

# === Frame wrapper to mimic ttk.Entry padding and structure ===
multi_url_frame = ttk.Frame(root)
multi_url_frame.grid(row=3, column=1, columnspan=2, sticky="we", padx=5, pady=5)

# === Styled tk.Text inside frame ===
default_font = ttk.Style().lookup("TEntry", "font")

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








# === Checkbox + Parse Button ===
checkbox_url = ttk.Checkbutton(root, text="URL für Parameter verwenden", variable=use_url_mode, command=toggle_input_mode)
checkbox_url.grid(row=2, column=1, columnspan=2, sticky="w", pady=(5, 10))

parse_button = ttk.Button(root, text="🔍 Link auslesen", command=populate_fields_from_link)
parse_button.grid(row=2, column=2, sticky="e", padx=(5, 10))

# === Input Fields (disabled if URL mode is active) ===
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


export_directory = tk.StringVar(value=os.getcwd())


# Button to choose directory
ttk.Button(root, text="📁 Exportverzeichnis auswählen", command=select_export_directory).grid(
    row=11, column=0, pady=(5, 0), padx=(30, 0), sticky="e"
)

# Directory path label
export_path_label = tk.Label(root, textvariable=export_directory, fg="gray30", anchor="w", wraplength=500)
export_path_label.grid(row=11, column=1, sticky="w", padx=(20, 10), pady=(5, 0))

# Checkbox to Export Full JSON
export_json_checkbox = ttk.Checkbutton(root, text="komplettes Suchergebnis als JSON exportieren", variable=export_json_var)
export_json_checkbox.grid(row=12, column=1, sticky="w", pady=(5, 0), padx=(30, 0))


# === Start Button ===
# In your main script, where you define the button:
def on_start_button_click():
    if not validate_inputs():
        return

    if multi_url_mode.get():
        urls = multi_url_text.get("1.0", tk.END).strip().splitlines()
        urls = [url.strip() for url in urls if url.strip()]
        if not urls:
            messagebox.showwarning("Keine Links", "Bitte geben Sie mindestens einen gültigen Link ein.")
            return

        # Launch each link as a separate thread/run
        def run_all_links():
            for url in urls:
                url_entry.config(state="normal")
                url_entry.delete(0, tk.END)
                url_entry.insert(0, url)
                run_main_logic()
                time.sleep(2)  # Small pause between runs

        threading.Thread(target=run_all_links, daemon=True).start()

    else:
        run_main_logic()


ttk.Button(root, text="Start", command=on_start_button_click).grid(row=13, column=0, columnspan=3, pady=15)

# === Enable/Disable Fields Accordingly ===
toggle_input_mode()

root.mainloop()