# AGENTS.md

## Project Goal

Convert GeoPackage (`.gpkg`) files dropped into `drop_gpkg_here/` into KML (`.kml`) files for Google Earth Pro.

## Repository Conventions

- Keep the converter entrypoint at `scripts/convert_gpkg_to_kml.py`.
- Keep the double-click launcher at `run_converter.command`.
- Input folder: `drop_gpkg_here/`.
- Style input folder: `drop_style_files_here/`.
- Output folder: `converted_kml/`.
- Archive folder for completed inputs: `processed_gpkg/`.
- Archive folder for processed styles: `processed_style_files/`.
- Prefer standard-library Python where possible.
- For conversion engine, use GDAL `ogr2ogr` unless explicitly changed.
- If `.qml` sidecar styles exist next to a `.gpkg`, apply supported categorized styles to output KML placemarks.
- Detect `.stylx` files for visibility, but treat them as informational unless explicit STYLX conversion support is added.

## Validation Checklist

- `run_converter.command` is executable.
- Script handles multiple `.gpkg` files in one run.
- Script handles multiple layers per `.gpkg`.
- README usage steps remain accurate.
