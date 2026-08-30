import os
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import tifffile

RAW_DIR = Path(r"D:\FYP\data\pradan\raw")

def parse_xml_labels():
    print("=" * 70)
    print("STAGE 1 — PDS4 XML LABELS & METADATA INVENTORY")
    print("=" * 70)
    
    xml_files = list(RAW_DIR.rglob("*.xml"))
    print(f"Found {len(xml_files)} XML label files:\n")
    
    namespaces = {
        'pds': 'http://pds.nasa.gov/pds4/pds/v1',
        'isro': 'http://psa.esac.esa.int/psa/v1' # generic fallback
    }

    for xml_path in xml_files:
        print(f"--- XML: {xml_path.name} ---")
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Print root tag and strip namespace
            def find_text(elem, tag_name):
                for el in elem.iter():
                    if el.tag.endswith(tag_name):
                        return el.text.strip() if el.text else ""
                return "N/A"

            title = find_text(root, "title")
            lid = find_text(root, "logical_identifier")
            start_date = find_text(root, "start_date_time")
            stop_date = find_text(root, "stop_date_time")
            inst = find_text(root, "instrument_name") or find_text(root, "instrument_id") or find_text(root, "observing_system_name")
            prod_type = find_text(root, "product_type") or find_text(root, "processing_level")
            
            # Bounding coordinates
            w_lon = find_text(root, "westernmost_longitude")
            e_lon = find_text(root, "easternmost_longitude")
            min_lat = find_text(root, "minimum_latitude")
            max_lat = find_text(root, "maximum_latitude")
            
            # Array dimensions
            axes = find_text(root, "axes")
            elements = find_text(root, "elements")
            data_type = find_text(root, "data_type")
            
            print(f"  Title: {title}")
            print(f"  Logical Identifier: {lid}")
            print(f"  Start Date/Time: {start_date}")
            print(f"  Stop Date/Time: {stop_date}")
            print(f"  Instrument / Type: {inst} | {prod_type}")
            print(f"  Lat Bounds: [{min_lat}, {max_lat}]")
            print(f"  Lon Bounds: [{w_lon}, {e_lon}]")
            print(f"  Data Type / Axes: {data_type} | axes={axes}")
            
            # Find associated file names mentioned in XML
            files = [el.text for el in root.iter() if el.tag.endswith("file_name")]
            print(f"  Referenced Data Files: {files}")
            print()
        except Exception as e:
            print(f"  Error reading XML: {e}\n")

def inspect_tif_files():
    print("=" * 70)
    print("STAGE 1 — TIFF DATA FILES SANITY CHECK")
    print("=" * 70)
    
    tif_files = sorted(list(RAW_DIR.rglob("*.tif")), key=lambda f: f.stat().st_size)
    for tif_path in tif_files:
        size_mb = tif_path.stat().st_size / (1024 * 1024)
        print(f"\nFile: {tif_path.name} ({size_mb:.2f} MB)")
        try:
            with tifffile.TiffFile(tif_path) as tif:
                series = tif.series[0]
                shape = series.shape
                dtype = series.dtype
                print(f"  Shape: {shape}, Dtype: {dtype}")
                
                # If file is < 100MB, read directly. If large (>500MB), read sample crop or memmap
                if size_mb < 200:
                    arr = tif.asarray()
                    valid_mask = np.isfinite(arr) & (arr != 0)
                    if np.any(valid_mask):
                        valid_vals = arr[valid_mask]
                        print(f"  Valid pixels: {valid_vals.size} / {arr.size} ({valid_vals.size/arr.size*100:.1f}%)")
                        print(f"  Min: {float(np.min(valid_vals)):.4f}, Max: {float(np.max(valid_vals)):.4f}, Mean: {float(np.mean(valid_vals)):.4f}")
                    else:
                        print(f"  All values zero/null or nan")
                else:
                    # Memmap or read small chunk
                    mem = tif.asarray(out='memmap')
                    print(f"  Large file memmapped safely. Shape: {mem.shape}")
                    sample = mem[:1000, :1000]
                    print(f"  Sample [0:1000, 0:1000] Min: {np.nanmin(sample):.4f}, Max: {np.nanmax(sample):.4f}, Mean: {np.nanmean(sample):.4f}")
        except Exception as e:
            print(f"  Error reading TIFF: {e}")

if __name__ == "__main__":
    parse_xml_labels()
    inspect_tif_files()
