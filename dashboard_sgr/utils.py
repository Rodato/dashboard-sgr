import io

import pandas as pd


def normalize_color_intensity(series):
    """Normalize a numeric series to 0-255 range for color mapping."""
    min_val = series.min()
    max_val = series.max()
    if max_val > min_val:
        return ((series - min_val) / (max_val - min_val) * 255).astype(int)
    return pd.Series(128, index=series.index)


def format_currency(value):
    """Format a number as abbreviated currency: $1.5M, $2.3B, etc."""
    if pd.isna(value) or value == 0:
        return "$0"
    abs_val = abs(value)
    sign = "" if value >= 0 else "-"
    if abs_val >= 1_000_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000_000:.1f}T"
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val / 1_000:.1f}K"
    return f"{sign}${abs_val:,.0f}"


def aggregate_sgr_data(df, group_cols):
    """Aggregate SGR data by given columns with standard monetary sums."""
    return df.groupby(group_cols).agg({
        "presupuestosgrinversion": "sum",
        "recursosaprobadosasignadosspgr": "sum",
        "SALDO_PENDIENTE": "sum",
        "numeroproyectosaprobados": lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum(),
        "nombrefondo": lambda x: ", ".join(x.unique()),
    }).reset_index()


def convert_df_to_excel(df):
    """Convert a DataFrame to Excel bytes for download."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos_SGR", float_format="%.2f")
    return output.getvalue()
