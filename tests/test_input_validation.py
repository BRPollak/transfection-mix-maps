"""Regression coverage for plate identifiers, units, and stock mapping."""
import pandas as pd
import pytest

import core
from plate_preview import plate_preview_html
from sources import read_plate
from workflow import default_configs, generate


@pytest.mark.parametrize("value, expected", [
    ("100", 100), ("100 ng", 100), ("1e2ng", 100), (".5 NG", .5),
    ("+2.5E+2 ng", 250), (100.0, 100), ("0", 0), ("-1 ng", -1),
])
def test_mass_parser_accepts_complete_numeric_ng_values(value, expected):
    assert core.parse_float(value) == expected


@pytest.mark.parametrize("value", [
    "100/2", "100foo", "1 ug", "1 µg", "1 μg", "1 mg", "100 ng/uL",
    "1,000", "1e999", "NaN", "inf", "", None, pd.NA,
])
def test_mass_parser_rejects_incomplete_unsupported_or_nonfinite_values(value):
    assert core.parse_float(value) is None


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("mass", ["100/2", "100foo", "1 ug"])
def test_bad_mass_has_source_row_and_prevents_output(tmp_path, wide, mass):
    columns = "Well,Plasmid1,Mass1 (ng)" if wide else "Well,Plasmid,Mass (ng)"
    plate = f"{columns}\nA1,Stock,{mass}\n".encode()
    tables = {"Stocks": [["Plasmid", "Concentration"], ["Stock", "100"]]}
    with pytest.raises(core.MixMapError, match="unreadable DNA mass") as caught:
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs())
    assert "CSV row 2" in caught.value.details[0]
    assert mass in caught.value.details[0]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("unit", ["ug", "µg", "μg", "mg", "pg", "ng/uL"])
def test_mass_headers_reject_incompatible_units(wide, unit):
    headers = ["Well", "Plasmid1", f"Mass1 ({unit})"] if wide else ["Well", "Plasmid", f"Mass ({unit})"]
    with pytest.raises(core.MixMapError, match="Unsupported DNA mass units"):
        core.standardize_plate_csv(pd.DataFrame([["A1", "Stock", "100"]], columns=headers))


@pytest.mark.parametrize("plasmid_header, mass_headers", [
    ("Plasmid", ["Mass (ng)", "Mass (ug)"]),
    ("Plasmid", ["Mass (ug)", "Mass (ng)"]),
    ("Plasmid", ["Mass (ng)", "Desired ng"]),
    ("Plasmid", ["Mass (ng)", "Mass (ng)"]),
    ("Plasmid1", ["Mass1 (ng)", "Mass1 (ug)"]),
    ("Plasmid1", ["Mass1 (ug)", "Mass1 (ng)"]),
    ("Plasmid1", ["Mass1 (ng)", "Desired ng1"]),
    ("Plasmid1", ["Mass1 (ng)", "Mass1 (ng)"]),
    ("Plasmid1", ["Mass (ng)", "Mass (ug)"]),
    ("Plasmid1", ["Mass (ng)", "Mass (ng)"]),
    ("Plasmid1", ["Mass1 (ng)", "Mass (ug)"]),
])
def test_ambiguous_mass_columns_never_choose_a_value_silently(tmp_path, plasmid_header, mass_headers):
    columns = ["Well", plasmid_header, *mass_headers]
    plate = (",".join(columns) + "\nA1,Stock,100,1\n").encode()
    tables = {"Stocks": [["Plasmid", "Concentration"], ["Stock", "100"]]}
    with pytest.raises(core.MixMapError, match="Ambiguous DNA mass columns"):
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs())
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("mass_header", ["Mass2", "Mass 2 (ng)", "Desired ng2", "Mass02 (ng)"])
@pytest.mark.parametrize("extra_mass", ["25", "0", ""])
def test_unmatched_mass_header_names_the_missing_plasmid_before_generation(monkeypatch, mass_header, extra_mass):
    plate = f"Well,Plasmid1,Mass1 (ng),{mass_header}\nA1,Stock,100,{extra_mass}\n".encode()
    tables = {"Stocks": [["Plasmid", "Concentration"], ["Stock", "100"]]}
    monkeypatch.setattr(core, "write_mix_map_workbook", lambda *args, **kwargs: pytest.fail("Created a workbook"))
    with pytest.raises(core.MixMapError, match="mass column without a matching plasmid column") as caught:
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs())
    assert caught.value.details == [f"Found {mass_header!r} but the Plasmid2 column is missing."]
    assert "Add a Plasmid2 column" in caught.value.fixes[0]


def test_every_unmatched_mass_slot_is_reported():
    columns = ["Well", "Plasmid1", "Mass1", "Mass3 (ng)", "Mass2 (ng)"]
    with pytest.raises(core.MixMapError) as caught:
        core.standardize_plate_csv(pd.DataFrame([["A1", "Stock", "100", "10", "20"]], columns=columns))
    assert caught.value.details == [
        "Found 'Mass2 (ng)' but the Plasmid2 column is missing.",
        "Found 'Mass3 (ng)' but the Plasmid3 column is missing.",
    ]


