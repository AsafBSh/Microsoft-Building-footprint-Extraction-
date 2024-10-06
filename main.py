import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, box, mapping
import os
import argparse
from tqdm import tqdm
import math
import json
import numpy as np
import sys
from rtree import index


def download_and_process_data(location, output_folder, divide_immediately=True):
    """
    Download and process building footprint data for a specified location.
    """
    print(f"Downloading data for {location}...")
    try:
        dataset_links = pd.read_csv("https://minedbuildings.blob.core.windows.net/global-buildings/dataset-links.csv")
    except Exception as e:
        print(f"Error downloading dataset links: {e}")
        sys.exit(1)

    location_links = dataset_links[dataset_links.Location == location]

    if location_links.empty:
        print(f"Error: No data found for '{location}'. Please check the location name and try again.")
        print("Available locations:")
        print(", ".join(sorted(dataset_links['Location'].unique())))
        sys.exit(1)

    os.makedirs(output_folder, exist_ok=True)

    all_data = []
    for _, row in tqdm(location_links.iterrows(), total=len(location_links), desc="Processing data"):
        try:
            df = pd.read_json(row.Url, lines=True)
            df['geometry'] = df['geometry'].apply(shape)
            gdf = gpd.GeoDataFrame(df, crs=4326)
            all_data.append(gdf)
        except Exception as e:
            print(f"Error processing data from {row.Url}: {e}")
            continue

    if not all_data:
        print("Error: No data could be processed. Exiting.")
        sys.exit(1)

    combined_gdf = pd.concat(all_data)
    bounds = combined_gdf.total_bounds

    if divide_immediately:
        divide_data(combined_gdf, output_folder, location, bounds)
    else:
        combined_gdf.to_file(f"{output_folder}/{location}.geojson", driver="GeoJSON")


def divide_data(gdf, output_folder, location, bounds):
    """
    Divide a large GeoDataFrame into smaller GeoJSON files based on adaptive grid.
    """
    x_min, y_min, x_max, y_max = bounds
    area = (x_max - x_min) * (y_max - y_min)

    # Aim for approximately 100 chunks
    chunk_area = area / 100
    grid_size = math.sqrt(chunk_area)

    x_ranges = list(np.arange(x_min, x_max, grid_size))
    y_ranges = list(np.arange(y_min, y_max, grid_size))

    metadata = {}

    for x in tqdm(x_ranges, desc="Dividing data"):
        for y in y_ranges:
            cell = box(x, y, min(x + grid_size, x_max), min(y + grid_size, y_max))
            cell_gdf = gdf[gdf.intersects(cell)]
            if not cell_gdf.empty:
                filename = f"{location}_{x:.6f}_{y:.6f}.geojson"
                cell_gdf.to_file(os.path.join(output_folder, filename), driver="GeoJSON")

                # Store chunk coordinates in metadata
                metadata[filename] = {
                    'x_min': x,
                    'y_min': y,
                    'x_max': min(x + grid_size, x_max),
                    'y_max': min(y + grid_size, y_max)
                }

    # Save metadata to a separate file
    with open(os.path.join(output_folder, f"{location}_metadata.json"), 'w') as f:
        json.dump(metadata, f)


