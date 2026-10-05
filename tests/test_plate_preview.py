from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
import pandas as pd
import pytest

from core import BULK_MIX_SYMBOLS, group_dna_masses, standardize_plate_csv
from plate_preview import plate_preview_html
from workflow import default_configs, generate


class PreviewParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.wells = {}
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if "data-well" in attrs:
            self.wells[attrs["data-well"]] = attrs

    def with_class(self, name):
        return [attrs for _, attrs in self.elements if name in attrs.get("class", "").split()]


def test_initial_preview_has_all_48_wells_without_interactions():
    preview = PreviewParser(plate_preview_html())
    assert list(preview.wells) == [f"{row}{col}" for row in "ABCDEF" for col in range(1, 9)]
    for attrs in preview.wells.values():
        assert "tmm-well-empty" in attrs["class"]
        assert "tabindex" not in attrs
        assert "title" not in attrs
        assert "aria-label" not in attrs
    assert not any(attrs.get("class") == "tmm-well-tooltip" for _, attrs in preview.elements)
    assert not preview.with_class("tmm-well-marker")
    assert not preview.with_class("tmm-mass-explanation")


def test_wide_plate_populates_correct_wells_and_masses():
    raw = pd.read_csv(Path(__file__).parent / "fixtures" / "plate.csv")
    wells, long, _ = standardize_plate_csv(raw)
    html = plate_preview_html(long, wells)
    preview = PreviewParser(html)
    filled = {well for well, attrs in preview.wells.items() if "tmm-well-filled" in attrs["class"]}
    assert filled == {"A1", "A2", "B1", "B2"}
    assert preview.wells["A1"]["tabindex"] == "0"
    assert preview.wells["A1"]["aria-label"] == "Well A1. Example_A: 100 ng; Example_B: 50 ng"
    assert "tmm-well-empty" in preview.wells["F8"]["class"]


def test_long_layout_combines_repeated_plasmids_and_normalizes_well_ids():
    raw = pd.DataFrame({"Well": ["a01", "A1", "A01", "F8"],
                        "Plasmid": ["A", "A", "B", "Zero"], "Mass (ng)": [50, 25, 12.5, 0]})
    wells, long, _ = standardize_plate_csv(raw)
    preview = PreviewParser(plate_preview_html(long, wells))
    assert preview.wells["A1"]["aria-label"] == "Well A1. A: 75 ng; B: 12.5 ng"
    assert "tmm-well-empty" in preview.wells["F8"]["class"]
    assert "tabindex" not in preview.wells["F8"]


def test_plasmid_html_is_escaped_in_tooltips_and_accessible_labels():
    name = '<script>alert("DNA")</script> & plasmid'
    long = pd.DataFrame({"Well": ["A1"], "Plasmid": [name], "Mass_ng": [1.25]})
    html = plate_preview_html(long)
    preview = PreviewParser(html)
    assert not any(tag == "script" for tag, _ in preview.elements)
    assert "&lt;script&gt;" in html
    assert preview.wells["A1"]["aria-label"] == f"Well A1. {name}: 1.25 ng"


def test_96_preview_includes_full_geometry_and_ignores_outside_empty_wells():
    long = pd.DataFrame({"Well": ["G1", "A9", "A1"], "Plasmid": ["A", "B", "C"], "Mass_ng": [1, 2, 3]})
    wells = pd.DataFrame({"Well": ["G1", "A9", "A1", "AA1", "AB1", "H12"]})
    html = plate_preview_html(long, wells, plate_type=96)
    preview = PreviewParser(html)
    assert "Wells outside" not in html
    assert len(preview.wells) == 96
    assert "tmm-well-filled" in preview.wells["A1"]["class"]
    assert "tmm-well-filled" in preview.wells["G1"]["class"]
    assert "tmm-well-empty" in preview.wells["H12"]["class"]


