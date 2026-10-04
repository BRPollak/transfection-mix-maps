"""Publish one complete workbook directly into an existing output folder."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

import core
from sources import LOCAL_ZONE, now_iso, read_plate

DEFAULT_CONFIGS = {
    "L2000": {
        "short_name": "L2000", "display_name": "Lipofectamine 2000",
        "reagent_label": "Lipofectamine 2000", "diluent_label": "Diluent (Opti-MEM)",
        "mode": "two_tube", "final_volume_ul": 25.0,
        "dna_to_reagent_ratio_ul_per_ug": 2.0,
        "well_overage_factor": 1.2, "bulk_overage_factor": 1.2,
    },
    "LT1": {
        "short_name": "LT1", "display_name": "LT1", "reagent_label": "LT1",
        "diluent_label": "Diluent", "mode": "single_tube", "final_volume_ul": 25.0,
        "dna_to_reagent_ratio_ul_per_ug": 3.5,
        "well_overage_factor": 1.3, "bulk_overage_factor": 1.0,
    },
}


def default_configs():
    return deepcopy(DEFAULT_CONFIGS)


def generate(plate_bytes, plate_name, tables, source_label, source_timestamp,
             reagents, configs, output_dir):
    started = time.perf_counter()
    if len(reagents) != 1 or reagents[0] not in DEFAULT_CONFIGS:
        raise core.MixMapError(
            "Choose exactly one transfectant: LT1 or L2000",
            fixes=["Select LT1 or L2000 and generate a separate workbook for each run."],
        )
    root = Path(output_dir).expanduser().resolve()
    if not root.is_dir():
        raise core.MixMapError(
            "Choose an existing output folder",
            details=[str(root)],
            fixes=["Use Save Excel files to to select a folder that already exists on your Mac."],
        )
    warnings = core.validate_run_inputs(reagents, configs, "error")
    wells, long, parsing_warnings = core.standardize_plate_csv(read_plate(plate_bytes))
    warnings.extend(parsing_warnings)
    # Avoid accidental enormous grids caused by mistyped well coordinates.
    rows = max(core.row_sort_key(r) for r in wells["Row"])
    if rows > 64 or wells["Col"].max() > 96:
        raise core.MixMapError("The plate extends beyond 64 rows or 96 columns",
                               fixes=["Check the Well column for a mistyped plate position."])
    used = sorted(set(long["Plasmid"].map(core.clean_cell)))
    concentrations, lookup, concentration_warnings = core.load_plasmid_concentrations(
        tables, duplicate_policy="error")
    warnings.extend(concentration_warnings)
    matched, matching_warnings = core.match_concentrations(long, lookup)
    warnings.extend(matching_warnings)
    reagent = reagents[0]
    details, summary, bulk, local_warnings = core.calculate_mix(wells, matched, configs[reagent])
    stem = re.sub(r"[^\w.\-]+", "_", Path(plate_name).stem)[:100] or "plate"
    stamp = datetime.now(LOCAL_ZONE).strftime("%Y%m%d_%H%M%S")
    all_warnings = core.dedupe_messages(warnings + [f"{reagent}: {w}" for w in local_warnings])
    source_hash = hashlib.sha256(json.dumps(tables, sort_keys=True).encode()).hexdigest()
    descriptor, temp_name = tempfile.mkstemp(prefix=".mixmap-", suffix=".xlsx", dir=root)
    os.close(descriptor)
    temp = Path(temp_name)
    try:
        core.write_mix_map_workbook(
            temp, Path(plate_name).name, source_label, reagent, configs[reagent],
            details, summary, bulk, concentrations, all_warnings)
        # Keep provenance inside the workbook; no sidecar file is created.
        wb = load_workbook(temp)
        ws = wb["Run config"]
        ws.append(["Concentrations loaded/refreshed at", source_timestamp])
        ws.append(["Concentration snapshot SHA256", source_hash])
        ws.append(["Plate CSV SHA256", hashlib.sha256(plate_bytes).hexdigest()])
        ws.append(["Generated at (Pacific time)", now_iso()])
        ws.append(["Duplicate concentration policy", "error"])
        wb.save(temp)
        workbook_bytes = temp.read_bytes()
        # A hard link atomically publishes the completed file and fails if the
        # name already exists. Unlike rename/replace, it cannot overwrite a run.
        for attempt in range(10):
            filename = f"{stem}_{reagent}_print_mixmap_{stamp}_{uuid.uuid4().hex[:8]}.xlsx"
            destination = root / filename
            try:
                os.link(temp, destination)
            except FileExistsError:
                if attempt == 9:
                    raise
            else:
                break
    finally:
        temp.unlink(missing_ok=True)
    artifact = {"name": filename, "path": str(destination), "bytes": workbook_bytes,
                "reagent": reagent, "summary": summary, "details": details, "bulk": bulk}
    return {"artifacts": [artifact], "folder": str(root),
            "warnings": all_warnings,
            "wells": len(wells), "entries": len(matched), "plasmids": len(used),
            "elapsed": time.perf_counter() - started, "source": source_label,
            "source_timestamp": source_timestamp}
