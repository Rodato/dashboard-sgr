import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard_sgr.theme import CHART_SCALE_BLUE, CHART_SCALE_WARM, CHART_SEQUENCE, PALETTE
from dashboard_sgr.utils import aggregate_sgr_data, format_currency


LAYOUT_DEFAULTS = {
    "font": {"family": "Inter, -apple-system, sans-serif", "color": PALETTE["text"], "size": 12},
    "plot_bgcolor": "rgba(0,0,0,0)",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "margin": {"t": 20, "l": 20, "r": 20, "b": 40},
    "colorway": CHART_SEQUENCE,
    "xaxis": {"gridcolor": PALETTE["border"], "zerolinecolor": PALETTE["border"]},
    "yaxis": {"gridcolor": PALETTE["border"], "zerolinecolor": PALETTE["border"]},
    "legend": {"bgcolor": "rgba(0,0,0,0)", "bordercolor": "rgba(0,0,0,0)"},
}


def _currency_ticks(max_val):
    """Return (tickvals, ticktext) for a currency axis 0..max_val.

    Picks a round base (1B, 10B, 100B, 1T, 10T) so labels are clean.
    """
    if max_val <= 0:
        return [0], ["$0"]
    bases = [
        (1_000_000_000, "B"),
        (1_000_000_000_000, "T"),
    ]
    # Step so we get roughly 5 ticks
    target_step = max_val / 5
    step_magnitudes = [1e8, 5e8, 1e9, 5e9, 1e10, 5e10, 1e11, 5e11, 1e12, 5e12]
    step = next((s for s in step_magnitudes if s >= target_step), step_magnitudes[-1])
    tickvals = []
    v = 0
    while v <= max_val * 1.05:
        tickvals.append(v)
        v += step
    ticktext = []
    for v in tickvals:
        if v == 0:
            ticktext.append("0")
        elif v >= 1_000_000_000_000:
            ticktext.append(f"${v / 1_000_000_000_000:.1f}T".replace(".0T", "T"))
        elif v >= 1_000_000_000:
            ticktext.append(f"${v / 1_000_000_000:.0f}B")
        elif v >= 1_000_000:
            ticktext.append(f"${v / 1_000_000:.0f}M")
        else:
            ticktext.append(f"${v:,.0f}")
    return tickvals, ticktext


def _apply_theme(fig, **overrides):
    fig.update_layout(**{**LAYOUT_DEFAULTS, **overrides})
    return fig


def create_fondo_comparison_chart(df_filtrado, fondos_interes):
    try:
        chart_data = []
        for fondo in fondos_interes:
            datos_fondo = df_filtrado[df_filtrado["nombrefondo"] == fondo]
            if len(datos_fondo) > 0:
                chart_data.append({
                    "Fondo": fondo.replace("ASIGNACION PARA LA INVERSION LOCAL", "INVERSION LOCAL"),
                    "Presupuesto": datos_fondo["presupuestosgrinversion"].sum(),
                    "Recursos Aprobados": datos_fondo["recursosaprobadosasignadosspgr"].sum(),
                    "Saldo Pendiente": datos_fondo["SALDO_PENDIENTE"].sum(),
                })

        if not chart_data:
            return None

        df_chart = pd.DataFrame(chart_data)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Presupuesto", x=df_chart["Fondo"], y=df_chart["Presupuesto"],
            marker_color=PALETTE["primary"],
            text=df_chart["Presupuesto"].apply(format_currency),
            textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name="Recursos Aprobados", x=df_chart["Fondo"], y=df_chart["Recursos Aprobados"],
            marker_color=PALETTE["secondary"],
            text=df_chart["Recursos Aprobados"].apply(format_currency),
            textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name="Saldo Pendiente", x=df_chart["Fondo"], y=df_chart["Saldo Pendiente"],
            marker_color=PALETTE["accent"],
            text=df_chart["Saldo Pendiente"].apply(format_currency),
            textposition="outside",
        ))
        return _apply_theme(
            fig,
            barmode="group",
            height=440,
            yaxis={"title": "", "gridcolor": PALETTE["border"], "tickformat": "~s"},
            xaxis={"title": "", "gridcolor": PALETTE["border"]},
            hovermode="x unified",
        )

    except Exception as e:
        st.error(f"Error al crear grafico por fondo: {e}")
        return None


