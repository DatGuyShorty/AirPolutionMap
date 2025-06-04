# AirPolutionMap

This project visualizes air pollution (AQI) data for cities in Slovakia using an interactive map.

## Important Notice

**You must manually download the `SK.txt` data file yourself.**  
Due to licensing or distribution restrictions, this file is not included in the repository.

- Download `SK.txt` from [https://download.geonames.org/export/dump/](https://download.geonames.org/export/dump/).
- Place the file in the root directory of this project.

The application will not work without this file.

## How It Works

- The script reads Slovak city data from `SK.txt` (from GeoNames).
- It filters cities with a population above 1000 and excludes administrative regions (e.g., names containing "okres").
- For each city, it fetches real-time AQI (Air Quality Index) data from the [World Air Quality Index API](https://aqicn.org/api/).
- The map displays each city as a colored marker (color based on AQI) with a popup showing AQI details and pollutants.
- A heatmap overlay visualizes AQI intensity across the country.
- The final map is saved as `slovakia_aqicn_heatmap_population.html`.

## Setup

1. **Clone this repository.**
2. **Download and place `SK.txt` as described above.**
3. **Install dependencies:**
```
pip install pandas folium requests
```
4. **Set your AQI API token. Get your's here: [https://aqicn.org/data-platform/token/](https://aqicn.org/data-platform/token/)**
5. **Run the script: (Takes a while, depending on your population treshold, so be patient!)**
```
python map.py
 ```
5. **Open slovakia_aqicn_heatmap_population.html in your browser to view the map.**

## Screenshots
![Main Map View](screenshots/main-map.png)
