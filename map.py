import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster, Fullscreen
import requests
import time
import json
import os
import csv

token_secret = "api_key.secret"
feature_codes_file = "featureCodes_en.csv"
output_file_name = "AQI_map_Slovakia.html"

def load_token(token_secret):
    if os.path.exists(token_secret):
        with open(token_secret, "r") as f:
            TOKEN = f.read().strip()
            if TOKEN != "":
                print("✅ Token loaded from secret file.")
                time.sleep(3)
            else:
                print("🔐 API token not found.")
                TOKEN = input("Please paste your AQI API token: ").strip()
                with open(token_secret, "w") as f:
                    f.write(TOKEN)
                print("✅ Token saved to secret file.")
                time.sleep(3)
            return TOKEN
        
print("Starting up. 🚀 ")
TOKEN = load_token(token_secret)

# Load cached AQI data if exists
cache_file = "aqi_cache.json"
if os.path.exists(cache_file):
    with open(cache_file, "r") as f:
        aqi_cache = json.load(f)
else:
    print("  ⚠️ aqi_cache doesn't exist. Creating new one")
    aqi_cache = {}

# Load feature code data if exists
feature_codes = {}
if os.path.exists(feature_codes_file):
    with open(feature_codes_file, "r", encoding="utf-8") as g:
        reader = csv.DictReader(g, delimiter="\t")
        for row in reader:
            code = row["Code"]         # e.g., "P.PPL"
            description = row["Description"]
            feature_codes[code] = description
else:
    print("  ⚠️ featureCodes_en.csv couldn't be loaded!")


def save_cache():
    with open(cache_file, "w") as f:
        json.dump(aqi_cache, f)
    print("✅ AQI cache saved.")
    
def generate_map():

    # Add heatmap
    if heat_data:
        print(f"Adding heatmap with {len(heat_data)} points…")
        HeatMap(heat_data, radius=25, blur=15, min_opacity=0.25,name="AQI Heatmap").add_to(m)
    else:
        print("  ⚠️ No heat data available.")

    # Add WAQI tile layer
    folium.raster_layers.TileLayer(
        tiles=f"https://tiles.aqicn.org/tiles/usepa-aqi/{{z}}/{{x}}/{{y}}.png?token={TOKEN}",
        attr="WAQI",
        name="Air Quality Overlay (WAQI)",
        overlay=True,
        control=True,
        opacity=0.6,
    ).add_to(m)

    # Add layer control
    folium.LayerControl().add_to(m)
    m.add_child(folium.plugins.LocateControl())
    m.add_child(Fullscreen(
        position="topright",
        title="Enter Fullscreen",
        title_cancel="Exit Fullscreen",
        force_separate_button=True,
    ))
    # Save final map
    m.save(f"output\{output_file_name}")
    print(f"Map saved to output folder. Filename:{output_file_name}")

def get_aqi_color(aqi):
    if aqi <= 50:
        return "blue"
    elif aqi <= 100:
        return "green"
    elif aqi <= 150:
        return "yellow"
    elif aqi <= 200:
        return "orange"
    elif aqi <= 300:
        return "red"
    else:
        return "purple"

def get_aqi_category(aqi):
    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Moderate"
    elif aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    elif aqi <= 200:
        return "Unhealthy"
    elif aqi <= 300:
        return "Very Unhealthy"
    else:
        return "Hazardous"

def get_aqi_emoji(aqi):
    if aqi <= 50:
        return "🔵"
    elif aqi <= 100:
        return "🟢"
    elif aqi <= 150:
        return "🟡"
    elif aqi <= 200:
        return "🟠"
    elif aqi <= 300:
        return "🔴"
    else:
        return "🟣"

def get_feature_code_desc(feature_class, feature_code):
    """Returns the description for a feature code given class and code."""
    fcode = f"{feature_class}.{feature_code}"
    return feature_codes.get(fcode, "  ⚠️ Unknown feature code")

columns = [
    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
    "feature_class", "feature_code", "country_code", "cc2", "admin1_code",
    "admin2_code", "admin3_code", "admin4_code", "population", "elevation",
    "dem", "timezone", "modification_date"
]

try:

    df = pd.read_csv("sk.txt", sep='\t', header=None, names=columns)

    # Filter cities in Slovakia with population above threshold
    threshold = 0
    locations = [
    [row["name"], row["latitude"], row["longitude"],row["feature_class"],row["feature_code"]]
    for _, row in df.iterrows()
    if row["population"] > threshold and row["feature_class"] != "" 
    ]

    # Setup map
    m = folium.Map(location=[48.7, 19.5], zoom_start=8, tiles="OpenStreetMap")
    marker_cluster = MarkerCluster(name="City Marker Clusters",).add_to(m)
    heat_data = []

    # Loop over list
    for idx, (city, lat, lon,fclass, fcode) in enumerate(locations, start=1):
        key = f"{lat},{lon}"
        percent = (idx / len(locations)) * 100

        print(f"[{idx}/{len(locations)}] [{percent:.1f}%] Processing city:{city}")
        
        if key in aqi_cache:
            data = aqi_cache[key]
            print(f"  ✅ Using cached data for {city}")
        else:
            try:
                print(f"  ⬇️ Fetching data from API for {city}...")
                url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={TOKEN}"
                resp = requests.get(url, timeout=10).json()
                if resp.get("status") == "ok":
                    data = resp["data"]
                    aqi_cache[key] = data
                    time.sleep(1)  # be nice to the API
                else:
                    print(f"  ⚠️ No data for {city}: {resp.get('data')}")
                    continue
            except Exception as e:
                print(f"  ❌ Error fetching {city}: {e}")
                continue

        aqi = data.get("aqi", 0)
        dom = data.get("dominentpol", "N/A")
        iaqi = data.get("iaqi", {})

        print(f"  {get_aqi_emoji(aqi)} {city} AQI = {aqi} (dominant: {dom}) Status: {get_aqi_category(aqi)} feature class: {get_feature_code_desc(fclass,fcode)}")
        heat_data.append([lat, lon, aqi])

        popup = f"<b>{city}</b><br>Status: <b>{get_aqi_category(aqi)}</b><br>AQI: <b>{aqi}</b><br>Dominant: <b>{dom.upper()}</b><br>"
        for pollutant, val in iaqi.items():
            popup += f"{pollutant.upper()}: {val.get('v')}<br>"

        folium.Marker(
            location=[lat, lon],
            popup=popup,
            icon=folium.Icon(color=get_aqi_color(aqi)),
        ).add_to(marker_cluster)

    generate_map()

except KeyboardInterrupt:
    print("\n⏹️ Interrupted by user.")

finally:

    save_cache()
    generate_map()