@pytest.mark.parametrize("second_header", ["Plasmid 1", "PLASMID1", "Plasmid-1", "Plasmid01", "Plasmid1"])
def test_duplicate_plasmid_slots_report_both_headers_before_generation(monkeypatch, second_header):
    plate = f"Well,Plasmid1,Mass1 (ng),{second_header}\nA1,Stock,100,Other\n".encode()
    tables = {"Stocks": [["Plasmid", "Concentration"], ["Stock", "100"], ["Other", "50"]]}
    monkeypatch.setattr(core, "write_mix_map_workbook", lambda *args, **kwargs: pytest.fail("Created a workbook"))
    with pytest.raises(core.MixMapError, match="Duplicate plasmid columns") as caught:
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs())
    assert caught.value.details == [f"Slot 1 has multiple plasmid columns: 'Plasmid1', {second_header!r}."]
    assert "Keep exactly one Plasmid column" in caught.value.fixes[0]


def test_original_csv_header_validation_handles_bom_blank_lines_and_quoted_headers():
    plate = '\ufeff\n\nWell,"Plasmid, 1",Mass1 (ng),Plasmid1\nA1,Stock,100,Other\n'.encode()
    with pytest.raises(core.MixMapError, match="Duplicate plasmid columns") as caught:
        read_plate(plate)
    assert caught.value.details == ["Slot 1 has multiple plasmid columns: 'Plasmid, 1', 'Plasmid1'."]


def test_duplicate_plasmid_slots_in_a_dataframe_also_stop():
    frame = pd.DataFrame([["A1", "Stock", "100", "Other"]],
                         columns=["Well", "Plasmid1", "Mass1 (ng)", "Plasmid1"])
    with pytest.raises(core.MixMapError, match="Duplicate plasmid columns"):
        core.standardize_plate_csv(frame)


def test_exact_duplicate_plasmid_header_cannot_masquerade_as_slot_11():
    plate = b"Well,Plasmid1,Mass1,Plasmid1,Mass11\nA1,Stock,100,Other,25\n"
    tables = {"Stocks": [["Plasmid", "Concentration"], ["Stock", "100"], ["Other", "50"]]}
    with pytest.raises(core.MixMapError, match="Duplicate plasmid columns") as caught:
        generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs())
    assert caught.value.details == ["Slot 1 has multiple plasmid columns: 'Plasmid1', 'Plasmid1'."]


def test_extra_unnumbered_mass_in_a_multi_slot_plate_is_not_ignored():
    plate = b"Well,Plasmid1,Mass1,Plasmid2,Mass2,Mass (ng)\nA1,Stock,100,Other,25,50\n"
    with pytest.raises(core.MixMapError, match="mass columns without slot numbers") as caught:
        read_plate(plate)
    assert "'Mass (ng)'" in caught.value.details[0]
    assert "Mass1 (ng) for Plasmid1" in caught.value.fixes[0]


@pytest.mark.parametrize("header", [
    "Well,Plasmid1,Mass1 (ng)",
    "Well,Plasmid 1,Mass 1 (ng)",
    "Well,Plasmid01,Mass1 (ng)",
    "Well,Plasmid1,Mass (ng)",
    "Well,Plasmid2,Desired ng",
    "Well,Plasmid,Mass (ng)",
    "Well,Plasmid,Mass2 (ng)",
])
def test_supported_single_mass_header_aliases_still_generate_the_requested_amount(header):
    plate = f"{header}\nA1,Stock,100\n".encode()
    tables = {"Stocks": [["Plasmid", "Concentration"], ["Stock", "100"]]}
    result = generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs())
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["summary"]["Total DNA_ng"].tolist() == [100]


@pytest.mark.parametrize("second_slot", [2, 11])
def test_reordered_wide_pairs_use_every_mass_and_the_corresponding_stock(second_slot):
    plate = f"Well,Mass{second_slot} (ng),Plasmid1,Plasmid{second_slot},Mass1 (ng)\nA1,25,Stock,Other,100\n".encode()
    tables = {"Stocks": [["Plasmid", "Concentration"], ["Stock", "100"], ["Other", "50"]]}
    result = generate(plate, "plate.csv", tables, "test", "test", ["LT1"], default_configs())
    details = result["artifacts"][0]["details"]
    assert details["Plasmid"].tolist() == ["Stock", "Other"]
    assert details["Mass_ng"].tolist() == [100, 25]
    assert result["artifacts"][0]["summary"]["Total DNA_ng"].tolist() == [125]


def test_well_aliases_merge_in_long_format_and_keep_component_slots():
    frame = read_plate(b"Well,Plasmid,Mass (ng)\na01,Stock,100\nA1,Stock,50\n A 001 ,Other,25\n")
    wells, long, _ = core.standardize_plate_csv(frame)
    assert wells.to_dict("records") == [{"Well": "A1", "Row": "A", "Col": 1}]
    assert long.Well.tolist() == ["A1"] * 3
    assert long.Slot.tolist() == [1, 2, 3]
    assert long.Mass_ng.sum() == 175
    html = plate_preview_html(long, wells)
    assert 'aria-label="Well A1. Stock: 150 ng; Other: 25 ng"' in html
    assert frame.Well.tolist() == ["a01", "A1", " A 001 "]


