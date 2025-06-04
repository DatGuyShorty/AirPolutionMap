import pandas as pd
import folium
from folium.plugins import HeatMap
import requests

TOKEN = ""



columns = [
    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
    "feature_class", "feature_code", "country_code", "cc2", "admin1_code",
    "admin2_code", "admin3_code", "admin4_code", "population", "elevation",
    "dem", "timezone", "modification_date"
]

df = pd.read_csv("SK.txt", sep='\t', header=None, names=columns)

# 2) Convert to a list of [city, lat, lon]
#locations = df[["name", "latitude", "longitude"]].values.tolist()

threshold = 1000  # set your desired population threshold
locations = []

for _, row in df.iterrows():
    if (row["population"] > threshold and
        row["name"] and "okres" not in row["name"].lower()):
        locations.append([row["name"], row["latitude"], row["longitude"]])

# 3) Build the map exactly as before, looping over this new locations list
m = folium.Map(location=[48.7, 19.5], zoom_start=7, tiles="Cartodb dark_matter")

def get_aqi_color(aqi):
    if aqi <= 50:
        return "green"
    elif aqi <= 100:
        return "yellow"
    elif aqi <= 150:
        return "orange"
    elif aqi <= 200:
        return "red"
    elif aqi <= 300:
        return "purple"
    else:
        return "maroon"

heat_data = []

for idx, (city, lat, lon) in enumerate(locations, start=1):
    percent = (idx / len(locations)) * 100
    print(f"[{idx}/{len(locations)}] [{percent:.1f}%] Fetching data for {city}...")
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={TOKEN}"
    try:
        resp = requests.get(url, timeout=10).json()
        if resp.get("status") == "ok":
            aqi = resp["data"]["aqi"]
            dom = resp["data"].get("dominentpol", "N/A")
            iaqi = resp["data"].get("iaqi", {})

            print(f"  → {city} AQI = {aqi} ({dom})")
            heat_data.append([lat, lon, aqi])

            popup = f"<b>{city}</b><br>AQI: {aqi}<br>Dominant: {dom.upper()}<br>"
            for pollutant, val in iaqi.items():
                popup += f"{pollutant.upper()}: {val['v']}<br>"

            folium.CircleMarker(
                location=[lat, lon],
                radius=10,
                color=get_aqi_color(aqi),
                fill=True,
                fill_opacity=0.8,
                popup=popup
            ).add_to(m)

        else:
            print(f"  ⚠️ No data for {city}: {resp.get('data')}")
    except Exception as e:
        print(f"  ❌ Error fetching {city}: {e}")

if heat_data:
    print(f"Adding heatmap with {len(heat_data)} points…")
    HeatMap(heat_data, radius=25, blur=15, min_opacity=0.5, max_zoom=10).add_to(m)
else:
    print("No heat data available.")

m.save("slovakia_aqicn_heatmap_population.html")
print("Map saved as slovakia_aqicn_heatmap_population.html")