@pytest.mark.parametrize("count", [2, 3, 4, 5])
def test_preview_symbols_match_l2000_workbook_for_every_mass_group(tmp_path, count):
    raw = pd.DataFrame({"Well": [f"A{n}" for n in range(1, count + 1)] + ["B1"],
                        "Plasmid": ["A"] * (count + 1),
                        "Mass (ng)": [n * 100 for n in range(1, count + 1)] + [100]})
    wells, long, _ = standardize_plate_csv(raw)
    html = plate_preview_html(long, wells, reagent="L2000")
    preview = PreviewParser(html)
    result = generate(raw.to_csv(index=False).encode(), "shape-parity.csv",
                      {"Stocks": [["Plasmid", "Concentration"], ["A", "100"]]},
                      "test", "test-time", ["L2000"], default_configs())
    workbook = load_workbook(BytesIO(result["artifacts"][0]["bytes"]))
    try:
        for group in group_dna_masses(long):
            number, symbol = group["Number"], group["Symbol"]
            assert symbol == BULK_MIX_SYMBOLS[number - 1]
            for well in group["Wells"]:
                attrs = preview.wells[well]
                assert attrs["data-mass-group"] == str(number)
                assert f"Bulk transfectant mix {number} ({symbol})" in attrs["aria-label"]
                assert f'Total DNA: {attrs["data-total-dna"]} ng' in attrs["aria-label"]
                cells = [cell for row in workbook["Mix Map"] for cell in row
                         if isinstance(cell.value, str) and cell.value.split()[:1] == [well]]
                assert len(cells) == 1
                assert cells[0].value.splitlines()[-1] == symbol
        assert len(preview.with_class("tmm-well-marker")) == count + 1
        assert len(preview.with_class("tmm-mass-explanation")) == 1
        assert "Each shape matches its bulk transfectant mix" in html
    finally:
        workbook.close()


def test_group_numbers_use_all_wells_and_are_stable_when_input_is_shuffled():
    long = pd.DataFrame({"Well": ["H1", "G1", "A10", "B1", "a02", "B2", "C3", "C1", "C2"],
                         "Plasmid": ["A"] * 9,
                         "Mass_ng": [400, 500, 100, 100, 200, 200, 300, 300, 300]})
    expected = {"C1": "1", "C2": "1", "C3": "1", "A2": "2", "B2": "2", "B1": "3",
                "A10": "3", "G1": "4", "H1": "5"}
    for entries in (long, long.sample(frac=1, random_state=3)):
        html = plate_preview_html(entries, plate_type=96)
        preview = PreviewParser(html)
        actual = {well: attrs["data-mass-group"] for well, attrs in preview.wells.items()
                  if "data-mass-group" in attrs}
        assert actual == expected
        assert "Bulk transfectant mix 3 · 100 ng DNA/well · 2 wells" in html
        assert "Bulk transfectant mix 4 · 500 ng DNA/well · 1 well" in html
        assert "Bulk transfectant mix 5 · 400 ng DNA/well · 1 well" in html


def test_96_mass_groups_span_both_halves_of_the_plate():
    long = pd.DataFrame({"Well": ["A9", "G1", "A1"], "Plasmid": ["A"] * 3,
                         "Mass_ng": [100, 100, 200]})
    html = plate_preview_html(long, plate_type=96)
    preview = PreviewParser(html)
    assert preview.wells["A1"]["data-mass-group"] == "2"
    assert "Bulk transfectant mix 2 (●)" in preview.wells["A1"]["aria-label"]
    assert "Bulk transfectant mix 1 · 100 ng DNA/well · 2 wells" in html
    assert len(preview.with_class("tmm-well-marker")) == 3


@pytest.mark.parametrize("plate_type,rows,columns", [
    (96, "ABCDEFGH", 12), (48, "ABCDEF", 8), (24, "ABCD", 6),
    (12, "ABC", 4), (6, "AB", 3), (1, "A", 1),
])
def test_selected_preview_has_exact_geometry_even_without_data(plate_type, rows, columns):
    html = plate_preview_html(plate_type=plate_type)
    preview = PreviewParser(html)
    assert list(preview.wells) == [f"{row}{col}" for row in rows for col in range(1, columns + 1)]
    assert f"--tmm-columns:{columns};" in html
    if plate_type == 1:
        assert '<span class="tmm-dish-label">A1</span>' in html
        assert preview.wells["A1"]["aria-label"] == "Well A1. No DNA"


