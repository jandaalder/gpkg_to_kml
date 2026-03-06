# GPKG to KML Converter

I don't like QGIS. I have it installed and I should probably learn to use it properly. But now most of my use cases are just quickly inspecting a .gpkg file and comparing it to satellite imagery or Google Streetview. Or to one of the other layers I already have in Google Earth Pro. For those use cases I built this easy to use local tool to convert `.gpkg` files into `.kml` files.

## Folder Structure

- `drop_gpkg_here/`: put your `.gpkg` files here.
- `drop_style_files_here/`: optional `.qml` and `.stylx` style files.
- `converted_kml/`: converted `.kml` files are written here.
- `processed_gpkg/`: successfully converted `.gpkg` files are moved here automatically.
- `processed_style_files/`: style files are moved here after successful conversion runs.
- `scripts/convert_gpkg_to_kml.py`: conversion logic.
- `run_converter.command`: double-click this on macOS to run conversion.

## One-Time Setup (macOS)

1. Install Python 3 (if needed).
2. Install GDAL (provides `ogr2ogr`):

```bash
brew install gdal
```

## Daily Use

1. Copy one or more `.gpkg` files into `drop_gpkg_here/`.
2. (Optional) Copy matching `.qml`/`.stylx` files into `drop_style_files_here/`.
3. Double-click `run_converter.command`.
4. Open generated `.kml` files from `converted_kml/` in Google Earth Pro.
5. Converted `.gpkg` files will be moved to `processed_gpkg/` so they are not reprocessed in the next run.

## Notes

- If a `.gpkg` has multiple feature layers, one `.kml` is created per layer.
- Output files are overwritten if names already exist.
- Archived `.gpkg` names are de-duplicated automatically (`name_2.gpkg`, `name_3.gpkg`, ...).
- Archived style names are also de-duplicated automatically.
- Style files are matched by filename similarity to each layer name (best match wins).
- If matching `.qml` files are in the same folder as the `.gpkg`, categorized QGIS colors are applied to the exported KML where possible.
- For backward compatibility, `.qml`/`.stylx` files in `drop_gpkg_here/` are also detected.
- If `.stylx` files are present, they are detected and reported, but not auto-converted to KML style (Google Earth style model differs from ArcGIS style libraries).
- If at least one `.gpkg` is converted successfully, `.qml`/`.stylx` files from `drop_style_files_here/` are moved to `processed_style_files/`.