def extract_data(input_folder, output_file, top_left, bottom_right):
    if not os.path.isdir(input_folder):
        print(f"Error: The input folder '{input_folder}' does not exist.")
        sys.exit(1)

    # Check if output file already exists
    if os.path.exists(output_file):
        while True:
            response = input(
                f"The file '{output_file}' already exists. Do you want to overwrite it? (y/n): ").lower()
            if response == 'y':
                break
            elif response == 'n':
                new_name = input("Please enter a new file name: ")
                output_file = new_name if new_name.endswith('.geojson') else new_name + '.geojson'
                break
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

    bbox = box(min(top_left[1], bottom_right[1]),
               min(top_left[0], bottom_right[0]),
               max(top_left[1], bottom_right[1]),
               max(top_left[0], bottom_right[0]))

    metadata_file = next((f for f in os.listdir(input_folder) if f.endswith('_metadata.json')), None)
    if not metadata_file:
        print("Error: Metadata file not found. Cannot perform efficient extraction.")
        sys.exit(1)

    try:
        with open(os.path.join(input_folder, metadata_file), 'r') as f:
            metadata = json.load(f)
    except json.JSONDecodeError:
        print("Error: Invalid metadata file. Cannot perform efficient extraction.")
        sys.exit(1)

    # Create a spatial index
    idx = index.Index()
    for i, (filename, chunk_coords) in enumerate(metadata.items()):
        idx.insert(i, (chunk_coords['x_min'], chunk_coords['y_min'],
                       chunk_coords['x_max'], chunk_coords['y_max']))

    # Find potentially intersecting files
    intersecting_files = []
    for i in idx.intersection(bbox.bounds):
        filename = list(metadata.keys())[i]
        chunk_coords = metadata[filename]
        if bbox.intersects(box(chunk_coords['x_min'], chunk_coords['y_min'],
                               chunk_coords['x_max'], chunk_coords['y_max'])):
            intersecting_files.append(filename)

    print(f"Found {len(intersecting_files)} potentially intersecting files.")

    all_features = []
    for filename in tqdm(intersecting_files, desc="Extracting data"):
        file_path = os.path.join(input_folder, filename)
        if not os.path.exists(file_path):
            print(f"Warning: File {filename} not found. Skipping.")
            continue
        try:
            gdf = gpd.read_file(file_path)
            filtered = gdf[gdf.intersects(bbox)]
            for _, row in filtered.iterrows():
                feature = {
                    "type": "Feature",
                    "properties": {"type": "Feature"},
                    "geometry": mapping(row.geometry)
                }
                try:
                    properties_dict = json.loads(row['properties'])
                    feature['properties'].update(properties_dict)
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse properties for a feature. Skipping.")
                    continue
                all_features.append(feature)
        except Exception as e:
            print(f"Error processing file {filename}: {e}")
            continue

    if all_features:
        # Create a GeoDataFrame from the features
        result_gdf = gpd.GeoDataFrame.from_features(all_features)
        # Set the CRS to EPSG:4326 (WGS84)
        result_gdf.set_crs(epsg=4326, inplace=True)
        # Save the GeoDataFrame to a GeoJSON file
        result_gdf.to_file(output_file, driver="GeoJSON")
        print(f"Extracted {len(result_gdf)} buildings to {output_file}")
    else:
        print("No buildings found in the specified area.")


def main():
    parser = argparse.ArgumentParser(description="Process Microsoft Global ML Building Footprints")
    parser.add_argument('--download', type=str, help="Download data for specified location")
    parser.add_argument('--output', type=str, default='output', help="Output folder for download and divide operations")
    parser.add_argument('--divide', action='store_true', help="Divide data immediately after download")
    parser.add_argument('--extract', action='store_true', help="Extract data from downloaded files")
    parser.add_argument('--input', type=str, help="Input folder containing GeoJSON files for extraction")
    parser.add_argument('--output-file', type=str, default='cropped_file.geojson',
                        help="Output file for extracted data")
    parser.add_argument('--top-left', type=str, help="Top-left coordinates (lat,lon)")
    parser.add_argument('--bottom-right', type=str, help="Bottom-right coordinates (lat,lon)")

    args = parser.parse_args()

    if args.download:
        download_and_process_data(args.download, args.output, args.divide)

    if args.extract:
        if not (args.input and args.top_left and args.bottom_right):
            parser.error("--input, --top-left, and --bottom-right are required for extraction")

        # Parse the coordinates
        top_left = list(map(float, args.top_left.split(',')))
        bottom_right = list(map(float, args.bottom_right.split(',')))

        extract_data(args.input, args.output_file, top_left, bottom_right)


if __name__ == "__main__":
    main()