def create_departamento_distribution_chart(df_filtrado, top_n=10):
    try:
        dept_data = aggregate_sgr_data(df_filtrado, ["nombredepartamento"])
        dept_data = dept_data.nlargest(top_n, "presupuestosgrinversion")

        if dept_data.empty:
            return None

        fig = px.bar(
            dept_data,
            x="presupuestosgrinversion",
            y="nombredepartamento",
            orientation="h",
            labels={"presupuestosgrinversion": "Presupuesto", "nombredepartamento": ""},
            color="presupuestosgrinversion",
            color_continuous_scale=CHART_SCALE_BLUE,
        )
        fig.update_traces(
            texttemplate="%{x:$,.2s}", textposition="outside",
            hovertemplate="<b>%{y}</b><br>Presupuesto: $%{x:,.0f}<extra></extra>",
        )
        return _apply_theme(
            fig,
            height=520,
            showlegend=False,
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending", "gridcolor": PALETTE["border"]},
            xaxis={"tickformat": "~s", "gridcolor": PALETTE["border"]},
        )

    except Exception as e:
        st.error(f"Error al crear grafico por departamento: {e}")
        return None


def create_fondo_pie_chart(df_filtrado, fondos_interes):
    try:
        pie_data = []
        for fondo in fondos_interes:
            datos_fondo = df_filtrado[df_filtrado["nombrefondo"] == fondo]
            if len(datos_fondo) > 0:
                pie_data.append({
                    "Fondo": fondo.replace("ASIGNACION PARA LA INVERSION LOCAL", "INVERSION LOCAL"),
                    "Presupuesto": datos_fondo["presupuestosgrinversion"].sum(),
                })

        if not pie_data:
            return None

        df_pie = pd.DataFrame(pie_data)
        total_presupuesto = df_pie["Presupuesto"].sum()
        fig = go.Figure(go.Pie(
            labels=df_pie["Fondo"],
            values=df_pie["Presupuesto"],
            hole=0.55,
            marker={"colors": CHART_SEQUENCE, "line": {"color": "#FFFFFF", "width": 2}},
            textposition="outside",
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Presupuesto: $%{value:,.0f}<br>%{percent}<extra></extra>",
        ))
        return _apply_theme(
            fig,
            height=440,
            showlegend=False,
            annotations=[{
                "text": f"<span style='font-size:12px;color:{PALETTE['text_muted']}'>Total</span><br>"
                        f"<span style='font-size:20px;color:{PALETTE['primary_dark']};font-weight:700'>"
                        f"{format_currency(total_presupuesto)}</span>",
                "x": 0.5, "y": 0.5, "showarrow": False,
            }],
        )

    except Exception as e:
        st.error(f"Error al crear grafico de pastel: {e}")
        return None


def create_kpi_metrics(df_filtrado):
    try:
        total_presupuesto = df_filtrado["presupuestosgrinversion"].sum()
        total_aprobado = df_filtrado["recursosaprobadosasignadosspgr"].sum()
        porcentaje = (total_aprobado / total_presupuesto * 100) if total_presupuesto > 0 else 0

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=porcentaje,
            number={"suffix": "%", "font": {"size": 34, "color": PALETTE["primary_dark"]}},
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Recursos aprobados vs presupuesto",
                   "font": {"size": 13, "color": PALETTE["text_muted"]}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": PALETTE["border"]},
                "bar": {"color": PALETTE["primary"], "thickness": 0.25},
                "bgcolor": PALETTE["surface_muted"],
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 60], "color": "#FEE2E2"},
                    {"range": [60, 80], "color": "#FEF3C7"},
                    {"range": [80, 100], "color": "#D1FAE5"},
                ],
                "threshold": {
                    "line": {"color": PALETTE["primary_dark"], "width": 3},
                    "thickness": 0.85,
                    "value": 80,
                },
            },
        ))
        return _apply_theme(fig, height=300), porcentaje

    except Exception as e:
        st.error(f"Error al crear metricas KPI: {e}")
        return None, 0


def _build_hierarchy_records(df_filtrado):
    tree_data = df_filtrado.groupby(
        ["nombrefondo", "nombredepartamento", "nombreentidad"], dropna=False
    ).agg({"presupuestosgrinversion": "sum"}).reset_index()

    if tree_data.empty:
        return None

    tree_data["fondo_short"] = tree_data["nombrefondo"].str.replace(
        "ASIGNACION PARA LA INVERSION LOCAL", "INVERSION LOCAL"
    )

    ids, labels, parents, values = [], [], [], []
    for fondo, grupo in tree_data.groupby("fondo_short", dropna=False):
        fondo_id = f"F::{fondo}"
        ids.append(fondo_id); labels.append(fondo); parents.append("")
        values.append(float(grupo["presupuestosgrinversion"].sum()))

        for depto, dep_grupo in grupo.groupby("nombredepartamento", dropna=False):
            depto_label = depto if pd.notna(depto) else "(sin depto)"
            depto_id = f"{fondo_id}||D::{depto_label}"
            ids.append(depto_id); labels.append(depto_label); parents.append(fondo_id)
            values.append(float(dep_grupo["presupuestosgrinversion"].sum()))

            for _, row in dep_grupo.iterrows():
                ent_label = row["nombreentidad"] if pd.notna(row["nombreentidad"]) else "(sin entidad)"
                ent_id = f"{depto_id}||E::{ent_label}"
                ids.append(ent_id); labels.append(ent_label); parents.append(depto_id)
                values.append(float(row["presupuestosgrinversion"]))

    return ids, labels, parents, values


