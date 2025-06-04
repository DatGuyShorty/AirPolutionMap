#!/usr/bin/env python3
"""
AQI Map Generator for Slovakia

This script reads geographic data for Slovakian cities, fetches Air Quality Index (AQI) data
from the WAQI API, and generates an interactive Folium map with markers and a heatmap overlay.
Results are cached locally; entries older than 4 hours are automatically refreshed. Existing
“old-format” cache entries (without timestamps) are migrated on first access.

Usage:
    python aqi_map.py [--token-file TOKEN_FILE]
                      [--feature-codes FEATURE_CODES_FILE]
                      [--input-file INPUT_FILE]
                      [--cache-file CACHE_FILE]
                      [--output-dir OUTPUT_DIR]
                      [--output-file OUTPUT_FILE]

Requirements:
    - pandas
    - folium
    - requests

Author: Tibor Hoppan
Date: 2025-06-04
"""

import os
import time
import json
import csv
import argparse
import logging
import requests

import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster, Fullscreen, LocateControl

# Cache Time-to-Live (in seconds): 4 hours
CACHE_TTL_SECONDS = 4 * 3600


def setup_logging(log_file: str = "app_log.log") -> None:
    """
    Configure the root logger to output to both a file and the console.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8", mode="w"),
            logging.StreamHandler()
        ]
    )


def load_token(token_path: str) -> str:
    """
    Load the WAQI API token from a file. If the file does not exist or is empty,
    prompt the user to input the token and save it.

    :param token_path: Path to the token file.
    :return: API token string.
    """
    if os.path.exists(token_path):
        with open(token_path, "r", encoding="utf-8") as f:
            token = f.read().strip()
        if token:
            logging.info("✅ API token loaded from %s.", token_path)
            return token

        logging.warning("🔐 Token file is empty. Prompting for API token.")
    else:
        logging.warning("🔐 Token file '%s' not found. Prompting for API token.", token_path)

    token = input("Please paste your AQI API token: ").strip()
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(token)
    logging.info("✅ API token saved to %s.", token_path)
    time.sleep(3)
    return token


def load_feature_codes(feature_codes_path: str) -> dict:
    """
    Load geographic feature codes and their descriptions into a dictionary.

    :param feature_codes_path: Path to the TSV file containing feature codes.
    :return: Dictionary mapping 'Code' -> 'Description'.
    """
    feature_codes = {}
    if not os.path.exists(feature_codes_path):
        logging.warning("⚠️ Feature codes file '%s' not found.", feature_codes_path)
        return feature_codes

    try:
        with open(feature_codes_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                code_key = row.get("Code", "").strip()
                description = row.get("Description", "").strip()
                if code_key:
                    feature_codes[code_key] = description
        logging.info("✅ Loaded %d feature codes.", len(feature_codes))
    except Exception as e:
        logging.error("❌ Failed to load feature codes: %s", e)

    return feature_codes


def load_cache(cache_path: str) -> dict:
    """
    Load the cached AQI responses from a JSON file. If the file doesn't exist or is invalid,
    return an empty cache.

    Old-format entries (where the value is just raw data) will be migrated on first usage.
    New-format entries are stored as:
        {
            "<lat>,<lon>": {
                "timestamp": <epoch_seconds>,
                "data": { ... WAQI data ... }
            },
            ...
        }

    :param cache_path: Path to the cache file.
    :return: Dictionary representing the cache.
    """
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            logging.info("✅ Loaded AQI cache from %s.", cache_path)
            return cache
        except (json.JSONDecodeError, PermissionError) as e:
            logging.warning("⚠️ Cache file '%s' is corrupt or unreadable. Starting with an empty cache. (%s)", cache_path, e)
    else:
        logging.warning("⚠️ Cache file '%s' not found. Creating a new cache.", cache_path)

    return {}


def save_cache(cache: dict, cache_path: str) -> None:
    """
    Save the AQI cache to a JSON file. Overwrites the entire file.

    :param cache: Dictionary to save.
    :param cache_path: Path to the cache file.
    """
    try:
        out_dir = os.path.dirname(cache_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        logging.info("✅ AQI cache saved to %s.", cache_path)
    except Exception as e:
        logging.error("❌ Failed to save cache to '%s': %s", cache_path, e)


def get_aqi_color(aqi: int) -> str:
    """
    Return a Folium-compatible marker color based on the AQI value.

    :param aqi: Air Quality Index.
    :return: Color string.
    """
    if aqi <= 50:
        return "blue"
    if aqi <= 100:
        return "green"
    if aqi <= 150:
        return "yellow"
    if aqi <= 200:
        return "orange"
    if aqi <= 300:
        return "red"
    return "purple"


def get_aqi_category(aqi: int) -> str:
    """
    Return a descriptive category for a given AQI value.

    :param aqi: Air Quality Index.
    :return: Category string.
    """
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def get_aqi_emoji(aqi: int) -> str:
    """
    Return a colored circle emoji based on the AQI value.

    :param aqi: Air Quality Index.
    :return: Emoji string.
    """
    if aqi <= 50:
        return "🔵"
    if aqi <= 100:
        return "🟢"
    if aqi <= 150:
        return "🟡"
    if aqi <= 200:
        return "🟠"
    if aqi <= 300:
        return "🔴"
    return "🟣"


def get_feature_code_desc(feature_class: str, feature_code: str, feature_codes: dict) -> str:
    """
    Look up a human-readable description for a given feature class/code.

    :param feature_class: GEO feature class.
    :param feature_code: GEO feature code.
    :param feature_codes: Dictionary mapping 'class.code' -> description.
    :return: Description or 'Unknown' placeholder.
    """
    fkey = f"{feature_class}.{feature_code}"
    return feature_codes.get(fkey, "⚠️ Unknown feature code")


def fetch_aqi_for_location(lat: float, lon: float, token: str, cache: dict, delay: float = 0.25) -> dict:
    """
    Fetch AQI data for a given latitude/longitude from the WAQI API, using and updating the cache.
    - If a new-format cache entry exists and is younger than CACHE_TTL_SECONDS, return it.
    - If it exists but is older, or if no entry exists, fetch fresh data and overwrite.
    - If an old-format entry is found (i.e., raw data without 'timestamp'), migrate it to new format,
      using 'now' as the timestamp, and return its data without re-fetching.

    :param lat: Latitude.
    :param lon: Longitude.
    :param token: API token.
    :param cache: Cache dictionary to read/write.
                  Keys: "lat,lon" strings; values either:
                    - new-format: {"timestamp": <epoch>, "data": {...}}
                    - old-format: {... raw WAQI data ...}
    :param delay: Seconds to pause after a successful API call.
    :return: Dictionary of API response data, or {} if unavailable.
    """
    key = f"{lat},{lon}"
    now = time.time()

    if key in cache:
        entry = cache[key]

        # Detect old-format entry (no 'timestamp' or 'data' keys)
        if not (isinstance(entry, dict) and "timestamp" in entry and "data" in entry):
            old_data = entry
            cache[key] = {"timestamp": now, "data": old_data}
            logging.info("  ℹ️ Migrated old cache format for %s.", key)
            return old_data

        # New-format entry exists; check age
        entry_ts = entry.get("timestamp", 0)
        age = now - entry_ts
        if age < CACHE_TTL_SECONDS:
            logging.info("  ✅ Using cached AQI data for %s (age: %.1f min).", key, age / 60.0)
            return entry["data"]
        else:
            logging.info("  ℹ️ Cache expired for %s (age: %.1f min). Refreshing...", key, age / 60.0)

    # Either no entry or expired; fetch from API
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={token}"
    try:
        logging.info("  ⬇️ Fetching AQI data from API for %s...", key)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("status") == "ok" and "data" in result:
            data = result["data"]
            cache[key] = {"timestamp": now, "data": data}
            time.sleep(delay)
            return data
        else:
            logging.warning("  ⚠️ API response not OK for %s: %s", key, result.get("data", result))
    except requests.RequestException as e:
        logging.error("  ❌ Request failed for %s: %s", key, e)
    except ValueError as e:
        logging.error("  ❌ Failed to parse JSON for %s: %s", key, e)

    return {}


def read_locations(input_path: str, population_threshold: int = 0) -> list:
    """
    Read city/location data from a TSV (tab-separated) file and filter by population.

    :param input_path: Path to the TSV file containing geographic data.
    :param population_threshold: Minimum population to include.
    :return: List of tuples (city_name, latitude, longitude, feature_class, feature_code).
    """
    columns = [
        "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
        "feature_class", "feature_code", "country_code", "cc2", "admin1_code",
        "admin2_code", "admin3_code", "admin4_code", "population", "elevation",
        "dem", "timezone", "modification_date"
    ]

    try:
        df = pd.read_csv(input_path, sep="\t", header=None, names=columns, dtype={"population": int})
        logging.info("✅ Loaded %d rows from %s.", len(df), input_path)
    except Exception as e:
        logging.error("❌ Failed to read '%s': %s", input_path, e)
        return []

    locations = []
    for _, row in df.iterrows():
        if row["population"] > population_threshold and row["feature_class"]:
            locations.append((
                row["name"],
                float(row["latitude"]),
                float(row["longitude"]),
                row["feature_class"],
                row["feature_code"]
            ))

    logging.info("✅ Filtered down to %d locations with population > %d.", len(locations), population_threshold)
    return locations


def generate_map(
    center: tuple,
    zoom_start: int,
    locations: list,
    token: str,
    feature_codes: dict,
    cache: dict,
    output_path: str
) -> None:
    """
    Build and save a Folium map with AQI markers and a heatmap overlay.

    :param center: Tuple of (latitude, longitude) for initial map view.
    :param zoom_start: Initial zoom level.
    :param locations: List of location tuples from read_locations().
    :param token: API token for WAQI.
    :param feature_codes: Dictionary of feature code descriptions.
    :param cache: Dictionary used/updated by fetch_aqi_for_location().
    :param output_path: Full path for the .html output file.
    """
    m = folium.Map(location=center, zoom_start=zoom_start, tiles="OpenStreetMap")
    marker_cluster = MarkerCluster(name="City Marker Clusters").add_to(m)
    heat_data = []

    total = len(locations)
    for idx, (city, lat, lon, fclass, fcode) in enumerate(locations, start=1):
        percent = (idx / total) * 100
        logging.info("[%d/%d] [%.1f%%] Processing: %s", idx, total, percent, city)

        data = fetch_aqi_for_location(lat, lon, token, cache)
        if not data:
            continue

        aqi = data.get("aqi", 0)
        dominentpol = data.get("dominentpol", "N/A")
        iaqi = data.get("iaqi", {})

        emoji = get_aqi_emoji(aqi)
        category = get_aqi_category(aqi)
        feature_desc = get_feature_code_desc(fclass, fcode, feature_codes)

        logging.info(
            "  %s %s | AQI=%d | Category=%s | Dominant=%s | Feature=%s",
            emoji, city, aqi, category, dominentpol.upper(), feature_desc
        )

        # Collect data for heatmap (lat, lon, weight)
        heat_data.append([lat, lon, aqi])

        # Build popup HTML
        popup_html = (
            f"<b>{city}</b><br>"
            f"Status: <b>{category}</b><br>"
            f"AQI: <b>{aqi}</b><br>"
            f"Dominant Pollutant: <b>{dominentpol.upper()}</b><br>"
        )
        for pollutant, val in iaqi.items():
            popup_html += f"{pollutant.upper()}: {val.get('v')}<br>"

        folium.Marker(
            location=(lat, lon),
            popup=popup_html,
            icon=folium.Icon(color=get_aqi_color(aqi))
        ).add_to(marker_cluster)

    # Add heatmap layer if any data points exist
    if heat_data:
        logging.info("Adding heatmap with %d points.", len(heat_data))
        HeatMap(
            heat_data,
            radius=25,
            blur=15,
            min_opacity=0.25,
            name="AQI Heatmap"
        ).add_to(m)
    else:
        logging.warning("⚠️ No heatmap data available. Skipping heatmap layer.")

    # Add WAQI tile layer
    folium.raster_layers.TileLayer(
        tiles=f"https://tiles.aqicn.org/tiles/usepa-aqi/{{z}}/{{x}}/{{y}}.png?token={token}",
        attr="WAQI",
        name="Air Quality Overlay (WAQI)",
        overlay=True,
        control=True,
        opacity=0.6
    ).add_to(m)

    # Add layer control, locate control, and fullscreen button
    folium.LayerControl().add_to(m)
    m.add_child(LocateControl())
    m.add_child(Fullscreen(
        position="topright",
        title="Enter Fullscreen",
        title_cancel="Exit Fullscreen",
        force_separate_button=True
    ))

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Save the map
    try:
        m.save(output_path)
        logging.info("✅ Map successfully saved to '%s'.", output_path)
    except Exception as e:
        logging.error("❌ Failed to save map to '%s': %s", output_path, e)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Generate a Folium map of AQI data for Slovakia.")
    parser.add_argument(
        "--token-file",
        type=str,
        default="api_key.secret",
        help="Path to the file containing the WAQI API token (default: api_key.secret)."
    )
    parser.add_argument(
        "--feature-codes",
        type=str,
        default="featureCodes_en.csv",
        help="Path to the TSV file with geographic feature code descriptions (default: featureCodes_en.csv)."
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default="sk.txt",
        help="Path to the TSV file containing city/location data (default: sk.txt)."
    )
    parser.add_argument(
        "--cache-file",
        type=str,
        default="aqi_cache.json",
        help="Path to the JSON file used for caching AQI API responses (default: aqi_cache.json)."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory where the resulting map HTML will be saved (default: output)."
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="AQI_map_Slovakia.html",
        help="Name of the output HTML file (default: AQI_map_Slovakia.html)."
    )
    parser.add_argument(
        "--population-threshold",
        type=int,
        default=1000,
        help="Minimum population of locations to include (default: 1000)."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging()

    logging.info("🚀 Starting AQI map generation.")

    # Load API token, feature codes, and cache
    token = load_token(args.token_file)
    feature_codes = load_feature_codes(args.feature_codes)
    aqi_cache = load_cache(args.cache_file)

    try:
        # Read and filter locations
        locations = read_locations(args.input_file, population_threshold=args.population_threshold)
        if not locations:
            logging.error("❌ No locations to process. Exiting.")
            return

        # Build and save the map
        output_path = os.path.join(args.output_dir, args.output_file)
        center_coords = (48.7, 19.5)  # Center over Slovakia
        generate_map(
            center=center_coords,
            zoom_start=8,
            locations=locations,
            token=token,
            feature_codes=feature_codes,
            cache=aqi_cache,
            output_path=output_path
        )

    except KeyboardInterrupt:
        logging.info("⏹️ Interrupted by user during processing.")

    finally:
        # Save cache on exit (even if interrupted)
        save_cache(aqi_cache, args.cache_file)
        logging.info("ℹ️ AQI map generation terminated; cache saved.")
    
if __name__ == "__main__":
    main()
