import csv
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

import core
import workflow
from sources import read_plate
from workflow import default_configs, generate

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def inputs():
    """Synthetic inputs exist only as test fixtures, never as app input options."""
    plate = (FIXTURES / "plate.csv").read_bytes()
    with (FIXTURES / "concentrations.csv").open(newline="", encoding="utf-8-sig") as handle:
        tables = {"concentrations": list(csv.reader(handle))}
    return plate, tables


def calculate(reagent, raw=None):
    plate, tables = inputs()
    wells, long, _ = core.standardize_plate_csv(read_plate(plate) if raw is None else raw)
    _, lookup, _ = core.load_plasmid_concentrations(tables, used_plasmids=long.Plasmid.tolist())
    matched, _ = core.match_concentrations(long, lookup)
    return core.calculate_mix(wells, matched, default_configs()[reagent])


def test_lt1_known_volumes():
    details, summary, bulk, warnings = calculate("LT1")
    a1 = summary.set_index("Well").loc["A1"]
    assert a1["Total DNA_ng"] == 150
    assert a1["Total working DNA_uL"] == pytest.approx(2.6)
    assert a1["Reagent_uL"] == pytest.approx(0.6825)
    assert a1["DNA diluent_uL"] == pytest.approx(29.2175)
    assert a1["DNA mix target_uL"] == pytest.approx(32.5)
    assert bulk == {}


def test_l2000_known_volumes():
    assert default_configs()["L2000"]["final_volume_ul"] == 25
    _, summary, bulk, _ = calculate("L2000")
    a1 = summary.set_index("Well").loc["A1"]
    assert a1["DNA mix target_uL"] == pytest.approx(15)
    assert a1["Total working DNA_uL"] == pytest.approx(2.4)
    assert a1["DNA diluent_uL"] == pytest.approx(12.6)
    assert a1["Reagent_uL"] == pytest.approx(0.36)
    assert a1["Transfection diluent_uL"] == pytest.approx(14.64)
    assert bulk["Bulk reagent_uL"] == pytest.approx(1.728)
    assert bulk["Bulk total_uL"] == pytest.approx(72)


@pytest.mark.parametrize("reagent", ["LT1", "L2000"])
def test_long_and_wide_match(reagent):
    long = pd.DataFrame([
        ["A1", "Example_A", 100], ["A1", "Example_B", 50],
        ["A2", "Example_A", 100], ["A2", "Example_C", 50],
        ["B1", "Example_B", 150], ["B2", "Example_C", 150],
    ], columns=["Well", "Plasmid", "Mass (ng)"])
    pd.testing.assert_frame_equal(calculate(reagent)[1], calculate(reagent, long)[1])


def test_conflicting_concentrations_only_block_used_plasmids():
    tables = {"Stock": [["Plasmid", "Concentration"], ["A", "100"], ["A", "200"], ["B", "50"]]}
    with pytest.raises(core.MixMapError, match="Conflicting duplicate"):
        core.load_plasmid_concentrations(tables, used_plasmids=["A"])
    core.load_plasmid_concentrations(tables, used_plasmids=["B"])


@pytest.mark.parametrize("plate_plasmid", ["A", "B"])
def test_generation_always_rejects_conflicting_concentrations(tmp_path, plate_plasmid):
    plate = f"Well,Plasmid,Mass (ng)\nA1,{plate_plasmid},100\n".encode()
    tables = {"Stock": [["Plasmid", "Concentration"], ["A", "100"], ["A", "200"], ["B", "50"]]}
    with pytest.raises(core.MixMapError, match="Conflicting duplicate"):
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs(), tmp_path)
    assert not list(tmp_path.iterdir())


def test_missing_concentration_stops():
    _, long, _ = core.standardize_plate_csv(pd.DataFrame([["A1", "Missing", 100]], columns=["Well", "Plasmid", "Mass (ng)"]))
    with pytest.raises(core.MixMapError, match="Missing or ambiguous"):
        core.match_concentrations(long, {})


def test_duplicate_wide_wells_stop():
    plate, _ = inputs()
    raw = read_plate(plate)
    with pytest.raises(core.MixMapError, match="Duplicate well"):
        core.standardize_plate_csv(pd.concat([raw, raw.iloc[:1]], ignore_index=True))


@pytest.mark.parametrize("value", ["1e999", "-1e999", "nan", "inf"])
def test_nonfinite_numbers_rejected(value):
    assert core.parse_float(value) is None


def test_impossible_volume_does_not_publish_partial_run(tmp_path):
    plate, tables = inputs()
    configs = default_configs()
    configs["LT1"]["final_volume_ul"] = 0.1
    with pytest.raises(core.MixMapError, match="more volume"):
        generate(plate, "plate.csv", tables, "test", "test-time", ["LT1"], configs, tmp_path)
    assert not list(tmp_path.iterdir())


def test_google_sheet_tab_provenance_preserved():
    tables = {
        "Stock A": [["Plasmid", "Concentration (ng/uL)"], ["A", "100"]],
        "Stock B": [["Plasmid", "Concentration (ng/uL)"], ["B", "50"]],
    }
    _, lookup, _ = core.load_plasmid_concentrations(tables)
    assert lookup["B"]["Source worksheet"] == "Stock B"
    assert lookup["B"]["Source row"] == 2


