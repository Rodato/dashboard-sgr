import json
import os
import time

import pandas as pd
import requests
import streamlit as st
from sodapy import Socrata

from dashboard_sgr.config import (
    API_MAX_RETRIES,
    API_RETRY_BACKOFF,
    API_ROW_LIMIT,
    CACHE_TTL,
    DATASET_ID,
    DEPT_NAME_MAPPING,
    GEOJSON_LOCAL_PATH,
    GEOJSON_URL,
    SOCRATA_DOMAIN,
)
from dashboard_sgr.utils import aggregate_sgr_data, normalize_color_intensity


@st.cache_data(ttl=CACHE_TTL)
def load_data():
    """Fetch SGR data from Socrata API with pagination and retry logic."""
    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            client = Socrata(SOCRATA_DOMAIN, None)
            all_results = []
            offset = 0

            while True:
                batch = client.get(DATASET_ID, limit=API_ROW_LIMIT, offset=offset)
                if not batch:
                    break
                all_results.extend(batch)
                if len(batch) < API_ROW_LIMIT:
                    break
                offset += API_ROW_LIMIT

            df = pd.DataFrame.from_records(all_results)
            rows_fetched = len(df)

            # Validate expected columns
            expected = {"codigodanedepartamento", "codigodaneentidad",
                        "presupuestosgrinversion", "recursosaprobadosasignadosspgr",
                        "nombrefondo", "nombreentidad", "nombredepartamento"}
            missing = expected - set(df.columns)
            if missing:
                st.warning(f"Columnas faltantes en los datos: {missing}")

            # Process DANE department code
            df["codigodanedepartamento"] = pd.to_numeric(
                df["codigodanedepartamento"], errors="coerce"
            )
            invalid_dept = df["codigodanedepartamento"].isna().sum()
            if invalid_dept > 0:
                st.info(f"{invalid_dept} filas descartadas por codigo departamento invalido.")
            df = df.dropna(subset=["codigodanedepartamento"])
            df["codigodanedepartamento"] = (df["codigodanedepartamento"] / 1000).astype(int)

            # Process DANE entity code
            df["codigodaneentidad"] = pd.to_numeric(
                df["codigodaneentidad"].str.strip(), errors="coerce"
            )
            invalid_ent = df["codigodaneentidad"].isna().sum()
            if invalid_ent > 0:
                st.info(f"{invalid_ent} filas descartadas por codigo entidad invalido.")
            df = df.dropna(subset=["codigodaneentidad"])
            df["codigodaneentidad"] = df["codigodaneentidad"].astype(int)
            df["codigodaneentidad"] = df["codigodaneentidad"].apply(
                lambda x: x // 1000 if x % 1000 == 0 else x
            )

            # Convert monetary columns
            df["presupuestosgrinversion"] = (
                df["presupuestosgrinversion"].str.strip().astype(float)
            )
            df["recursosaprobadosasignadosspgr"] = (
                df["recursosaprobadosasignadosspgr"].str.strip().astype(float)
            )
            df["SALDO_PENDIENTE"] = (
                df["presupuestosgrinversion"] - df["recursosaprobadosasignadosspgr"]
            ).clip(lower=0)

            return df, rows_fetched

        except Exception as e:
            if attempt < API_MAX_RETRIES:
                time.sleep(API_RETRY_BACKOFF * attempt)
            else:
                st.error(f"Error al cargar los datos tras {API_MAX_RETRIES} intentos: {e}")
                return pd.DataFrame(), 0


@st.cache_data
def load_municipios_geo():
    """Load municipality coordinates from divipola.csv."""
    try:
        municipios_df = pd.read_csv("divipola.csv")
        municipios_df["COD_MPIO_CLEAN"] = (
            municipios_df["COD_MPIO"].astype(str).str.replace(",", "").astype(int)
        )
        return municipios_df
    except Exception as e:
        st.warning(f"No se pudo cargar el archivo de municipios: {e}")
        return pd.DataFrame()


@st.cache_data
def load_colombia_geojson():
    """Load Colombia department boundaries GeoJSON (local first, then remote fallback)."""
    # Try local file first
    if os.path.exists(GEOJSON_LOCAL_PATH):
        try:
            with open(GEOJSON_LOCAL_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback to remote URL
    try:
        response = requests.get(GEOJSON_URL, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.warning(f"Error al cargar GeoJSON: {e}")
    return None


def prepare_map_data(df_filtrado, municipios_df):
    """Prepare municipality-level data for the scatter map."""
    if municipios_df.empty:
        return pd.DataFrame(), 0

    try:
        group_cols = ["codigodaneentidad", "nombreentidad", "nombredepartamento"]
        df_agrupado = aggregate_sgr_data(df_filtrado, group_cols)

        map_data = pd.merge(
            df_agrupado,
            municipios_df[["COD_MPIO_CLEAN", "NOM_MPIO", "NOM_DPTO", "LATITUD", "LONGITUD"]],
            left_on="codigodaneentidad",
            right_on="COD_MPIO_CLEAN",
            how="inner",
        )

        unmatched = len(df_agrupado) - len(map_data)

        if len(map_data) > 0:
            intensity = normalize_color_intensity(map_data["presupuestosgrinversion"])
            map_data["color_r"] = intensity
            map_data["color_g"] = 100
            map_data["color_b"] = 255 - intensity
            map_data["color_a"] = 200

            map_data["tooltip"] = map_data.apply(
                lambda row: (
                    f"{row['NOM_MPIO']}\n"
                    f"{row['NOM_DPTO']}\n"
                    f"Presupuesto: ${row['presupuestosgrinversion']:,.0f}\n"
                    f"Fondo: {row['nombrefondo']}\n"
                    f"Proyectos: {int(row['numeroproyectosaprobados']) if pd.notna(row['numeroproyectosaprobados']) else 0}"
                ),
                axis=1,
            )

        return map_data, unmatched

    except Exception as e:
        st.warning(f"Error al preparar datos del mapa: {e}")
        return pd.DataFrame(), 0


def prepare_choropleth_data(df_filtrado):
    """Prepare department-level aggregated data for choropleth map."""
    try:
        dept_data = aggregate_sgr_data(df_filtrado, ["nombredepartamento"])

        dept_data["dept_normalized"] = dept_data["nombredepartamento"].str.upper().str.strip()

        for old_name, new_name in DEPT_NAME_MAPPING.items():
            dept_data.loc[
                dept_data["dept_normalized"] == old_name, "dept_normalized"
            ] = new_name

        return dept_data

    except Exception as e:
        st.warning(f"Error al preparar datos coropleticos: {e}")
        return pd.DataFrame()
