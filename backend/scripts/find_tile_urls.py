import urllib.request
import re
import json

def test_urls():
    print("Testing Lunar WMTS / XYZ Tile Servers...")
    
    # 1. USGS Astrogeology MapServer WMS / WMTS endpoints
    # 2. NASA Moon Trek WMTS endpoints
    # 3. OpenPlanetary / Esri Lunar endpoints
    
    test_endpoints = [
        # NASA Moon Trek Tile WMTS Template
        ("NASA Moon Trek (WAC Global)", "https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303m/1.0.0/default/default028mm/2/1/1.jpg"),
        ("NASA Moon Trek (LOLA Shaded Relief)", "https://trek.nasa.gov/tiles/Moon/EQ/LRO_LOLA_ClrShade_Global_128ppd/1.0.0/default/default028mm/2/1/1.png"),
        ("NASA Moon Trek (South Pole LOLA 60m)", "https://trek.nasa.gov/tiles/Moon/SP/LRO_LOLA_DEM_SPolar_60m/1.0.0/default/default028mm/2/1/1.png"),
        
        # USGS Astrogeology TMS / WMS
        ("USGS Lunar WAC (PlanetaryMaps)", "https://planetarymaps.usgs.gov/cgi-bin/mapserv?map=/maps/earth/moon_simp_maj.map&mode=tile&tilemode=gmap&tile=1+1+2"),
        
        # GIBS EPSG:4326
        ("GIBS MODIS Test Tile", "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/2024-01-01/250m/2/1/1.jpg"),
        
        # OpenPlanetary WAC
        ("OpenPlanetary Moon WAC", "https://s3.amazonaws.com/opmbuilder/opm.nasa.moon.wac/1.0.0/common/2/1/1.png"),
        
        # Esri ArcGIS Moon REST MapServer
        ("ArcGIS LRO LOLA MapServer", "https://tiles.arcgis.com/tiles/5T7mBq70c3aJgU8D/arcgis/rest/services/Moon_LRO_LOLA_ShadedRelief_Global_128ppd/MapServer/tile/2/1/1")
    ]
    
    for name, url in test_endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                ct = resp.headers.get("content-type", "")
                print(f"[SUCCESS] {name:<35} | HTTP {resp.status} | Content-Type: {ct:<20} | Length: {len(data)} bytes")
        except Exception as e:
            print(f"[FAILED]  {name:<35} | Exception: {e}")

if __name__ == "__main__":
    test_urls()
