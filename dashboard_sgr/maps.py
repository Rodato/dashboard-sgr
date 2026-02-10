import pandas as pd
import pydeck as pdk
import streamlit as st

from dashboard_sgr.config import MAP_CENTER_LAT, MAP_CENTER_LON, DEFAULT_ZOOM, MAP_STYLE
from dashboard_sgr.data import prepare_choropleth_data
from dashboard_sgr.utils import normalize_color_intensity


def create_choropleth_map(df_filtrado, geojson_data):
    """Create a department-level choropleth map."""
    if not geojson_data:
        return None

    try:
        dept_data = prepare_choropleth_data(df_filtrado)
        if dept_data.empty:
            return None

        intensity = normalize_color_intensity(dept_data["presupuestosgrinversion"])
        dept_data["color_intensity"] = intensity

        color_dict = {}
        tooltip_dict = {}

        for _, row in dept_data.iterrows():
            dept_name = row["dept_normalized"]
            i = row["color_intensity"]
            color_dict[dept_name] = [i, 50, 255 - i, 200]

            proyectos = int(row["numeroproyectosaprobados"]) if pd.notna(row["numeroproyectosaprobados"]) else 0
            tooltip_dict[dept_name] = (
                f"DEPARTAMENTO: {row['nombredepartamento']}\n"
                f"Presupuesto: ${row['presupuestosgrinversion']:,.0f}\n"
                f"Fondos: {row['nombrefondo']}\n"
                f"Proyectos: {proyectos:,}\n"
                f"Recursos Aprobados: ${row['recursosaprobadosasignadosspgr']:,.0f}"
            )

        for feature in geojson_data["features"]:
            dept_name = feature["properties"].get("NOMBRE_DPT", "").upper().strip()
            if dept_name in color_dict:
                feature["properties"]["fill_color"] = color_dict[dept_name]
                feature["properties"]["tooltip"] = tooltip_dict[dept_name]
            else:
                feature["properties"]["fill_color"] = [200, 200, 200, 100]
                feature["properties"]["tooltip"] = f"{dept_name}\nSin datos disponibles"

        choropleth_layer = pdk.Layer(
            "GeoJsonLayer",
            data=geojson_data,
            get_fill_color="properties.fill_color",
            get_line_color=[80, 80, 80, 200],
            get_line_width=2,
            pickable=True,
            auto_highlight=True,
            opacity=0.8,
        )

        view_state = pdk.ViewState(
            latitude=MAP_CENTER_LAT, longitude=MAP_CENTER_LON,
            zoom=DEFAULT_ZOOM, pitch=0, bearing=0,
        )

        tooltip = {
            "html": (
                "<div style='background: white; color: black; padding: 12px; "
                "border-radius: 8px; border: 1px solid #ccc; "
                "box-shadow: 0 2px 10px rgba(0,0,0,0.1);'>"
                "<b>{tooltip}</b></div>"
            ),
            "style": {
                "fontSize": "13px",
                "fontFamily": "Arial, sans-serif",
                "whiteSpace": "pre-line",
                "maxWidth": "300px",
            },
        }

        deck = pdk.Deck(
            layers=[choropleth_layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style=MAP_STYLE,
        )

        return deck, dept_data

    except Exception as e:
        st.error(f"Error al crear mapa coropletico: {e}")
        return None, pd.DataFrame()


def create_pydeck_map(map_data):
    """Create a scatter plot map at the municipality level."""
    if map_data.empty:
        return None

    center_lat = map_data["LATITUD"].mean()
    center_lon = map_data["LONGITUD"].mean()

    circle_layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_data,
        get_position=["LONGITUD", "LATITUD"],
        get_color=["color_r", "color_g", "color_b", "color_a"],
        get_radius=8000,
        radius_scale=1,
        radius_min_pixels=8,
        radius_max_pixels=50,
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=center_lat, longitude=center_lon,
        zoom=5.5, pitch=0, bearing=0,
    )

    tooltip = {
        "html": "<b>{tooltip}</b>",
        "style": {
            "backgroundColor": "white",
            "color": "black",
            "padding": "10px",
            "border-radius": "5px",
            "font-family": "Arial",
            "font-size": "12px",
            "white-space": "pre-line",
            "border": "1px solid #ccc",
        },
    }

    deck = pdk.Deck(
        layers=[circle_layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style=MAP_STYLE,
    )

    return deck
