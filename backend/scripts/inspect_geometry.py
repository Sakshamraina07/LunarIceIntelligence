import csv
import xml.etree.ElementTree as ET
from pathlib import Path

# Repository root, derived from this file's location rather than a hardcoded
# drive letter. backend/scripts/ -> parents[2] is the root.
BASE_DIR = Path(__file__).resolve().parents[2]
raw = BASE_DIR / "data" / "pradan" / "raw"

def inspect_geometry():
    print("--- SRI XML Content ---")
    xml_path = list(raw.rglob("*d_sri_xx_cp_xx_d18.xml"))[0]
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if el.text and el.text.strip() and len(el.text.strip()) < 100:
            if any(k in tag.lower() for k in ["lat", "lon", "product", "instrument", "time", "date", "target", "resolution", "pixel", "line", "sample", "azimuth", "range"]):
                print(f"  {tag}: {el.text.strip()}")
                
    print("\n--- Geometry CSV Files ---")
    csv_files = sorted(list(raw.rglob("*.csv")))
    for c in csv_files:
        print(f"\nFile: {c.name} ({c.stat().st_size / (1024*1024):.2f} MB)")
        with open(c, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            header = next(reader)
            print("  Header:", header[:10])
            first_row = next(reader)
            print("  Row 0 :", first_row[:10])
            
            # Find min/max lat/lon in file
            lats = []
            lons = []
            lat_idx = -1
            lon_idx = -1
            for i, h in enumerate(header):
                if 'lat' in h.lower():
                    lat_idx = i
                elif 'lon' in h.lower():
                    lon_idx = i
            
            if lat_idx != -1 and lon_idx != -1:
                # Sample 1000 rows across file
                count = 0
                for row in reader:
                    count += 1
                    if count % 50 == 0:
                        try:
                            lats.append(float(row[lat_idx]))
                            lons.append(float(row[lon_idx]))
                        except:
                            pass
                if lats:
                    print(f"  Lat range: [{min(lats):.4f}, {max(lats):.4f}]")
                    print(f"  Lon range: [{min(lons):.4f}, {max(lons):.4f}]")

if __name__ == "__main__":
    inspect_geometry()
