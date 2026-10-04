"""A safe, self-contained 48-well plate view for Streamlit's ``st.html``."""
from __future__ import annotations

from html import escape
import math

import pandas as pd

from core import parse_well, row_sort_key


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
  display:grid; grid-template-columns:20px repeat(8,minmax(0,1fr));
  gap:12px 10px; align-items:center; justify-items:center;
}
.tmm-plate-axis {font-size:.78rem; font-weight:600; color:#746f7b;}
.tmm-well {
  position:relative; width:100%; max-width:46px; aspect-ratio:1;
  border-radius:50%; border:1px solid #dfe0e6;
  background:#ececf0;
}
.tmm-well-empty {pointer-events:none;}
.tmm-well-filled {background:#dfd2f0; border-color:#cabbdf; outline:none;}
.tmm-well-filled:hover, .tmm-well-filled:focus {
  border-color:#9271b7; box-shadow:0 0 0 3px #eee6f6; z-index:2;
}
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
  .tmm-plate-grid {grid-template-columns:15px repeat(8,minmax(0,1fr)); gap:10px 6px;}
  .tmm-well-tooltip {max-width:210px;}
}
</style>"""


def plate_preview_html(
    long_df: pd.DataFrame | None = None,
    wells_df: pd.DataFrame | None = None,
    *, embedded: bool = False,
) -> str:
    """Return an A1–F8 grid, using the frames from ``standardize_plate_csv``.

    Call without data for the initial empty preview. Positive masses populate
    wells; repeated plasmid entries at the same physical well are summed. Pass
    ``wells_df`` too so any empty wells outside A1–F8 appear in the notice.
    This fixed view does not change which wells may be used for calculations.
    Use ``embedded=True`` inside the app's card with its preview selector.
    """
    components: dict[tuple[str, int], dict[str, float]] = {}
    observed: set[tuple[str, int]] = set()
    if wells_df is not None:
        observed.update(parse_well(well) for well in wells_df["Well"])
    if long_df is not None:
        for record in long_df.to_dict("records"):
            position = parse_well(record["Well"])
            observed.add(position)
            mass = float(record["Mass_ng"])
            if not math.isfinite(mass) or mass <= 0:
                continue
            name = str(record["Plasmid"])
            amounts = components.setdefault(position, {})
            amounts[name] = amounts.get(name, 0) + mass

    outside = sorted(
        (position for position in observed if position[0] not in tuple("ABCDEF") or not 1 <= position[1] <= 8),
        key=lambda position: (row_sort_key(position[0]), position[1]),
    )
    caption = ("Choose a plate CSV to populate this preview." if long_df is None else
               "Hover over a purple well to see its plasmids and DNA masses.")
    classes = "tmm-plate-preview tmm-plate-embedded" if embedded else "tmm-plate-preview"
    parts = [_STYLE, f'<section class="{classes}" aria-label="48-well plate preview">']
    if not embedded:
        parts.append('<p class="tmm-plate-heading">48-well plate preview</p>')
    parts.append(f'<p class="tmm-plate-caption">{caption}</p>')
    if outside:
        names = ", ".join(f"{row}{col}" for row, col in outside)
        parts.append('<p class="tmm-plate-notice" role="note">This preview shows A1–F8 only. '
                     f'Wells outside this view: {escape(names)}. They remain in your plate layout.</p>')

    parts.append('<div class="tmm-plate-grid"><span aria-hidden="true"></span>')
    for col in range(1, 9):
        parts.append(f'<span class="tmm-plate-axis" aria-hidden="true">{col}</span>')
    for row in "ABCDEF":
        parts.append(f'<span class="tmm-plate-axis" aria-hidden="true">{row}</span>')
        for col in range(1, 9):
            well = f"{row}{col}"
            amounts = components.get((row, col))
            if not amounts:
                parts.append(f'<div class="tmm-well tmm-well-empty" data-well="{well}" aria-hidden="true"></div>')
                continue
            edge = " tmm-well-left" if col <= 3 else " tmm-well-right" if col >= 6 else ""
            entries = [f"{name}: {mass:.12g} ng" for name, mass in amounts.items()]
            accessible_text = escape(f"Well {well}. " + "; ".join(entries), quote=True)
            parts.append(f'<div class="tmm-well tmm-well-filled{edge}" data-well="{well}" '
                         f'tabindex="0" role="img" aria-label="{accessible_text}">')
            parts.append(f'<span class="tmm-well-tooltip" aria-hidden="true"><span class="tmm-tooltip-well">{well}</span>')
            parts.extend(f'<span class="tmm-tooltip-component">{escape(entry)}</span>' for entry in entries)
            parts.append('</span></div>')
    parts.append('</div><div class="tmm-plate-legend" aria-hidden="true">'
                 '<span><i class="tmm-legend-dot tmm-legend-dna"></i>DNA present</span>'
                 '<span><i class="tmm-legend-dot tmm-legend-empty"></i>No DNA</span>'
                 '</div></section>')
    return "".join(parts)
