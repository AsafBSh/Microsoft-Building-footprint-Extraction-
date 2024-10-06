# Microsoft Global ML Building Footprints Extractor

This Python script processes Microsoft's Global ML Building Footprints dataset. It allows users to download, divide, and extract building footprint data for specific locations and areas.

## Features

1. Download building footprint data for a specified location

2.  Divide large datasets into smaller, manageable chunks

3. Extract building data for a specific bounding box

## Requirements

- Python 3.6+

- pandas 

- geopandas 

- shapely

- numpy

- tqdm

## Usage

The script can be run from the command line with various options:

### Downloading and Dividing Data

To download data for a specific location and optionally divide it:

```
python main.py --download <location> --output <output_folder> [--divide]
```

- `<location>`: Name of the location to download data for (e.g., "Egypt")
- `<output_folder>`: Folder to save the downloaded and processed data
- `--divide`: Optional flag to divide the data into smaller chunks immediately after download

### Extracting Data

To extract building data for a specific bounding box:

```
python main.py --extract --input <input_folder> --output-file <output_file> --top-left <lat,lon> --bottom-right <lat,lon>
```

- `<input_folder>`: Folder containing the divided GeoJSON files
- `<output_file>`: Name of the output GeoJSON file for extracted data
- `<lat,lon>`: Latitude and longitude coordinates for the top-left and bottom-right corners of the bounding box

## How It Works

1. **Downloading**: The script downloads building footprint data from Microsoft's dataset for the specified location.

2. **Dividing**: If the `--divide` flag is used, the downloaded data is divided into smaller GeoJSON files based on an adaptive grid system. This makes it easier to manage large datasets.

3. **Extracting**: The extraction process uses the metadata created during the division step to efficiently locate and process only the relevant GeoJSON files that intersect with the specified bounding box.

## Output

The script produces GeoJSON files containing building footprint data. Each feature in the output includes:

- Geometry (polygon representing the building outline)
- Properties:
  - type: "Feature"
  - height: Building height (if available)
  - confidence: Confidence score of the building detection

## Notes

- The script uses a spatial index to optimize the extraction process for large datasets.
- Error handling is implemented to manage issues with file access, data parsing, and user input.
- Progress bars are provided for long-running operations to give users feedback on the process.

## Limitations

- The accuracy and completeness of the data depend on Microsoft's original dataset.
- Processing very large areas or datasets with many buildings may require significant computational resources and time.
