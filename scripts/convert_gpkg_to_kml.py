#!/usr/bin/env python3
"""Convert every .gpkg in drop_gpkg_here/ to KML files in converted_kml/."""

from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "drop_gpkg_here"
STYLE_DIR = ROOT / "drop_style_files_here"
OUTPUT_DIR = ROOT / "converted_kml"
PROCESSED_DIR = ROOT / "processed_gpkg"
PROCESSED_STYLE_DIR = ROOT / "processed_style_files"
KML_NS = "http://www.opengis.net/kml/2.2"

ET.register_namespace("", KML_NS)


@dataclass
class SymbolStyle:
    line_color: str | None = None
    line_width: float | None = None
    poly_color: str | None = None
    poly_fill: bool | None = None
    poly_outline: bool | None = None
    icon_color: str | None = None
    icon_scale: float | None = None


@dataclass
class CategorizedQmlStyle:
    attribute_name: str
    value_to_symbol: dict[str, str]
    symbol_styles: dict[str, SymbolStyle]


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "layer"


def feature_layers(gpkg_path: Path) -> list[str]:
    query = """
        SELECT table_name
        FROM gpkg_contents
        WHERE data_type = 'features'
        ORDER BY table_name;
    """
    with sqlite3.connect(gpkg_path) as conn:
        rows = conn.execute(query).fetchall()
    return [row[0] for row in rows]


