#!/usr/bin/env python3
"""Small, dependency-free XLSX reader used by the baseline ingestors.

The production dashboard intentionally builds with the Python standard library.
Pulling pandas/openpyxl into the scheduled workflow just to read two source
workbooks would make refreshes less reliable.  XLSX files are ZIP archives of
XML parts; this module exposes the narrow surface the IEA and London Register
ingestors need while preserving native numeric values and cached formula values.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN, "r": REL, "p": PKG_REL}


def column_index(cell_ref: str) -> int:
    """Return a zero-based column index for an A1-style cell reference."""
    letters = re.match(r"[A-Z]+", cell_ref.upper())
    if not letters:
        raise ValueError(f"invalid cell reference: {cell_ref!r}")
    value = 0
    for char in letters.group(0):
        value = value * 26 + ord(char) - 64
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    out = []
    for si in root.findall("m:si", NS):
        out.append("".join(node.text or "" for node in si.iter(f"{{{MAIN}}}t")))
    return out


def sheet_targets(path: str | Path) -> dict[str, str]:
    """Return ``{sheet name: zip member}`` for an XLSX workbook."""
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        by_id = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall("p:Relationship", NS)
        }
        result = {}
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            target = by_id[sheet.attrib[f"{{{REL}}}id"]]
            result[sheet.attrib["name"]] = "xl/" + target.lstrip("/")
        return result


def read_sheet(path: str | Path, sheet_name: str) -> list[list[object | None]]:
    """Read one worksheet into a rectangular list of native cell values."""
    targets = sheet_targets(path)
    if sheet_name not in targets:
        raise KeyError(f"sheet {sheet_name!r} not found; available: {sorted(targets)}")
    with zipfile.ZipFile(path) as archive:
        strings = _shared_strings(archive)
        root = ET.fromstring(archive.read(targets[sheet_name]))

    sparse_rows: list[dict[int, object | None]] = []
    max_col = -1
    for row in root.findall("m:sheetData/m:row", NS):
        values: dict[int, object | None] = {}
        for cell in row.findall("m:c", NS):
            idx = column_index(cell.attrib["r"])
            max_col = max(max_col, idx)
            value_node = cell.find("m:v", NS)
            inline = cell.find("m:is", NS)
            if inline is not None:
                value: object | None = "".join(
                    node.text or "" for node in inline.iter(f"{{{MAIN}}}t")
                )
            elif value_node is None:
                value = None
            else:
                raw = value_node.text or ""
                cell_type = cell.attrib.get("t")
                if cell_type == "s":
                    value = strings[int(raw)]
                elif cell_type in {"str", "inlineStr"}:
                    value = raw
                elif cell_type == "b":
                    value = raw == "1"
                else:
                    try:
                        number = float(raw)
                        value = int(number) if number.is_integer() else number
                    except ValueError:
                        value = raw
            values[idx] = value
        sparse_rows.append(values)

    width = max_col + 1
    return [[row.get(col) for col in range(width)] for row in sparse_rows]


def normalise_header(value: object | None) -> str:
    """Normalise a worksheet header for schema matching."""
    text = str(value or "").strip().lower()
    text = re.sub(r"co[₂2]", "co2", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")