@pytest.mark.parametrize("reagent", ["LT1", "L2000"])
def test_workbooks_and_repeated_runs(tmp_path, reagent):
    plate, tables = inputs()
    args = (plate, "plate.csv", tables, "test source", "2026-10-04T12:00:00-07:00", [reagent], default_configs(), tmp_path)
    first = generate(*args)
    first_file = Path(first["artifacts"][0]["path"])
    first_bytes = first_file.read_bytes()
    second = generate(*args)
    assert first["folder"] == second["folder"] == str(tmp_path)
    assert first["artifacts"][0]["name"] != second["artifacts"][0]["name"]
    assert first_file.read_bytes() == first_bytes
    assert len(first["artifacts"]) == 1
    assert first["artifacts"][0]["reagent"] == reagent
    saved = list(tmp_path.iterdir())
    assert len(saved) == 2
    assert all(path.is_file() and path.suffix == ".xlsx" for path in saved)
    for artifact in first["artifacts"]:
        wb = load_workbook(BytesIO(artifact["bytes"]))
        assert {"Mix Map", "Per-well details", "Concentrations used", "Well summary", "Run config"} <= set(wb.sheetnames)
        assert wb["Mix Map"].page_setup.orientation == "landscape"
        assert str(wb["Mix Map"].page_setup.paperSize) == wb["Mix Map"].PAPERSIZE_LETTER
        assert wb["Mix Map"].page_setup.fitToWidth == 1
        config = dict(wb["Run config"].iter_rows(min_row=2, values_only=True))
        assert config["Concentrations loaded/refreshed at"] == args[4]
        assert config["Duplicate concentration policy"] == "error"
        assert len(config["Concentration snapshot SHA256"]) == 64


def test_missing_output_folder_is_not_created(tmp_path):
    plate, tables = inputs()
    missing = tmp_path / "missing" / "nested"
    with pytest.raises(core.MixMapError, match="existing output folder"):
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs(), missing)
    assert not list(tmp_path.iterdir())


def test_output_path_must_be_a_folder(tmp_path):
    plate, tables = inputs()
    existing_file = tmp_path / "existing.xlsx"
    existing_file.write_bytes(b"previous workbook")
    with pytest.raises(core.MixMapError, match="existing output folder"):
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs(), existing_file)
    assert existing_file.read_bytes() == b"previous workbook"


def test_failed_workbook_write_leaves_no_partial_file(tmp_path, monkeypatch):
    plate, tables = inputs()

    def fail_after_starting(path, *args):
        path.write_bytes(b"incomplete workbook")
        raise OSError("disk write failed")

    monkeypatch.setattr(core, "write_mix_map_workbook", fail_after_starting)
    with pytest.raises(OSError, match="disk write failed"):
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs(), tmp_path)
    assert not list(tmp_path.iterdir())


def test_publication_collision_preserves_existing_file_and_retries(tmp_path, monkeypatch):
    plate, tables = inputs()
    real_link = workflow.os.link
    collisions = []

    def collide_once(source, destination):
        if not collisions:
            destination.write_bytes(b"another process saved this file")
            collisions.append(destination)
        return real_link(source, destination)

    monkeypatch.setattr(workflow.os, "link", collide_once)
    result = generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs(), tmp_path)
    assert collisions[0].read_bytes() == b"another process saved this file"
    saved = Path(result["artifacts"][0]["path"])
    assert saved != collisions[0]
    assert saved.read_bytes() == result["artifacts"][0]["bytes"]
    assert len(list(tmp_path.iterdir())) == 2


def test_failed_publication_removes_temporary_file(tmp_path, monkeypatch):
    plate, tables = inputs()

    def fail_publication(*args):
        raise PermissionError("cannot publish")

    monkeypatch.setattr(workflow.os, "link", fail_publication)
    with pytest.raises(PermissionError, match="cannot publish"):
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs(), tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("reagents", [[], ["LT1", "L2000"], ["LT1", "LT1"], ["unknown"]])
def test_invalid_reagent_selection_does_not_publish_output(tmp_path, reagents):
    plate, tables = inputs()
    with pytest.raises(core.MixMapError, match="exactly one transfectant"):
        generate(plate, "plate.csv", tables, "test", "test", reagents,
                 default_configs(), tmp_path)
    assert not list(tmp_path.iterdir())


def test_small_volume_warning_survives_to_workbook(tmp_path):
    plate = b"Well,Plasmid,Mass (ng)\nA1,A,1\n"
    tables = {"stocks": [["Plasmid", "Concentration"], ["A", "100"]]}
    result = generate(plate, "small.csv", tables, "test", "test", ["LT1"], default_configs(), tmp_path)
    assert any("below 0.200" in w for w in result["warnings"])
    wb = load_workbook(BytesIO(result["artifacts"][0]["bytes"]))
    assert "Warnings" in wb.sheetnames