def run_cmd(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def archive_processed_gpkg(gpkg_path: Path) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    destination = unique_destination(PROCESSED_DIR / gpkg_path.name)
    shutil.move(str(gpkg_path), str(destination))
    return destination


def archive_style_file(style_path: Path) -> Path:
    PROCESSED_STYLE_DIR.mkdir(parents=True, exist_ok=True)
    destination = unique_destination(PROCESSED_STYLE_DIR / style_path.name)
    shutil.move(str(style_path), str(destination))
    return destination


def parse_rgba_from_qml_value(raw_value: str) -> tuple[int, int, int, int] | None:
    parts = raw_value.split(",")
    if len(parts) < 4:
        return None
    try:
        r = int(parts[0].strip())
        g = int(parts[1].strip())
        b = int(parts[2].strip())
        a = int(parts[3].strip())
    except ValueError:
        return None
    return (r, g, b, a)


def rgba_to_kml_color(r: int, g: int, b: int, a: int) -> str:
    return f"{a:02x}{b:02x}{g:02x}{r:02x}"


def qml_options_from_symbol(symbol_elem: ET.Element) -> dict[str, str]:
    options: dict[str, str] = {}
    first_layer = symbol_elem.find("./layer")
    if first_layer is None:
        return options

    option_map = first_layer.find("./Option")
    if option_map is None:
        return options

    for opt in option_map.findall("./Option"):
        name = opt.attrib.get("name")
        value = opt.attrib.get("value")
        if name is not None and value is not None:
            options[name] = value
    return options


def parse_qml_symbol_style(symbol_elem: ET.Element) -> SymbolStyle:
    symbol_type = (symbol_elem.attrib.get("type") or "").strip().lower()
    alpha = 1.0
    try:
        alpha = float(symbol_elem.attrib.get("alpha", "1"))
    except ValueError:
        alpha = 1.0

    options = qml_options_from_symbol(symbol_elem)
    style = SymbolStyle()

    if symbol_type == "fill":
        fill_rgba = parse_rgba_from_qml_value(options.get("color", ""))
        if fill_rgba is not None:
            r, g, b, a = fill_rgba
            a = max(0, min(255, int(round(a * alpha))))
            style.poly_color = rgba_to_kml_color(r, g, b, a)
        style.poly_fill = options.get("style", "solid") != "no"

        outline_style = options.get("outline_style", "solid")
        style.poly_outline = outline_style != "no"
        if style.poly_outline:
            outline_rgba = parse_rgba_from_qml_value(options.get("outline_color", ""))
            if outline_rgba is not None:
                r, g, b, a = outline_rgba
                a = max(0, min(255, int(round(a * alpha))))
                style.line_color = rgba_to_kml_color(r, g, b, a)
            try:
                width_mm = float(options.get("outline_width", "1"))
                style.line_width = max(1.0, round(width_mm * 3.0, 2))
            except ValueError:
                style.line_width = 1.0

    elif symbol_type == "line":
        line_rgba = parse_rgba_from_qml_value(options.get("line_color", ""))
        if line_rgba is not None:
            r, g, b, a = line_rgba
            a = max(0, min(255, int(round(a * alpha))))
            style.line_color = rgba_to_kml_color(r, g, b, a)
        try:
            width_mm = float(options.get("line_width", "1"))
            style.line_width = max(1.0, round(width_mm * 3.0, 2))
        except ValueError:
            style.line_width = 1.0

    elif symbol_type == "marker":
        marker_rgba = parse_rgba_from_qml_value(options.get("color", ""))
        if marker_rgba is not None:
            r, g, b, a = marker_rgba
            a = max(0, min(255, int(round(a * alpha))))
            style.icon_color = rgba_to_kml_color(r, g, b, a)
        try:
            size_mm = float(options.get("size", "3"))
            style.icon_scale = max(0.3, round(size_mm / 3.0, 2))
        except ValueError:
            style.icon_scale = 1.0

    return style


def parse_categorized_qml_style(qml_path: Path) -> CategorizedQmlStyle | None:
    try:
        tree = ET.parse(qml_path)
    except ET.ParseError:
        return None

    root = tree.getroot()
    renderer = root.find(".//renderer-v2[@type='categorizedSymbol']")
    if renderer is None:
        return None

    attribute_name = (renderer.attrib.get("attr") or "").strip()
    if not attribute_name:
        return None

    symbols_parent = renderer.find("./symbols")
    categories_parent = renderer.find("./categories")
    if symbols_parent is None or categories_parent is None:
        return None

    symbol_styles: dict[str, SymbolStyle] = {}
    for symbol_elem in symbols_parent.findall("./symbol"):
        symbol_name = (symbol_elem.attrib.get("name") or "").strip()
        if not symbol_name:
            continue
        symbol_styles[symbol_name] = parse_qml_symbol_style(symbol_elem)

    value_to_symbol: dict[str, str] = {}
    for cat in categories_parent.findall("./category"):
        render = (cat.attrib.get("render") or "true").strip().lower()
        if render in {"0", "false"}:
            continue
        value = (cat.attrib.get("value") or "").strip()
        symbol_name = (cat.attrib.get("symbol") or "").strip()
        if value and symbol_name:
            value_to_symbol[value] = symbol_name

    if not symbol_styles or not value_to_symbol:
        return None

    return CategorizedQmlStyle(
        attribute_name=attribute_name,
        value_to_symbol=value_to_symbol,
        symbol_styles=symbol_styles,
    )


def qml_stem_match_score(stem: str, layer: str) -> int:
    stem_l = stem.lower()
    layer_l = layer.lower()
    if stem_l == layer_l:
        return 100
    if stem_l.endswith("_" + layer_l):
        return 95
    if stem_l.endswith(layer_l):
        return 90
    if layer_l in stem_l:
        return 80
    return 0


def list_style_files() -> tuple[list[Path], list[Path]]:
    candidates: list[Path] = []
    for directory in [STYLE_DIR, INPUT_DIR]:
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.is_file():
                candidates.append(path)

    # Keep only one path per absolute file path to avoid duplicates.
    unique = sorted({p.resolve(): p for p in candidates}.values(), key=lambda p: p.name.lower())
    qml_candidates = [p for p in unique if p.suffix.lower() == ".qml"]
    stylx_candidates = [p for p in unique if p.suffix.lower() == ".stylx"]
    return qml_candidates, stylx_candidates


def detect_sidecar_style_files(layer: str) -> tuple[Path | None, Path | None]:
    qml_candidates, stylx_candidates = list_style_files()

    qml_match: Path | None = None
    qml_best_score = 0
    for candidate in qml_candidates:
        score = qml_stem_match_score(candidate.stem, layer)
        if score > qml_best_score:
            qml_best_score = score
            qml_match = candidate
    if qml_match is None and len(qml_candidates) == 1:
        qml_match = qml_candidates[0]

    stylx_match: Path | None = None
    stylx_best_score = 0
    for candidate in stylx_candidates:
        score = qml_stem_match_score(candidate.stem, layer)
        if score > stylx_best_score:
            stylx_best_score = score
            stylx_match = candidate
    if stylx_match is None and len(stylx_candidates) == 1:
        stylx_match = stylx_candidates[0]

    return qml_match, stylx_match


def ensure_child(parent: ET.Element, child_tag: str) -> ET.Element:
    for child in parent:
        if child.tag == child_tag:
            return child
    created = ET.Element(child_tag)
    parent.append(created)
    return created


def apply_symbol_style_to_placemark(placemark: ET.Element, style: SymbolStyle) -> None:
    style_elem = ET.Element(f"{{{KML_NS}}}Style")

    if style.line_color is not None or style.line_width is not None:
        line_style = ensure_child(style_elem, f"{{{KML_NS}}}LineStyle")
        if style.line_color is not None:
            ensure_child(line_style, f"{{{KML_NS}}}color").text = style.line_color
        if style.line_width is not None:
            ensure_child(line_style, f"{{{KML_NS}}}width").text = f"{style.line_width:.2f}".rstrip("0").rstrip(".")

    if style.poly_color is not None or style.poly_fill is not None or style.poly_outline is not None:
        poly_style = ensure_child(style_elem, f"{{{KML_NS}}}PolyStyle")
        if style.poly_color is not None:
            ensure_child(poly_style, f"{{{KML_NS}}}color").text = style.poly_color
        if style.poly_fill is not None:
            ensure_child(poly_style, f"{{{KML_NS}}}fill").text = "1" if style.poly_fill else "0"
        if style.poly_outline is not None:
            ensure_child(poly_style, f"{{{KML_NS}}}outline").text = "1" if style.poly_outline else "0"

    if style.icon_color is not None or style.icon_scale is not None:
        icon_style = ensure_child(style_elem, f"{{{KML_NS}}}IconStyle")
        if style.icon_color is not None:
            ensure_child(icon_style, f"{{{KML_NS}}}color").text = style.icon_color
        if style.icon_scale is not None:
            ensure_child(icon_style, f"{{{KML_NS}}}scale").text = f"{style.icon_scale:.2f}".rstrip("0").rstrip(".")

    placemark[:] = [child for child in placemark if child.tag != f"{{{KML_NS}}}Style"]
    placemark.insert(0, style_elem)


def apply_qml_styles_to_kml(kml_path: Path, qml_path: Path) -> tuple[int, int] | None:
    qml_style = parse_categorized_qml_style(qml_path)
    if qml_style is None:
        return None

    try:
        tree = ET.parse(kml_path)
    except ET.ParseError:
        return None

    root = tree.getroot()
    ns = {"kml": KML_NS}

    placemarks = root.findall(".//kml:Placemark", ns)
    if not placemarks:
        return (0, 0)

    styled = 0
    unmatched = 0

    for placemark in placemarks:
        value = None
        for item in placemark.findall(".//kml:SimpleData", ns):
            if item.attrib.get("name") == qml_style.attribute_name:
                value = (item.text or "").strip()
                break

        if not value:
            unmatched += 1
            continue

        symbol_name = qml_style.value_to_symbol.get(value)
        if symbol_name is None:
            unmatched += 1
            continue

        symbol_style = qml_style.symbol_styles.get(symbol_name)
        if symbol_style is None:
            unmatched += 1
            continue

        apply_symbol_style_to_placemark(placemark, symbol_style)
        styled += 1

    tree.write(kml_path, encoding="utf-8", xml_declaration=True)
    return (styled, unmatched)


def convert_file(gpkg_path: Path) -> tuple[int, int]:
    layers = feature_layers(gpkg_path)
    if not layers:
        print(f"- {gpkg_path.name}: skipped (no feature layers found)")
        return 0, 0

    converted = 0
    failed = 0
    base = safe_name(gpkg_path.stem)

    for layer in layers:
        layer_safe = safe_name(layer)
        if len(layers) == 1:
            out_name = f"{base}.kml"
        else:
            out_name = f"{base}__{layer_safe}.kml"

        out_path = OUTPUT_DIR / out_name
        cmd = [
            "ogr2ogr",
            "-f",
            "KML",
            str(out_path),
            str(gpkg_path),
            layer,
            "-skipfailures",
        ]

        try:
            run_cmd(cmd)
            converted += 1
            print(f"  -> {out_name}")

            qml_path, stylx_path = detect_sidecar_style_files(layer)
            if qml_path is not None:
                style_result = apply_qml_styles_to_kml(out_path, qml_path)
                if style_result is None:
                    print(f"     style: detected {qml_path.name}, but this QML renderer is not supported")
                else:
                    styled_count, unmatched_count = style_result
                    print(
                        f"     style: applied from {qml_path.name} "
                        f"({styled_count} placemarks styled, {unmatched_count} unmatched)"
                    )
            if stylx_path is not None:
                print(
                    f"     style: detected {stylx_path.name} "
                    "(STYLX is not automatically convertible to Google Earth KML styles)"
                )
        except subprocess.CalledProcessError as exc:
            failed += 1
            print(f"  !! failed layer '{layer}':")
            if exc.stderr:
                print(exc.stderr.strip())

    return converted, failed


def main() -> int:
    print("GPKG -> KML converter")
    print(f"Input:  {INPUT_DIR}")
    print(f"Styles: {STYLE_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Archive: {PROCESSED_DIR}")
    print(f"Style Archive: {PROCESSED_STYLE_DIR}\n")

    if shutil.which("ogr2ogr") is None:
        print("ERROR: 'ogr2ogr' not found.")
        print("Install GDAL first (macOS): brew install gdal")
        return 1

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    STYLE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_STYLE_DIR.mkdir(parents=True, exist_ok=True)

    gpkg_files = sorted(INPUT_DIR.glob("*.gpkg"))
    if not gpkg_files:
        print("No .gpkg files found in drop_gpkg_here/. Nothing to do.")
        return 0

    files_ok = 0
    files_failed = 0
    layer_ok = 0
    layer_failed = 0

    for gpkg in gpkg_files:
        print(f"Processing {gpkg.name}")
        try:
            ok, fail = convert_file(gpkg)
            layer_ok += ok
            layer_failed += fail
            if fail == 0 and ok > 0:
                try:
                    archived_to = archive_processed_gpkg(gpkg)
                    print(f"  archived: {archived_to.name}")
                    files_ok += 1
                except OSError as exc:
                    files_failed += 1
                    print(f"  !! archive failed for {gpkg.name}: {exc}")
            elif ok == 0 and fail == 0:
                # no feature layers, count as failed/ignored for visibility
                files_failed += 1
            else:
                files_failed += 1
        except sqlite3.Error as exc:
            files_failed += 1
            print(f"- {gpkg.name}: failed to read GeoPackage metadata ({exc})")

    print("\nDone.")
    print(f"Files succeeded: {files_ok}")
    print(f"Files with issues: {files_failed}")
    print(f"Layers converted: {layer_ok}")
    print(f"Layers failed: {layer_failed}")

    style_archive_failed = 0

    # Keep the style input folder clean only after a fully successful conversion batch.
    if files_ok > 0 and files_failed == 0 and layer_failed == 0:
        style_candidates = sorted(
            [p for p in STYLE_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".qml", ".stylx"}]
        )
        moved_styles = 0
        for style_file in style_candidates:
            try:
                archive_style_file(style_file)
                moved_styles += 1
            except OSError as exc:
                style_archive_failed += 1
                print(f"  !! style archive failed for {style_file.name}: {exc}")
        if moved_styles > 0:
            print(f"Style files archived: {moved_styles}")
    elif files_ok > 0:
        print("Style files not archived because the conversion batch had issues.")

    return 0 if files_failed == 0 and layer_failed == 0 and style_archive_failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