def test_preview_cannot_silently_hide_unsupported_positive_dna():
    long = pd.DataFrame({"Well": ["C8"], "Plasmid": ["A"], "Mass_ng": [100]})
    with pytest.raises(ValueError, match="C8.*6-well.*A1–B3"):
        plate_preview_html(long, plate_type=6)


def test_decimal_equal_totals_share_markers_but_close_totals_remain_distinct():
    long = pd.DataFrame({"Well": ["A1", "A1", "A2", "A3", "A4"], "Plasmid": ["A"] * 5,
                         "Mass_ng": ["0.1", "0.2", "0.3", "0.3000001", "0.3000002"]})
    html = plate_preview_html(long)
    preview = PreviewParser(html)
    assert [preview.wells[f"A{n}"]["data-mass-group"] for n in range(1, 5)] == ["1", "1", "2", "3"]
    assert [preview.wells[f"A{n}"]["data-total-dna"] for n in range(1, 5)] == ["0.3", "0.3", "0.3000001", "0.3000002"]
    for mass in ["0.3", "0.3000001", "0.3000002"]:
        assert f"{mass} ng DNA/well" in html


@pytest.mark.parametrize("reagent", ["L2000", "LT1"])
def test_single_mass_empty_and_nonpositive_wells_have_no_markers_or_explanation(reagent):
    long = pd.DataFrame({"Well": ["A1", "A2", "A3", "A4"], "Plasmid": ["A"] * 4,
                         "Mass_ng": [100, 100, 0, float("nan")]})
    for entries in (long, long.iloc[2:], long.iloc[0:0]):
        preview = PreviewParser(plate_preview_html(entries, reagent=reagent))
        assert not preview.with_class("tmm-well-marker")
        assert not preview.with_class("tmm-mass-explanation")
        assert all("data-mass-group" not in attrs for attrs in preview.wells.values())
        assert "tmm-well-empty" in preview.wells["A3"]["class"]
        assert "tabindex" not in preview.wells["A3"]


def test_lt1_uses_same_shapes_with_preview_only_explanation():
    long = pd.DataFrame({"Well": ["A1", "A2"], "Plasmid": ["A"] * 2, "Mass_ng": [100, 200]})
    html = plate_preview_html(long, reagent="LT1")
    preview = PreviewParser(html)
    assert "DNA mass set 1 (▲)" in preview.wells["A1"]["aria-label"]
    assert "DNA mass set 2 (●)" in preview.wells["A2"]["aria-label"]
    assert "These LT1 markers are preview-only and do not appear in the Excel output." in html
    assert "matches its bulk transfectant mix" not in html


@pytest.mark.parametrize("reagent", ["L2000", "LT1"])
def test_more_than_five_groups_use_numbered_circle_badges_for_every_set(reagent):
    long = pd.DataFrame({"Well": [f"A{n}" for n in range(1, 7)], "Plasmid": ["A"] * 6,
                         "Mass_ng": [n * 100 for n in range(1, 7)]})
    html = plate_preview_html(long, reagent=reagent)
    preview = PreviewParser(html)
    assert not preview.with_class("tmm-mass-symbol")
    assert len(preview.with_class("tmm-number-badge")) == 12  # Six wells and six legend entries.
    assert len(preview.with_class("tmm-well-marker")) == 6
    for number in range(1, 7):
        assert f"DNA mass set {number} ({number})" in preview.wells[f"A{number}"]["aria-label"]
    assert "Numbered circle badges identify every set" in html
    assert "L2000 Excel export supports at most five sets per plate." in html
    if reagent == "LT1":
        assert "These LT1 markers are preview-only" in html


def test_repeated_calls_do_not_leak_markers_between_selected_plates():
    mixed = pd.DataFrame({"Well": ["A1", "A2"], "Plasmid": ["A"] * 2, "Mass_ng": [100, 200]})
    single = pd.DataFrame({"Well": ["B1"], "Plasmid": ["A"], "Mass_ng": [300]})
    for entries, expected_count in [(mixed, 2), (single, 0), (None, 0), (mixed, 2)]:
        preview = PreviewParser(plate_preview_html(entries, embedded=True))
        assert len(preview.with_class("tmm-well-marker")) == expected_count
        assert bool(preview.with_class("tmm-mass-explanation")) == bool(expected_count)