def create_treemap_chart(df_filtrado):
    try:
        records = _build_hierarchy_records(df_filtrado)
        if records is None:
            return None
        ids, labels, parents, values = records
        fig = go.Figure(go.Treemap(
            ids=ids, labels=labels, parents=parents, values=values,
            branchvalues="total",
            marker={"colorscale": CHART_SCALE_BLUE,
                    "line": {"color": "#FFFFFF", "width": 1}},
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>",
            pathbar={"visible": True, "textfont": {"color": PALETTE["text"]}},
        ))
        return _apply_theme(fig, height=560, margin={"t": 40, "l": 10, "r": 10, "b": 10})

    except Exception as e:
        st.error(f"Error al crear treemap: {e}")
        return None


def create_sunburst_chart(df_filtrado):
    try:
        records = _build_hierarchy_records(df_filtrado)
        if records is None:
            return None
        ids, labels, parents, values = records
        fig = go.Figure(go.Sunburst(
            ids=ids, labels=labels, parents=parents, values=values,
            branchvalues="total",
            marker={"colorscale": CHART_SCALE_BLUE,
                    "line": {"color": "#FFFFFF", "width": 1}},
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>",
        ))
        return _apply_theme(fig, height=560, margin={"t": 40, "l": 10, "r": 10, "b": 10})

    except Exception as e:
        st.error(f"Error al crear sunburst: {e}")
        return None


def create_presupuesto_vs_saldo_chart(df_filtrado, top_n=10):
    """Hero chart: top N departamentos con presupuesto apilado (Aprobado + Saldo pendiente).

    Largo total = presupuesto. Segmento oscuro = aprobado. Segmento ambar = saldo pendiente.
    Label lateral: % ejecucion + total.
    """
    try:
        dept_data = aggregate_sgr_data(df_filtrado, ["nombredepartamento"])
        dept_data = dept_data.nlargest(top_n, "presupuestosgrinversion")

        if dept_data.empty:
            return None

        dept_data = dept_data.sort_values("presupuestosgrinversion", ascending=True)
        dept_data["pct_ejecucion"] = (
            dept_data["recursosaprobadosasignadosspgr"]
            / dept_data["presupuestosgrinversion"].replace(0, pd.NA)
            * 100
        ).fillna(0)

        max_presupuesto = dept_data["presupuestosgrinversion"].max()

        bar_width = 0.55

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Aprobado",
            x=dept_data["recursosaprobadosasignadosspgr"],
            y=dept_data["nombredepartamento"],
            orientation="h",
            width=bar_width,
            marker={"color": PALETTE["primary"], "line": {"width": 0}},
            hovertemplate="<b>%{y}</b><br>Aprobado: $%{x:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name="Saldo pendiente",
            x=dept_data["SALDO_PENDIENTE"],
            y=dept_data["nombredepartamento"],
            orientation="h",
            width=bar_width,
            marker={"color": PALETTE["accent"], "line": {"width": 0}},
            hovertemplate="<b>%{y}</b><br>Pendiente: $%{x:,.0f}<extra></extra>",
            text=[
                f"  {format_currency(p)} · {pct:.0f}%"
                for p, pct in zip(
                    dept_data["presupuestosgrinversion"],
                    dept_data["pct_ejecucion"],
                )
            ],
            textposition="outside",
            textfont={"size": 11, "color": PALETTE["text_muted"]},
            cliponaxis=False,
        ))

        tickvals, ticktext = _currency_ticks(max_presupuesto)
        n = len(dept_data)
        height = 120 + 38 * n if n > 3 else 180 + 30 * n

        return _apply_theme(
            fig,
            barmode="stack",
            height=height,
            showlegend=True,
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02,
                    "xanchor": "right", "x": 1, "bgcolor": "rgba(0,0,0,0)"},
            xaxis={
                "tickmode": "array",
                "tickvals": tickvals,
                "ticktext": ticktext,
                "gridcolor": PALETTE["border"],
                "showline": False,
                "zeroline": False,
                "range": [0, max_presupuesto * 1.25],
            },
            yaxis={"gridcolor": "rgba(0,0,0,0)", "automargin": True},
            margin={"t": 40, "l": 20, "r": 40, "b": 40},
            uniformtext={"mode": "hide", "minsize": 10},
        )

    except Exception as e:
        st.error(f"Error al crear chart presupuesto vs saldo: {e}")
        return None


