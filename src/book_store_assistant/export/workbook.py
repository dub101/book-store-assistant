from openpyxl.styles import Alignment
from openpyxl.worksheet.worksheet import Worksheet


def apply_sheet_basics(
    sheet: Worksheet,
    *,
    freeze_panes: str,
    column_widths: dict[str, int] | None = None,
    wrap_columns: tuple[int, int] | None = None,
) -> None:
    sheet.freeze_panes = freeze_panes
    sheet.auto_filter.ref = sheet.dimensions

    if column_widths:
        for column, width in column_widths.items():
            sheet.column_dimensions[column].width = width

    if wrap_columns is None:
        return

    min_column, max_column = wrap_columns
    for row in sheet.iter_rows(min_row=2, min_col=min_column, max_col=max_column):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
