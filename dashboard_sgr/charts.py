import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard_sgr.utils import aggregate_sgr_data


def create_fondo_comparison_chart(df_filtrado, fondos_interes):
    """Create a grouped bar chart comparing funds."""
    try:
        chart_data = []
        for fondo in fondos_interes:
            datos_fondo = df_filtrado[df_filtrado["nombrefondo"] == fondo]
            if len(datos_fondo) > 0:
                chart_data.append({
                    "Fondo": fondo.replace(
                        "ASIGNACION PARA LA INVERSION LOCAL", "INVERSION LOCAL"
                    ),
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
            marker_color="lightblue",
            text=df_chart["Presupuesto"].apply(lambda x: f"${x:,.0f}"),
            textposition="auto",
        ))
        fig.add_trace(go.Bar(
            name="Recursos Aprobados", x=df_chart["Fondo"], y=df_chart["Recursos Aprobados"],
            marker_color="darkgreen",
            text=df_chart["Recursos Aprobados"].apply(lambda x: f"${x:,.0f}"),
            textposition="auto",
        ))
        fig.add_trace(go.Bar(
            name="Saldo Pendiente", x=df_chart["Fondo"], y=df_chart["Saldo Pendiente"],
            marker_color="coral",
            text=df_chart["Saldo Pendiente"].apply(lambda x: f"${x:,.0f}"),
            textposition="auto",
        ))

        fig.update_layout(
            title="Comparacion de Fondos SGR",
            xaxis_title="Tipo de Fondo",
            yaxis_title="Valor (COP)",
            barmode="group",
            height=500,
            showlegend=True,
            hovermode="x unified",
        )
        return fig

    except Exception as e:
        st.error(f"Error al crear grafico por fondo: {e}")
        return None


def create_departamento_distribution_chart(df_filtrado, top_n=10):
    """Create a horizontal bar chart of top departments by budget."""
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
            title=f"Top {top_n} Departamentos por Presupuesto SGR",
            labels={
                "presupuestosgrinversion": "Presupuesto (COP)",
                "nombredepartamento": "Departamento",
            },
            color="presupuestosgrinversion",
            color_continuous_scale="Blues",
        )
        fig.update_layout(
            height=600, showlegend=False, yaxis={"categoryorder": "total ascending"}
        )
        fig.update_traces(texttemplate="$%{x:,.0f}", textposition="outside")
        return fig

    except Exception as e:
        st.error(f"Error al crear grafico por departamento: {e}")
        return None


def create_fondo_pie_chart(df_filtrado, fondos_interes):
    """Create a pie chart of budget distribution by fund type."""
    try:
        pie_data = []
        for fondo in fondos_interes:
            datos_fondo = df_filtrado[df_filtrado["nombrefondo"] == fondo]
            if len(datos_fondo) > 0:
                pie_data.append({
                    "Fondo": fondo.replace(
                        "ASIGNACION PARA LA INVERSION LOCAL", "INVERSION LOCAL"
                    ),
                    "Presupuesto": datos_fondo["presupuestosgrinversion"].sum(),
                })

        if not pie_data:
            return None

        df_pie = pd.DataFrame(pie_data)
        fig = px.pie(
            df_pie, values="Presupuesto", names="Fondo",
            title="Distribucion del Presupuesto por Tipo de Fondo",
        )
        fig.update_traces(
            textposition="inside", textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Presupuesto: $%{value:,.0f}<br>Porcentaje: %{percent}<extra></extra>",
        )
        fig.update_layout(height=500)
        return fig

    except Exception as e:
        st.error(f"Error al crear grafico de pastel: {e}")
        return None


def create_kpi_metrics(df_filtrado):
    """Create a gauge chart showing approval percentage."""
    try:
        total_presupuesto = df_filtrado["presupuestosgrinversion"].sum()
        total_aprobado = df_filtrado["recursosaprobadosasignadosspgr"].sum()

        porcentaje = (total_aprobado / total_presupuesto * 100) if total_presupuesto > 0 else 0

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=porcentaje,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "% de Recursos Aprobados vs Presupuesto"},
            delta={"reference": 80},
            gauge={
                "axis": {"range": [None, 100]},
                "bar": {"color": "darkgreen"},
                "steps": [
                    {"range": [0, 50], "color": "lightgray"},
                    {"range": [50, 80], "color": "yellow"},
                    {"range": [80, 100], "color": "lightgreen"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 90,
                },
            },
        ))
        fig.update_layout(height=400)
        return fig, porcentaje

    except Exception as e:
        st.error(f"Error al crear metricas KPI: {e}")
        return None, 0


def create_treemap_chart(df_filtrado):
    """Create a hierarchical treemap: Fondo -> Departamento -> Entidad."""
    try:
        tree_data = df_filtrado.groupby(
            ["nombrefondo", "nombredepartamento", "nombreentidad"]
        ).agg({"presupuestosgrinversion": "sum"}).reset_index()

        if tree_data.empty:
            return None

        # Shorten fund names for readability
        tree_data["nombrefondo_short"] = tree_data["nombrefondo"].str.replace(
            "ASIGNACION PARA LA INVERSION LOCAL", "INVERSION LOCAL"
        )

        fig = px.treemap(
            tree_data,
            path=["nombrefondo_short", "nombredepartamento", "nombreentidad"],
            values="presupuestosgrinversion",
            title="Distribucion Jerarquica del Presupuesto SGR",
            color="presupuestosgrinversion",
            color_continuous_scale="Blues",
        )
        fig.update_layout(height=600)
        fig.update_traces(
            hovertemplate="<b>%{label}</b><br>Presupuesto: $%{value:,.0f}<extra></extra>"
        )
        return fig

    except Exception as e:
        st.error(f"Error al crear treemap: {e}")
        return None


def create_vigencia_chart(df_filtrado):
    """Create a bar chart comparing budget by vigencia (if multiple exist)."""
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
            marker_color="lightblue",
            text=vigencia_data["presupuestosgrinversion"].apply(lambda x: f"${x:,.0f}"),
            textposition="auto",
        ))
        fig.add_trace(go.Bar(
            name="Recursos Aprobados", x=vigencia_data["vigencia"],
            y=vigencia_data["recursosaprobadosasignadosspgr"],
            marker_color="darkgreen",
            text=vigencia_data["recursosaprobadosasignadosspgr"].apply(lambda x: f"${x:,.0f}"),
            textposition="auto",
        ))

        fig.update_layout(
            title="Presupuesto por Vigencia",
            xaxis_title="Vigencia",
            yaxis_title="Valor (COP)",
            barmode="group",
            height=500,
        )
        return fig

    except Exception as e:
        st.error(f"Error al crear grafico de vigencias: {e}")
        return None