def create_bottom_ejecucion_chart(df_filtrado, bottom_n=5):
    """Bottom N departamentos por % ejecucion (callout de problema)."""
    try:
        dept_data = aggregate_sgr_data(df_filtrado, ["nombredepartamento"])
        dept_data = dept_data[dept_data["presupuestosgrinversion"] > 0].copy()
        if dept_data.empty:
            return None

        dept_data["pct_ejecucion"] = (
            dept_data["recursosaprobadosasignadosspgr"]
            / dept_data["presupuestosgrinversion"] * 100
        )
        dept_data = dept_data.nsmallest(bottom_n, "pct_ejecucion")
        dept_data = dept_data.sort_values("pct_ejecucion", ascending=False)

        fig = go.Figure(go.Bar(
            x=dept_data["pct_ejecucion"],
            y=dept_data["nombredepartamento"],
            orientation="h",
            marker_color=PALETTE["danger"],
            text=dept_data["pct_ejecucion"].apply(lambda v: f"{v:.1f}%"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Ejecucion: %{x:.1f}%<extra></extra>",
        ))
        return _apply_theme(
            fig,
            height=280,
            showlegend=False,
            xaxis={"tickformat": ".0f", "ticksuffix": "%",
                   "gridcolor": PALETTE["border"], "title": "",
                   "range": [0, max(100, dept_data["pct_ejecucion"].max() * 1.15)]},
            yaxis={"title": "", "gridcolor": "rgba(0,0,0,0)"},
            margin={"t": 20, "l": 20, "r": 60, "b": 30},
        )

    except Exception as e:
        st.error(f"Error al crear chart bottom ejecucion: {e}")
        return None


def create_saldo_pendiente_chart(df_filtrado, top_n=10):
    try:
        entidad_data = aggregate_sgr_data(df_filtrado, ["nombreentidad", "nombredepartamento"])
        entidad_data = entidad_data.nlargest(top_n, "SALDO_PENDIENTE")

        if entidad_data.empty or entidad_data["SALDO_PENDIENTE"].sum() == 0:
            return None

        entidad_data["label"] = (
            entidad_data["nombreentidad"] + " · " + entidad_data["nombredepartamento"]
        )

        fig = px.bar(
            entidad_data,
            x="SALDO_PENDIENTE",
            y="label",
            orientation="h",
            labels={"SALDO_PENDIENTE": "Saldo pendiente", "label": ""},
            color="SALDO_PENDIENTE",
            color_continuous_scale=CHART_SCALE_WARM,
        )
        fig.update_traces(
            text=[format_currency(v) for v in entidad_data["SALDO_PENDIENTE"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Saldo: $%{x:,.0f}<extra></extra>",
            cliponaxis=False,
        )
        tickvals, ticktext = _currency_ticks(entidad_data["SALDO_PENDIENTE"].max())
        return _apply_theme(
            fig,
            height=max(400, 38 * len(entidad_data) + 80),
            showlegend=False,
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending", "automargin": True},
            xaxis={
                "tickmode": "array", "tickvals": tickvals, "ticktext": ticktext,
                "gridcolor": PALETTE["border"], "showline": False, "zeroline": False,
                "range": [0, entidad_data["SALDO_PENDIENTE"].max() * 1.18],
            },
            margin={"t": 20, "l": 20, "r": 40, "b": 40},
        )

    except Exception as e:
        st.error(f"Error al crear grafico de saldo pendiente: {e}")
        return None


def create_vigencia_chart(df_filtrado):
    if "vigencia" not in df_filtrado.columns:
        return None

    try:
        vigencia_data = df_filtrado.groupby("vigencia").agg(
            {"presupuestosgrinversion": "sum", "recursosaprobadosasignadosspgr": "sum"}
        ).reset_index()

        if len(vigencia_data) < 2:
            return None

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Presupuesto", x=vigencia_data["vigencia"],
            y=vigencia_data["presupuestosgrinversion"],
            marker_color=PALETTE["primary"],
            text=vigencia_data["presupuestosgrinversion"].apply(format_currency),
            textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name="Recursos Aprobados", x=vigencia_data["vigencia"],
            y=vigencia_data["recursosaprobadosasignadosspgr"],
            marker_color=PALETTE["secondary"],
            text=vigencia_data["recursosaprobadosasignadosspgr"].apply(format_currency),
            textposition="outside",
        ))
        return _apply_theme(
            fig,
            barmode="group",
            height=420,
            xaxis={"title": ""},
            yaxis={"title": "", "tickformat": "~s"},
        )

    except Exception as e:
        st.error(f"Error al crear grafico de vigencias: {e}")
        return None
