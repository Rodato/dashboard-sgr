"""Cross-dataset analytics: join asignaciones (budget) with proyectos (delivery)
and surface oversight red-flags.

These functions take the already-loaded DataFrames and return tidy frames the
charts/tab consume. All department grouping uses the normalized key (`k`) from
`norm_dept` so the two differently-spelled sources reconcile.
"""

import pandas as pd

from dashboard_sgr.config import (
    ESTADO_DESAPROBADO,
    ESTADO_EN_EJECUCION,
    NON_TERRITORIAL,
)
from dashboard_sgr.utils import norm_dept


def _territorial(series):
    """Boolean mask: keep rows whose normalized dept is a real department."""
    k = series.map(norm_dept)
    return k, k.notna() & ~k.isin(NON_TERRITORIAL)


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
    a["k"], mask_a = _territorial(a["nombredepartamento"])
    a = a[mask_a]
    asig_g = (
        a.groupby("k")
        .agg(
            presupuesto=("presupuestosgrinversion", "sum"),
            aprobado=("recursosaprobadosasignadosspgr", "sum"),
        )
        .reset_index()
    )

    p = df_proy.copy()
    p["k"], mask_p = _territorial(p["departamento"])
    p = p[mask_p]

    proy_g = (
        p.groupby("k")
        .agg(n_proy=("codigobpin", "count"), valor=("valortotal", "sum"))
    )

    activos = p[p["estado"] == ESTADO_EN_EJECUCION]
    act_g = activos.groupby("k").agg(
        n_activos=("codigobpin", "count"),
        valor_activos=("valortotal", "sum"),
        ejec_fis=("ejecucionfisica", "mean"),
        ejec_fin=("ejecucionfinanciera", "mean"),
    )

    desap = p[p["estado"] == ESTADO_DESAPROBADO]
    desap_g = desap.groupby("k").agg(n_desaprobados=("codigobpin", "count"))

    proy_g = proy_g.join(act_g).join(desap_g).reset_index()

    j = asig_g.merge(proy_g, on="k", how="left").rename(columns={"k": "depto"})
    fill0 = ["n_proy", "valor", "n_activos", "valor_activos", "n_desaprobados"]
    for c in fill0:
        if c in j.columns:
            j[c] = j[c].fillna(0)
    return j.sort_values("presupuesto", ascending=False).reset_index(drop=True)


def national_execution(df_proy):
    """National average physical/financial execution over EN EJECUCIÓN projects."""
    activos = df_proy[df_proy["estado"] == ESTADO_EN_EJECUCION]
    if activos.empty:
        return 0.0, 0.0
    return (
        float(activos["ejecucionfisica"].mean()),
        float(activos["ejecucionfinanciera"].mean()),
    )


def paying_ahead(df_proy, gap_pp=20):
    """Projects EN EJECUCIÓN where financial execution outpaces physical by
    more than `gap_pp` percentage points — money out, work not on the ground.

    Returns the offending rows sorted by `valortotal` desc, with a `gap` column.
    """
    p = df_proy[df_proy["estado"] == ESTADO_EN_EJECUCION].copy()
    p = p.dropna(subset=["ejecucionfisica", "ejecucionfinanciera"])
    p["gap"] = p["ejecucionfinanciera"] - p["ejecucionfisica"]
    out = p[p["gap"] > gap_pp].sort_values("valortotal", ascending=False)
    return out


def zombies(df_proy, before_year=2020):
    """Projects still EN EJECUCIÓN whose BPIN year predates `before_year`."""
    p = add_bpin_year(df_proy[df_proy["estado"] == ESTADO_EN_EJECUCION].copy())
    return p[p["bpin_year"] < before_year].copy()


def zombies_by_year(df_proy, before_year=2020):
    """Count + value of zombie (stalled EN EJECUCIÓN) projects per BPIN year."""
    z = zombies(df_proy, before_year)
    if z.empty:
        return pd.DataFrame(columns=["bpin_year", "n", "valor"])
    g = (
        z.groupby("bpin_year")
        .agg(n=("codigobpin", "count"), valor=("valortotal", "sum"))
        .reset_index()
        .sort_values("bpin_year")
    )
    return g


def desaprobado_by_dept(df_proy, top_n=10):
    """Top departments by DESAPROBADO project value (formulation/approval failures)."""
    p = df_proy[df_proy["estado"] == ESTADO_DESAPROBADO].copy()
    p["k"], mask = _territorial(p["departamento"])
    p = p[mask]
    if p.empty:
        return pd.DataFrame(columns=["depto", "n", "valor"])
    g = (
        p.groupby("k")
        .agg(n=("codigobpin", "count"), valor=("valortotal", "sum"))
        .reset_index()
        .rename(columns={"k": "depto"})
        .sort_values("valor", ascending=False)
        .head(top_n)
    )
    return g
