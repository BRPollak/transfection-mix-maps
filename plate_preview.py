"""A safe, self-contained plate view for Streamlit's ``st.html``."""
from __future__ import annotations

from html import escape
import math

import pandas as pd

from core import group_dna_masses, parse_well
from plate_formats import get_plate_format


_STYLE = """<style>
.tmm-plate-preview {
  width:100%; max-width:660px; box-sizing:border-box;
  margin:12px 0 24px; padding:20px 22px 18px;
  border:1px solid #e3e3e9; border-radius:16px; background:#fafafb;
  color:#373341; font-family:inherit;
}
.tmm-plate-preview * {box-sizing:border-box;}
.tmm-plate-embedded {max-width:none; margin:0; padding:0; border:0; border-radius:0; background:transparent;}
.tmm-plate-heading {font-size:.95rem; font-weight:600; margin:0 0 4px;}
.tmm-plate-caption {font-size:.8rem; color:#686473; margin:0 0 16px; line-height:1.5;}
.tmm-plate-notice {
  font-size:.8rem; line-height:1.5; margin:0 0 16px; padding:9px 12px;
  border-radius:8px; background:#fff2d6; color:#694a12; overflow-wrap:anywhere;
}
.tmm-plate-grid {
  display:grid; grid-template-columns:20px repeat(var(--tmm-columns),minmax(0,1fr));
  max-width:var(--tmm-grid-width); margin-inline:auto;
  gap:12px 10px; align-items:center; justify-items:center;
}
.tmm-plate-axis {font-size:.78rem; font-weight:600; color:#746f7b;}
.tmm-well {
  position:relative; width:100%; max-width:var(--tmm-well-size); aspect-ratio:1;
  border-radius:50%; border:1px solid #dfe0e6;
  background:#ececf0;
}
.tmm-well-empty {pointer-events:none;}
.tmm-dish-label {position:absolute; inset:0; display:grid; place-items:center; font-weight:600;}
.tmm-well-filled {background:#dfd2f0; border-color:#cabbdf; outline:none;}
.tmm-well-filled:hover, .tmm-well-filled:focus {
  border-color:#9271b7; box-shadow:0 0 0 3px #eee6f6; z-index:2;
}
.tmm-well-marker {
  position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
  color:#373341; font-size:1.4rem; line-height:1; pointer-events:none;
}
.tmm-mass-symbol {font-family:Arial,"DejaVu Sans",sans-serif; line-height:1;}
.tmm-number-badge {
  display:inline-flex; align-items:center; justify-content:center;
  min-width:1.6em; height:1.6em; padding:0 .15em;
  border:1px solid currentColor; border-radius:50%; font-size:.7rem; font-weight:600;
}
.tmm-mass-explanation {
  margin:16px 0 0; padding:12px; border:1px solid #dfe0e6; border-radius:8px;
  background:#fff; color:#514b5a; font-size:.78rem; line-height:1.5;
}
.tmm-mass-explanation p {margin:0 0 8px;}
.tmm-mass-legend {list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:5px;}
.tmm-mass-legend li {display:flex; align-items:center; gap:8px;}
.tmm-mass-legend .tmm-mass-symbol {display:inline-flex; justify-content:center; width:1.3rem; flex-shrink:0; font-size:1rem;}
.tmm-mass-legend .tmm-number-badge {flex-shrink:0;}
.tmm-well-tooltip {
  visibility:hidden; opacity:0; position:absolute; z-index:3;
  bottom:calc(100% + 10px); left:50%; transform:translateX(-50%);
  width:max-content; max-width:260px; padding:10px 12px; border-radius:9px;
  background:#39313f; color:#fff; box-shadow:0 4px 16px #25143226;
  font-size:.78rem; line-height:1.5; text-align:left; overflow-wrap:anywhere;
  pointer-events:none;
}
.tmm-well-filled:hover .tmm-well-tooltip,
.tmm-well-filled:focus .tmm-well-tooltip {visibility:visible; opacity:1;}
.tmm-well-left .tmm-well-tooltip {left:0; transform:none;}
.tmm-well-right .tmm-well-tooltip {left:auto; right:0; transform:none;}
.tmm-tooltip-well {display:block; font-weight:700; margin-bottom:3px; color:#e9dcf8;}
.tmm-tooltip-component {display:block;}
.tmm-plate-legend {display:flex; flex-wrap:wrap; gap:16px; margin-top:18px; font-size:.75rem; color:#686473;}
.tmm-plate-legend span {display:inline-flex; align-items:center; gap:6px;}
.tmm-legend-dot {width:10px; height:10px; border-radius:50%; display:inline-block;}
.tmm-legend-dna {background:#dfd2f0; border:1px solid #cabbdf;}
.tmm-legend-empty {background:#ececf0; border:1px solid #dfe0e6;}
@media (max-width:480px) {
  .tmm-plate-preview {padding:16px 12px;}
  .tmm-plate-embedded {padding:0;}
  .tmm-plate-grid {grid-template-columns:15px repeat(var(--tmm-columns),minmax(0,1fr)); gap:10px 6px;}
  .tmm-well-tooltip {max-width:210px;}
  .tmm-well-marker {font-size:var(--tmm-mobile-marker,1.15rem);}
  .tmm-well-marker .tmm-number-badge {font-size:.6rem;}
}
</style>"""


