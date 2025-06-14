# AirPolutionMap

This project visualizes air pollution (AQI) data for cities in Slovakia using an interactive map.

## Important Notice

**You must manually download the `SK.txt` data file yourself.**  
Due to licensing or distribution restrictions, this file is not included in the repository.

- Download `SK.txt` from [https://download.geonames.org/export/dump/](https://download.geonames.org/export/dump/).
- Place the file in the root directory of this project.

The application will not work without this file.

## How It Works

- The script reads Slovak city data from `sk.txt` (from GeoNames).
- It filters cities with a population above a threshold (default: 0).
- For each city, it fetches real-time AQI (Air Quality Index) data from the [World Air Quality Index API](https://aqicn.org/api/), with caching to avoid redundant requests.
- The map displays each city as a colored marker (color based on AQI) with a popup showing AQI details and pollutants.
- A heatmap overlay visualizes AQI intensity across the country.
- The map includes a WAQI tile overlay, marker clustering, fullscreen mode, and location control.
- The final map is saved as `output/AQI_map_Slovakia.html`.

## Setup

1. **Clone this repository.**
2. **Download and place `SK.txt` as described above.**
3. **(Optional) Download `featureCodes_en.csv` from [GeoNames](https://download.geonames.org/export/dump/featureCodes_en.txt) and place it in the root directory for feature code descriptions.**
4. **Install dependencies:**
```
pip install pandas folium requests
```
5. **Run the script:**
```
python map.py
```
6. **Get your token here: [https://aqicn.org/data-platform/token/](https://aqicn.org/data-platform/token/) and paste your AQI API token inside terminal after being prompted.**

7. **Open `output/AQI_map_Slovakia.html` in your browser to view the map.**

## Screenshots
![Main Map View](screenshots/main-map.png)
