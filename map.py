import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
import requests
import time
import json
import os

TOKEN = ""  # Replace with your actual token

columns = [
    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
    "feature_class", "feature_code", "country_code", "cc2", "admin1_code",
    "admin2_code", "admin3_code", "admin4_code", "population", "elevation",
    "dem", "timezone", "modification_date"
]

# Load cached AQI data if exists
cache_file = "aqi_cache.json"
if os.path.exists(cache_file):
    with open(cache_file, "r") as f:
        aqi_cache = json.load(f)
else:
    aqi_cache = {}

# Setup map
m = folium.Map(location=[48.7, 19.5], zoom_start=8, tiles="Cartodb dark_matter")
marker_cluster = MarkerCluster(name="City Marker Clusters",).add_to(m)
heat_data = []
def get_aqi_color(aqi):
    if aqi <= 50:
        return "green"
    elif aqi <= 100:
        return "lightgreen"
    elif aqi <= 150:
        return "orange"
    elif aqi <= 200:
        return "red"
    elif aqi <= 300:
        return "purple"
    else:
        return "darkred"

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

try:

    df = pd.read_csv("sk.txt", sep='\t', header=None, names=columns)

    # Filter cities in Slovakia with population above threshold
    threshold = 750
    locations = [
    [row["name"], row["latitude"], row["longitude"]]
    for _, row in df.iterrows()
    if row["feature_class"] == "P" and row["population"] > threshold
    ]

    # Setup map
    m = folium.Map(location=[48.7, 19.5], zoom_start=8, tiles="Cartodb dark_matter")
    marker_cluster = MarkerCluster(name="City Marker Clusters",).add_to(m)
    heat_data = []
# Loop over list
    for idx, (city, lat, lon) in enumerate(locations, start=1):
        key = f"{lat},{lon}"
        percent = (idx / len(locations)) * 100
        if idx % 3 == 0:
            print("\033c")  # clear terminal
        print(f"[{idx}/{len(locations)}] [{percent:.1f}%] Fetching data for {city}...")

        if key in aqi_cache:
            data = aqi_cache[key]
            print(f"  ✔ Using cached data for {city}")
        else:
            try:
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

        print(f"  → {city} AQI = {aqi} (dominant: {dom}) Status: {get_aqi_category(aqi)}")
        heat_data.append([lat, lon, aqi])

        popup = f"<b>{city}</b><br>Status: <b>{get_aqi_category(aqi)}</b><br>AQI: <b>{aqi}</b><br>Dominant: <b>{dom.upper()}</b><br>"
        for pollutant, val in iaqi.items():
            popup += f"{pollutant.upper()}: {val.get('v')}<br>"

        folium.Marker(
            location=[lat, lon],
            popup=popup,
            icon=folium.Icon(color=get_aqi_color(aqi)),
        ).add_to(marker_cluster)

    # Save updated cache
    with open(cache_file, "w") as f:
        json.dump(aqi_cache, f)

    # Add heatmap
    if heat_data:
        print(f"Adding heatmap with {len(heat_data)} points…")
        HeatMap(heat_data, radius=25, blur=15, min_opacity=0.25,name="AQI Heatmap").add_to(m)
    else:
        print("No heat data available.")

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

    # Save final map
    file_name = "AQI_map_Slovakia.html"
    m.save(r"output\{file_name}")
    print("Map saved to output folder. As {file_name}")

except KeyboardInterrupt:
    print("\n⏹️ Interrupted by user.")
finally:
    with open(cache_file, "w") as f:
        json.dump(aqi_cache, f)
    print("✅ AQI cache saved.")