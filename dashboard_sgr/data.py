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
    DATASET_ID_PROYECTOS,
    DEPT_NAME_MAPPING,
    GEOJSON_LOCAL_PATH,
    GEOJSON_URL,
    SOCRATA_DOMAIN,
)
from dashboard_sgr.utils import aggregate_sgr_data, normalize_color_intensity, strip_accents


@st.cache_data(ttl=CACHE_TTL)
def load_data():
    """Fetch SGR data from Socrata API with pagination and retry logic."""
    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            client = Socrata(SOCRATA_DOMAIN, None)
            all_results = []
            offset = 0

            while True:
                batch = client.get(
                    DATASET_ID,
                    limit=API_ROW_LIMIT,
                    offset=offset,
                )
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
            df = df.dropna(subset=["codigodanedepartamento"])
            df["codigodanedepartamento"] = (df["codigodanedepartamento"] / 1000).astype(int)

            # Process DANE entity code
            df["codigodaneentidad"] = pd.to_numeric(
                df["codigodaneentidad"].str.strip(), errors="coerce"
            )
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
    """Prepare municipality-level data for the scatter map.

    Returns (map_data, unmatched_df) — unmatched_df lists entities whose DANE code
    did not match any row in divipola.csv.
    """
    empty_unmatched = pd.DataFrame(
        columns=["codigodaneentidad", "nombreentidad", "nombredepartamento"]
    )
    if municipios_df.empty:
        return pd.DataFrame(), empty_unmatched

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

        matched_codes = set(map_data["codigodaneentidad"].unique())
        unmatched_df = df_agrupado[
            ~df_agrupado["codigodaneentidad"].isin(matched_codes)
        ][group_cols].copy()

        if len(map_data) > 0:
            intensity = normalize_color_intensity(map_data["presupuestosgrinversion"])
            # Blue ramp: light #E8EEF4 (232,238,244) -> dark #083358 (8,51,88)
            t = intensity / 255.0
            map_data["color_r"] = (232 + (8 - 232) * t).astype(int)
            map_data["color_g"] = (238 + (51 - 238) * t).astype(int)
            map_data["color_b"] = (244 + (88 - 244) * t).astype(int)
            map_data["color_a"] = 220

            def _build_tooltip(row):
                presupuesto = row["presupuestosgrinversion"]
                aprobado = row["recursosaprobadosasignadosspgr"]
                saldo = row["SALDO_PENDIENTE"]
                ejecucion = (aprobado / presupuesto * 100) if presupuesto > 0 else 0
                proyectos = (
                    int(row["numeroproyectosaprobados"])
                    if pd.notna(row["numeroproyectosaprobados"]) else 0
                )
                return (
                    f"{row['NOM_MPIO']}\n"
                    f"{row['NOM_DPTO']}\n"
                    f"Presupuesto: ${presupuesto:,.0f}\n"
                    f"Aprobado: ${aprobado:,.0f} ({ejecucion:.1f}%)\n"
                    f"Saldo pendiente: ${saldo:,.0f}\n"
                    f"Fondo: {row['nombrefondo']}\n"
                    f"Proyectos: {proyectos}"
                )

            map_data["tooltip"] = map_data.apply(_build_tooltip, axis=1)

        return map_data, unmatched_df

    except Exception as e:
        st.warning(f"Error al preparar datos del mapa: {e}")
        return pd.DataFrame(), empty_unmatched


def prepare_choropleth_data(df_filtrado):
    """Prepare department-level aggregated data for choropleth map."""
    try:
        dept_data = aggregate_sgr_data(df_filtrado, ["nombredepartamento"])

        dept_data["dept_normalized"] = dept_data["nombredepartamento"].str.upper().str.strip()

        for old_name, new_name in DEPT_NAME_MAPPING.items():
            dept_data.loc[
                dept_data["dept_normalized"] == old_name, "dept_normalized"
            ] = new_name

        dept_data["dept_normalized"] = dept_data["dept_normalized"].map(strip_accents)

        return dept_data

    except Exception as e:
        st.warning(f"Error al preparar datos coropleticos: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL)
def load_proyectos():
    """Fetch DNP-ProyectosSGR (mzgh-shtp) from Socrata with pagination + retry.

    Returns (DataFrame, rows_fetched). Numeric columns are coerced.
    """
    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            client = Socrata(SOCRATA_DOMAIN, None)
            all_results = []
            offset = 0
            while True:
                batch = client.get(
                    DATASET_ID_PROYECTOS, limit=API_ROW_LIMIT, offset=offset,
                )
                if not batch:
                    break
                all_results.extend(batch)
                if len(batch) < API_ROW_LIMIT:
                    break
                offset += API_ROW_LIMIT

            df = pd.DataFrame.from_records(all_results)
            rows_fetched = len(df)

            if df.empty:
                return df, 0

            numeric_cols = ["valortotal", "ejecucionfisica", "ejecucionfinanciera"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            for col in ["sector", "estado", "departamento", "entidadejecutora"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()

            return df, rows_fetched

        except Exception as e:
            if attempt < API_MAX_RETRIES:
                time.sleep(API_RETRY_BACKOFF * attempt)
            else:
                st.error(f"Error al cargar proyectos tras {API_MAX_RETRIES} intentos: {e}")
                return pd.DataFrame(), 0