def test_well_aliases_are_duplicate_wide_rows():
    frame = read_plate(b"Well,Plasmid1,Mass1 (ng)\nA01,Stock,100\na1,Stock,150\n")
    with pytest.raises(core.MixMapError, match="Duplicate well") as caught:
        core.standardize_plate_csv(frame)
    assert caught.value.details == ["A1: CSV rows 2, 3"]


@pytest.mark.parametrize("well", ["A0", "A00", "A000", "B-1"])
def test_invalid_wells_stop_before_calculation(well):
    with pytest.raises(core.MixMapError, match="Malformed well") as caught:
        core.standardize_plate_csv(read_plate(f"Well,Plasmid,Mass (ng)\n{well},Stock,100\n".encode()))
    assert "CSV row 2" in caught.value.details[0]


def test_populated_wide_rows_need_wells_but_fully_blank_rows_are_allowed():
    plate = b"Well,Plasmid1,Mass1 (ng)\nA1,Stock,100\n,,\n,Stock,50\n"
    with pytest.raises(core.MixMapError, match="Missing well value in wide-format") as caught:
        core.standardize_plate_csv(read_plate(plate))
    assert "CSV row 4" in caught.value.details[0]
    wells, long, warnings = core.standardize_plate_csv(read_plate(plate.replace(b",Stock,50\n", b"")))
    assert wells.Well.tolist() == ["A1"]
    assert long.Mass_ng.tolist() == [100]
    assert not warnings


@pytest.mark.parametrize("second", ["Concentration", "Conc", "Concentration (ng/uL)", "ng/µL"])
def test_multiple_concentration_candidates_cannot_silently_select_first(second):
    tables = {"Stocks": [["Plasmid", "Concentration", second], ["Stock", "50", "100"]]}
    with pytest.raises(core.MixMapError) as caught:
        core.load_plasmid_concentrations(tables, used_plasmids=["Stock"])
    assert caught.value.details == ["Stock: concentration column is ambiguous."]


@pytest.mark.parametrize("header", [
    "Concentration (nM)", "Conc (nM)", "Concentration (ug/uL)",
    "Concentration (ng/mL)", "Concentration (mg/mL)", "Concentration (molar)",
])
def test_concentration_headers_require_supported_units(header):
    with pytest.raises(core.MixMapError) as caught:
        core.load_plasmid_concentrations({"Stocks": [["Plasmid", header], ["Stock", "100"]]},
                                         used_plasmids=["Stock"])
    assert "units must be ng/µL" in caught.value.details[0]


@pytest.mark.parametrize("header", [
    "Concentration", "Conc", "Concentration (ng/uL)", "Concentration (ng/µL)",
    "Concentration (ng/μL)", "Conc (ng per uL)", "ng/uL", "ng/µL", "ng/μL", "ng microliter",
])
def test_concentration_headers_accept_unlabelled_and_ng_per_ul(header):
    _, lookup, _ = core.load_plasmid_concentrations(
        {"Stocks": [["Plasmid", header], ["Stock", "100 ng/µL"]]}, used_plasmids=["Stock"])
    assert lookup["Stock"]["Concentration_ng_per_uL"] == 100


def test_unrelated_bad_concentration_columns_remain_nonblocking():
    tables = {
        "Stocks": [["Plasmid", "Concentration"], ["Stock", "100"], ["Unused", "bad"]],
        "Ambiguous": [["Plasmid", "Concentration", "Conc"], ["Other", "50", "100"]],
        "Molar": [["Plasmid", "Concentration (nM)"], ["Other", "50"]],
        "Notes": [["Date", "Operator"], ["Oct 4", "Lab"]],
    }
    _, lookup, warnings = core.load_plasmid_concentrations(tables, used_plasmids=["Stock"])
    assert list(lookup) == ["Stock"]
    assert not warnings


def test_csv_identifiers_keep_leading_zeros_and_literal_missing_value_names():
    identifiers = ["00123", "NA", "None", "null", "nan"]
    rows = "\n".join(f"A{index},{name},100" for index, name in enumerate(identifiers, 1))
    frame = read_plate(f"Well,Plasmid,Mass (ng)\n{rows}\n".encode())
    wells, long, _ = core.standardize_plate_csv(frame)
    assert frame.Plasmid.tolist() == identifiers
    assert long.Plasmid.tolist() == identifiers
    tables = {"Stocks": [["Plasmid", "Concentration"]] + [[name, "100"] for name in identifiers]}
    _, lookup, _ = core.load_plasmid_concentrations(tables, used_plasmids=identifiers)
    matched, warnings = core.match_concentrations(long, lookup)
    assert matched["Matched plasmid"].tolist() == identifiers
    assert len(wells) == len(identifiers)
    assert not warnings


@pytest.mark.parametrize("value", [None, float("nan"), pd.NA, pd.NaT])
def test_actual_missing_cells_still_clean_to_empty(value):
    assert core.clean_cell(value) == ""