def _mass_text(mass) -> str:
    """Keep distinct decimal mass sets readable without rounding them together."""
    text = format(mass, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _marker_html(symbol: str, numbered: bool) -> str:
    css_class = "tmm-number-badge" if numbered else "tmm-mass-symbol"
    return f'<span class="{css_class}" aria-hidden="true">{escape(symbol)}</span>'


def plate_preview_html(
    long_df: pd.DataFrame | None = None,
    wells_df: pd.DataFrame | None = None,
    *, embedded: bool = False, reagent: str = "L2000", plate_type: int = 48,
) -> str:
    """Return the selected full grid using ``standardize_plate_csv`` frames.

    Call without data for the initial empty preview. Positive masses populate
    wells; repeated plasmid entries at the same physical well are summed.
    Empty template wells outside the selected geometry are ignored.
    Use ``embedded=True`` inside the app's card with its preview selector.
    Multiple DNA totals get the same group markers as the L2000 workbook;
    ``reagent`` selects the explanation, since LT1 exports do not use them.
    """
    plate_format = get_plate_format(plate_type)
    components: dict[tuple[str, int], dict[str, float]] = {}
    if long_df is not None:
        for record in long_df.to_dict("records"):
            position = parse_well(record["Well"])
            mass = float(record["Mass_ng"])
            if not math.isfinite(mass) or mass <= 0:
                continue
            if not plate_format.contains(*position):
                raise ValueError(f"Well {record['Well']} contains DNA outside the selected "
                                 f"{plate_format.label} layout ({plate_format.well_range}).")
            name = str(record["Plasmid"])
            amounts = components.setdefault(position, {})
            amounts[name] = amounts.get(name, 0) + mass

    groups = group_dna_masses(long_df)
    show_markers = len(groups) > 1
    numbered = len(groups) > 5
    group_label = "Bulk transfectant mix" if reagent == "L2000" and not numbered else "DNA mass set"
    well_groups = {
        parse_well(well): group
        for group in groups for well in group["Wells"]
    } if show_markers else {}

    caption = ("Choose a plate CSV to populate this preview." if long_df is None else
               "Hover over or focus a purple well to see its plasmids and DNA masses.")
    classes = "tmm-plate-preview tmm-plate-embedded" if embedded else "tmm-plate-preview"
    heading = ("Single well (dish) preview" if plate_type == 1 else f"{plate_format.label} plate preview")
    well_size = min(140, max(36, round(368 / len(plate_format.columns))))
    grid_width = min(616, 24 + len(plate_format.columns) * (well_size + 10))
    style = (f"--tmm-columns:{len(plate_format.columns)};--tmm-well-size:{well_size}px;"
             f"--tmm-grid-width:{grid_width}px;--tmm-mobile-marker:{'.85rem' if plate_type == 96 else '1.15rem'}")
    parts = [_STYLE, f'<section class="{classes}" aria-label="{heading}" style="{style}">']
    if not embedded:
        parts.append(f'<p class="tmm-plate-heading">{heading}</p>')
    parts.append(f'<p class="tmm-plate-caption">{caption}</p>')
    parts.append('<div class="tmm-plate-grid"><span aria-hidden="true"></span>')
    for col in plate_format.columns:
        parts.append(f'<span class="tmm-plate-axis" aria-hidden="true">{col}</span>')
    for row in plate_format.rows:
        parts.append(f'<span class="tmm-plate-axis" aria-hidden="true">{row}</span>')
        for col in plate_format.columns:
            well = f"{row}{col}"
            amounts = components.get((row, col))
            if not amounts:
                dish_label = '<span class="tmm-dish-label">A1</span>' if plate_type == 1 else ""
                attributes = 'role="img" aria-label="Well A1. No DNA"' if plate_type == 1 else 'aria-hidden="true"'
                parts.append(f'<div class="tmm-well tmm-well-empty" data-well="{well}" {attributes}>{dish_label}</div>')
                continue
            edge = ("" if plate_type == 1 else " tmm-well-left" if col <= len(plate_format.columns) / 3
                    else " tmm-well-right" if col > len(plate_format.columns) * 2 / 3 else "")
            entries = [f"{name}: {mass:.12g} ng" for name, mass in amounts.items()]
            group = well_groups.get((row, col))
            marker_attributes = ""
            if group:
                total = _mass_text(group["Total DNA_ng"])
                entries.extend([f"Total DNA: {total} ng", f'{group_label} {group["Number"]} ({group["Symbol"]})'])
                marker_attributes = f' data-mass-group="{group["Number"]}" data-total-dna="{total}"'
            accessible_text = escape(f"Well {well}. " + "; ".join(entries), quote=True)
            parts.append(f'<div class="tmm-well tmm-well-filled{edge}" data-well="{well}" '
                         f'tabindex="0" role="img" aria-label="{accessible_text}"{marker_attributes}>')
            if plate_type == 1:
                parts.append('<span class="tmm-dish-label" aria-hidden="true">A1</span>')
            if group:
                parts.append('<span class="tmm-well-marker" aria-hidden="true">'
                             + _marker_html(group["Symbol"], numbered) + '</span>')
            parts.append(f'<span class="tmm-well-tooltip" aria-hidden="true"><span class="tmm-tooltip-well">{well}</span>')
            parts.extend(f'<span class="tmm-tooltip-component">{escape(entry)}</span>' for entry in entries)
            parts.append('</span></div>')
    parts.append('</div><div class="tmm-plate-legend" aria-hidden="true">'
                 '<span><i class="tmm-legend-dot tmm-legend-dna"></i>DNA present</span>'
                 '<span><i class="tmm-legend-dot tmm-legend-empty"></i>No DNA</span>'
                 '</div>')
    if show_markers:
        if numbered:
            explanation = (f"This plate contains {len(groups)} total DNA mass sets. Numbered circle badges identify "
                           "every set because there are more than five. L2000 Excel export supports at most five sets per plate.")
            if reagent == "LT1":
                explanation += " These LT1 markers are preview-only and do not appear in the Excel output."
        elif reagent == "LT1":
            explanation = ("Shapes identify different total DNA masses per well on this plate. "
                           "These LT1 markers are preview-only and do not appear in the Excel output.")
        else:
            explanation = ("Shapes identify different total DNA masses per well on this plate. "
                           "Each shape matches its bulk transfectant mix and preparation recipe in the L2000 Excel output.")
        parts.append('<aside class="tmm-mass-explanation" role="note" aria-label="DNA mass groups">'
                     f'<p>{explanation}</p><ul class="tmm-mass-legend">')
        for group in groups:
            well_count = len(group["Wells"])
            description = (f'{group_label} {group["Number"]} · {_mass_text(group["Total DNA_ng"])} ng DNA/well'
                           f' · {well_count} {"well" if well_count == 1 else "wells"}')
            parts.append(f'<li>{_marker_html(group["Symbol"], numbered)}<span>{description}</span></li>')
        parts.append('</ul></aside>')
    parts.append('</section>')
    return "".join(parts)
