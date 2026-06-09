"""Cross-dataset analytics: join asignaciones (budget) with proyectos (delivery)
and surface oversight red-flags.

Grain note: the proyectos dataset is at (project x department x OCAD) grain — a
project that spans N departments is repeated N times, each carrying the *full*
``valortotal``. ``load_proyectos`` already collapses the pure multi-OCAD
duplicates (same project+department) so within a department a BPIN is unique.
Project-level metrics (audit counts/value, the national benchmark) therefore
de-duplicate by ``codigobpin`` so a multi-department project counts once; the
per-department aggregates keep one row per department by design (a project that
operates in several territories is shown in each).
"""

import pandas as pd

from dashboard_sgr.config import (
    ESTADO_DESAPROBADO,
    ESTADO_EN_EJECUCION,
    NON_TERRITORIAL,
)
from dashboard_sgr.utils import norm_dept


def territorialize(df, col="departamento"):
    """Keep only rows whose department maps to a real (territorial) department,
    dropping NULL and non-territorial buckets (OTROS / corporaciones / etc.)."""
    k = df[col].map(norm_dept)
    return df[k.notna() & ~k.isin(NON_TERRITORIAL)]


def add_bpin_year(df):
    """Add a numeric `bpin_year` column parsed from the first 4 chars of BPIN."""
    if "codigobpin" not in df.columns:
        df["bpin_year"] = pd.NA
        return df
    df = df.copy()
    df["bpin_year"] = pd.to_numeric(
        df["codigobpin"].astype(str).str[:4], errors="coerce"
    ).astype("Int64")
    return df


def territorio_join(df_asig, df_proy):
    """Department-level join of budget (asignaciones) vs delivery (proyectos).

    Returns a DataFrame, one row per department, with:
      depto, presupuesto, aprobado (asignaciones 2025-26),
      n_proy, valor (full portfolio), n_activos, valor_activos,
      ejec_fis, ejec_fin (averages over EN EJECUCIÓN projects),
      n_desaprobados.
    Only departments present in the asignaciones (budget) side are kept.
    """
    a = df_asig.copy()
    a["k"] = a["nombredepartamento"].map(norm_dept)
    a = a[a["k"].notna() & ~a["k"].isin(NON_TERRITORIAL)]
    asig_g = (
        a.groupby("k")
        .agg(
            presupuesto=("presupuestosgrinversion", "sum"),
            aprobado=("recursosaprobadosasignadosspgr", "sum"),
        )
        .reset_index()
    )

    p = df_proy.copy()
    p["k"] = p["departamento"].map(norm_dept)
    p = p[p["k"].notna() & ~p["k"].isin(NON_TERRITORIAL)]

    proy_g = (
        p.groupby("k")
        .agg(n_proy=("codigobpin", "nunique"), valor=("valortotal", "sum"))
    )

    activos = p[p["estado"] == ESTADO_EN_EJECUCION]
    act_g = activos.groupby("k").agg(
        n_activos=("codigobpin", "nunique"),
        valor_activos=("valortotal", "sum"),
        ejec_fis=("ejecucionfisica", "mean"),
        ejec_fin=("ejecucionfinanciera", "mean"),
    )

    desap = p[p["estado"] == ESTADO_DESAPROBADO]
    desap_g = desap.groupby("k").agg(n_desaprobados=("codigobpin", "nunique"))

    proy_g = proy_g.join(act_g).join(desap_g).reset_index()

    j = asig_g.merge(proy_g, on="k", how="left").rename(columns={"k": "depto"})
    # Lock the dtype contract: counts are ints (0 when a left-join miss), money
    # is float; execution rates stay NaN where there are no active projects.
    for c in ["n_proy", "n_activos", "n_desaprobados"]:
        if c in j.columns:
            j[c] = j[c].fillna(0).astype("int64")
    for c in ["valor", "valor_activos"]:
        if c in j.columns:
            j[c] = j[c].fillna(0)
    return j.sort_values("presupuesto", ascending=False).reset_index(drop=True)


def national_execution(df_proy):
    """National average physical/financial execution over EN EJECUCIÓN projects.

    Restricted to territorialized projects and de-duplicated to project grain so
    it is a fair, fixed reference for the per-department values. NaN-safe.
    """
    p = df_proy[df_proy["estado"] == ESTADO_EN_EJECUCION]
    p = territorialize(p).drop_duplicates("codigobpin")
    if p.empty:
        return 0.0, 0.0
    fis = p["ejecucionfisica"].mean()
    fin = p["ejecucionfinanciera"].mean()
    return (0.0 if pd.isna(fis) else float(fis), 0.0 if pd.isna(fin) else float(fin))


def paying_ahead(df_proy, gap_pp=20):
    """Projects EN EJECUCIÓN where financial execution outpaces physical by
    more than `gap_pp` percentage points — money out, work not on the ground.

    De-duplicated to project grain; returns offending rows sorted by `valortotal`
    desc, with a `gap` column.
    """
    p = df_proy[df_proy["estado"] == ESTADO_EN_EJECUCION].copy()
    p = p.dropna(subset=["ejecucionfisica", "ejecucionfinanciera"])
    p = p.drop_duplicates("codigobpin")
    p["gap"] = p["ejecucionfinanciera"] - p["ejecucionfisica"]
    return p[p["gap"] > gap_pp].sort_values("valortotal", ascending=False)


def zombies(df_proy, before_year=2020):
    """Projects still EN EJECUCIÓN whose BPIN year predates `before_year`
    (de-duplicated to project grain)."""
    p = add_bpin_year(df_proy[df_proy["estado"] == ESTADO_EN_EJECUCION].copy())
    p = p.drop_duplicates("codigobpin")
    mask = (p["bpin_year"] < before_year).fillna(False)
    return p[mask].copy()


def zombies_by_year(df_proy, before_year=2020, z=None):
    """Count + value of zombie (stalled EN EJECUCIÓN) projects per BPIN year.

    Accepts a precomputed zombie frame `z` to avoid recomputing it."""
    z = zombies(df_proy, before_year) if z is None else z
    if z.empty:
        return pd.DataFrame(columns=["bpin_year", "n", "valor"])
    return (
        z.groupby("bpin_year")
        .agg(n=("codigobpin", "nunique"), valor=("valortotal", "sum"))
        .reset_index()
        .sort_values("bpin_year")
    )


def desaprobado_by_dept(df_proy, top_n=10):
    """Top departments by DESAPROBADO project value (formulation/approval failures)."""
    p = territorialize(df_proy[df_proy["estado"] == ESTADO_DESAPROBADO].copy())
    if p.empty:
        return pd.DataFrame(columns=["depto", "n", "valor"])
    p["k"] = p["departamento"].map(norm_dept)
    return (
        p.groupby("k")
        .agg(n=("codigobpin", "nunique"), valor=("valortotal", "sum"))
        .reset_index()
        .rename(columns={"k": "depto"})
        .sort_values("valor", ascending=False)
        .head(top_n)
    )
