from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

from core import standardize_plate_csv
from plate_preview import plate_preview_html


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


def test_initial_preview_has_all_48_wells_without_interactions():
    preview = PreviewParser(plate_preview_html())
    assert list(preview.wells) == [f"{row}{col}" for row in "ABCDEF" for col in range(1, 9)]
    for attrs in preview.wells.values():
        assert "tmm-well-empty" in attrs["class"]
        assert "tabindex" not in attrs
        assert "title" not in attrs
        assert "aria-label" not in attrs
    assert not any(attrs.get("class") == "tmm-well-tooltip" for _, attrs in preview.elements)


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


def test_outside_wells_are_explicitly_reported_including_empty_wells():
    long = pd.DataFrame({"Well": ["G1", "A9", "A1"], "Plasmid": ["A", "B", "C"], "Mass_ng": [1, 2, 3]})
    wells = pd.DataFrame({"Well": ["G1", "A9", "A1", "AA1", "AB1", "H12"]})
    html = plate_preview_html(long, wells)
    preview = PreviewParser(html)
    assert "This preview shows A1–F8 only." in html
    assert "Wells outside this view: A9, G1, H12, AA1, AB1." in html
    assert len(preview.wells) == 48
    assert "tmm-well-filled" in preview.wells["A1"]["class"]
