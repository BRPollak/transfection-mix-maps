"""Shared physical layouts for supported plates and a single culture dish."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlateFormat:
    well_count: int
    rows: tuple[str, ...]
    columns: tuple[int, ...]

    @property
    def label(self) -> str:
        return "Single well (dish)" if self.well_count == 1 else f"{self.well_count}-well"

    @property
    def well_range(self) -> str:
        return "A1" if self.well_count == 1 else f"A1–{self.rows[-1]}{self.columns[-1]}"

    def contains(self, row: str, column: int) -> bool:
        return row in self.rows and column in self.columns

    @property
    def map_sections(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        if self.well_count == 96:
            return (("Mix Map (A-D)", self.rows[:4]), ("Mix Map (E-H)", self.rows[4:]))
        return (("Mix Map", self.rows),)


PLATE_FORMATS = {
    count: PlateFormat(count, tuple("ABCDEFGH"[:row_count]), tuple(range(1, column_count + 1)))
    for count, row_count, column_count in (
        (96, 8, 12), (48, 6, 8), (24, 4, 6), (12, 3, 4), (6, 2, 3), (1, 1, 1)
    )
}


def get_plate_format(plate_type: int = 48) -> PlateFormat:
    if type(plate_type) is not int or plate_type not in PLATE_FORMATS:
        raise ValueError("Choose a supported plate type: 96, 48, 24, 12, 6, or single well (1).")
    return PLATE_FORMATS[plate_type]
