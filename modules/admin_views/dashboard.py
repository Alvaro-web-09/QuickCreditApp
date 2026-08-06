"""
============================================================
TABLERO DE CONTROL ADMINISTRATIVO — Reconstrucción completa
============================================================
Conserva la estructura y los KPIs originales, pero corrige de raíz
el problema de "todo en 0":

  1) monto_real: usa 'monto_pagado' SOLO si > 0; si no, usa 'monto'.
  2) El rango de fechas por defecto se ajusta AUTOMÁTICAMENTE al
     primer y último dato real (así siempre abre mostrando datos).
  3) Botón "Buscar" (st.form) para evitar el parpadeo a 0.
  4) .copy() para no mutar la caché de Streamlit.
============================================================
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from db_connection import get_db_client

# ==========================================
# CONSTANTES
# ==========================================
ESTADO_MORA = "mora"
ESTADO_PAGADO = "Pagado"
TIPOS_GASTO = ["pago_nomina", "egreso", "otros"]
TIPO_ENTREGA_CAPITAL = "entrega_capital"
MONEDA = "C$"


# ==========================================
# HELPER: traer TODAS las filas (rompe el límite de 1000 de Supabase)
# ==========================================
def fetch_all(supabase, tabla, columnas="*", fecha_col=None, fecha_limite=None, page_size=1000):
    """Supabase devuelve como MÁXIMO 1000 filas por consulta. Esta función pide
    los datos en bloques (paginación con .range) y los junta hasta traerlos TODOS.
    Así ya no se pierden los registros más recientes (julio/agosto)."""
    filas = []
    inicio = 0
    while True:
        query = supabase.table(tabla).select(columnas)
        if fecha_col and fecha_limite:
            query = query.gte(fecha_col, fecha_limite)
        # .range(inicio, fin) trae el bloque [inicio..fin] inclusive
        resp = query.range(inicio, inicio + page_size - 1).execute()
        bloque = resp.data or []
        filas.extend(bloque)
        # Si el bloque vino incompleto (< page_size), ya no hay más páginas
        if len(bloque) < page_size:
            break
        inicio += page_size
    return filas


# ==========================================
# 1. CARGA DE DATOS (con paginación completa)
# ==========================================
@st.cache_data(ttl=60)
def cargar_datos():
    supabase = get_db_client()

    # Ventana amplia (2 años) para no dejar datos fuera
    fecha_limite = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

    # Traemos TODAS las filas usando paginación (ya no se corta en 1000)
    data_pagos = fetch_all(
        supabase, "pagos",
        "id, prestamo_id, cobrador_id, monto, monto_pagado, fecha_pago",
        fecha_col="fecha_pago", fecha_limite=fecha_limite)

    data_prestamos = fetch_all(
        supabase, "prestamos",
        "id, cliente_id, cobrador_id, monto_prestado, monto_total_deuda, saldo_pendiente, estado, fecha_inicio")

    data_visitas = fetch_all(supabase, "bitacora_visitas", "*", fecha_col="fecha", fecha_limite=fecha_limite)
    data_caja = fetch_all(supabase, "movimientos_caja", "*", fecha_col="fecha", fecha_limite=fecha_limite)
    data_usuarios = fetch_all(supabase, "usuarios", "id, nombre_completo")
    data_clientes = fetch_all(supabase, "clientes", "id, nombre")

    # --- DataFrames ---
    df_pagos = pd.DataFrame(data_pagos) if data_pagos else pd.DataFrame()
    df_prestamos = pd.DataFrame(data_prestamos) if data_prestamos else pd.DataFrame()
    df_visitas = pd.DataFrame(data_visitas) if data_visitas else pd.DataFrame()
    df_caja = pd.DataFrame(data_caja) if data_caja else pd.DataFrame()

    mapa_usuarios = {u['id']: u['nombre_completo'] for u in data_usuarios} if data_usuarios else {}
    mapa_clientes = {c['id']: c.get('nombre', 'Desconocido') for c in data_clientes} if data_clientes else {}

    # --- PAGOS: limpieza + monto_real (corrección del bug) ---
    if not df_pagos.empty:
        df_pagos['nombre_cobrador'] = df_pagos['cobrador_id'].map(mapa_usuarios).fillna('Desconocido')
        df_pagos['fecha_pago'] = pd.to_datetime(df_pagos['fecha_pago'], errors='coerce').dt.date

        df_pagos['monto'] = pd.to_numeric(df_pagos.get('monto'), errors='coerce').fillna(0)
        if 'monto_pagado' in df_pagos.columns:
            df_pagos['monto_pagado'] = pd.to_numeric(df_pagos['monto_pagado'], errors='coerce').fillna(0)
            # Usa monto_pagado SOLO si es > 0; de lo contrario usa monto
            df_pagos['monto_real'] = df_pagos['monto_pagado'].where(df_pagos['monto_pagado'] > 0, df_pagos['monto'])
        else:
            df_pagos['monto_real'] = df_pagos['monto']
        df_pagos['monto_real'] = pd.to_numeric(df_pagos['monto_real'], errors='coerce').fillna(0)

    # --- VISITAS ---
    if not df_visitas.empty:
        df_visitas['nombre_cobrador'] = df_visitas['cobrador_id'].map(mapa_usuarios).fillna('Desconocido')
        df_visitas['fecha'] = pd.to_datetime(df_visitas['fecha'], errors='coerce').dt.date

    # --- PRÉSTAMOS ---
    if not df_prestamos.empty:
        df_prestamos['nombre_cobrador'] = df_prestamos['cobrador_id'].map(mapa_usuarios).fillna('Sin Asignar')
        df_prestamos['nombre_cliente'] = df_prestamos['cliente_id'].map(mapa_clientes).fillna('Cliente Desconocido')
        df_prestamos['fecha_inicio'] = pd.to_datetime(df_prestamos['fecha_inicio'], errors='coerce').dt.date

    # --- CAJA ---
    if not df_caja.empty:
        if 'usuario_id' in df_caja.columns:
            df_caja['nombre_cobrador'] = df_caja['usuario_id'].map(mapa_usuarios).fillna('Desconocido')
        if 'fecha' in df_caja.columns:
            df_caja['fecha'] = pd.to_datetime(df_caja['fecha'], errors='coerce').dt.date
        if 'monto' in df_caja.columns:
            df_caja['monto'] = pd.to_numeric(df_caja['monto'], errors='coerce').fillna(0)

    return df_pagos, df_prestamos, df_visitas, df_caja, mapa_usuarios, mapa_clientes


# ==========================================
# 2. RANGO DE FECHAS AUTOMÁTICO (clave del fix)
# ==========================================
def rango_datos_reales(df_pagos, df_caja, df_visitas):
    """Devuelve (min, max) de todas las fechas que existen en los datos.
    Así el dashboard abre mostrando SIEMPRE el periodo con información."""
    fechas = []
    if not df_pagos.empty and 'fecha_pago' in df_pagos.columns:
        fechas += df_pagos['fecha_pago'].dropna().tolist()
    if not df_caja.empty and 'fecha' in df_caja.columns:
        fechas += df_caja['fecha'].dropna().tolist()
    if not df_visitas.empty and 'fecha' in df_visitas.columns:
        fechas += df_visitas['fecha'].dropna().tolist()

    if fechas:
        return min(fechas), max(fechas)
    hoy = datetime.now().date()
    return hoy - timedelta(days=365), hoy


# ==========================================
# 3. LÓGICA FINANCIERA
# ==========================================
def calcular_kpis_financieros(df_pagos, df_prestamos, df_caja):
    if df_pagos.empty or df_prestamos.empty:
        return 0, 0, 0, 0

    df_prestamos = df_prestamos.copy()  # no mutar la caché
    df_caja = df_caja.copy()

    monto_deuda = pd.to_numeric(df_prestamos['monto_total_deuda'], errors='coerce').fillna(0)
    monto_prestado = pd.to_numeric(df_prestamos['monto_prestado'], errors='coerce').fillna(0)
    df_prestamos['margen'] = ((monto_deuda - monto_prestado) / monto_deuda.replace(0, 1)).fillna(0)

    df_merge = pd.merge(df_pagos, df_prestamos[['id', 'margen']],
                        left_on='prestamo_id', right_on='id', how='left')
    df_merge['margen'] = df_merge['margen'].fillna(0)
    df_merge['ganancia_interes'] = df_merge['monto_real'] * df_merge['margen']

    ganancia_bruta = df_merge['ganancia_interes'].sum()
    recaudado_total = df_merge['monto_real'].sum()

    gastos_operativos = 0
    if not df_caja.empty and 'tipo' in df_caja.columns:
        df_caja['monto'] = pd.to_numeric(df_caja['monto'], errors='coerce').fillna(0)
        gastos_operativos = abs(df_caja[df_caja['tipo'].isin(TIPOS_GASTO)]['monto'].sum())

    utilidad_neta = ganancia_bruta - gastos_operativos
    return recaudado_total, ganancia_bruta, gastos_operativos, utilidad_neta


# ==========================================
# 4. PANEL DE DIAGNÓSTICO (opcional)
# ==========================================
def panel_diagnostico(df_pagos, df_prestamos, df_caja, df_visitas, mapa_users):
    st.warning("MODO DIAGNÓSTICO — datos crudos de Supabase.")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Filas Pagos", len(df_pagos))
    c2.metric("Filas Préstamos", len(df_prestamos))
    c3.metric("Filas Caja", len(df_caja))
    c4.metric("Filas Visitas", len(df_visitas))
    c5.metric("Usuarios", len(mapa_users))
    if not df_pagos.empty:
        st.write("Fechas de pagos:", df_pagos['fecha_pago'].min(), "→", df_pagos['fecha_pago'].max())
        st.write("Suma monto_real (histórico):", df_pagos['monto_real'].sum())
        st.dataframe(df_pagos.head(10), use_container_width=True)
    st.markdown("---")


# ==========================================
# 5. INTERFAZ
# ==========================================
def mostrar_dashboard():
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown("## Tablero de Control Administrativo")
        st.markdown("Monitor de rendimiento financiero y operativo.")
    with col_h2:
        st.markdown(f"**Fecha de Corte:** {datetime.now().strftime('%d/%m/%Y')}")

    with st.spinner("Procesando base de datos..."):
        try:
            df_pagos, df_prestamos, df_visitas, df_caja, mapa_users, mapa_clientes = cargar_datos()
        except Exception as e:
            st.error(f"Error de conexión: {e}")
            return

    # Rango real de los datos (mín y máx reales)
    fecha_min_datos, fecha_max_datos = rango_datos_reales(df_pagos, df_caja, df_visitas)

    # Inicializamos el rango APLICADO con el rango REAL de los datos (¡clave!)
    if "f_ini_aplicado" not in st.session_state:
        st.session_state["f_ini_aplicado"] = fecha_min_datos
        st.session_state["f_fin_aplicado"] = fecha_max_datos
        st.session_state["cobrador_aplicado"] = "Todos"

    # SEGURIDAD: recortamos (clamp) cualquier fecha guardada para que SIEMPRE
    # esté dentro de [fecha_min_datos, fecha_max_datos]. Esto evita el crash
    # cuando quedó en memoria un rango viejo fuera de los límites del calendario.
    def _clamp(f):
        f = max(f, fecha_min_datos)
        f = min(f, fecha_max_datos)
        return f
    st.session_state["f_ini_aplicado"] = _clamp(st.session_state["f_ini_aplicado"])
    st.session_state["f_fin_aplicado"] = _clamp(st.session_state["f_fin_aplicado"])
    if st.session_state["f_ini_aplicado"] > st.session_state["f_fin_aplicado"]:
        st.session_state["f_ini_aplicado"] = fecha_min_datos
        st.session_state["f_fin_aplicado"] = fecha_max_datos

    # Interruptor de diagnóstico (apagado por defecto)
    if st.toggle("🔧 Activar modo diagnóstico", value=False):
        panel_diagnostico(df_pagos, df_prestamos, df_caja, df_visitas, mapa_users)

    # --- FILTROS CON BOTÓN BUSCAR ---
    with st.expander("⚙️ Configuración de Análisis (Filtros)", expanded=True):
        st.caption(f"📅 Tus datos van del **{fecha_min_datos.strftime('%d/%m/%Y')}** "
                   f"al **{fecha_max_datos.strftime('%d/%m/%Y')}**. "
                   "El tablero ya abre mostrando todo ese periodo.")
        with st.form("filtros_form"):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                # Sin candados de min/max: el calendario NO bloquea ningún mes.
                # (El aviso de arriba ya te indica dónde hay datos.)
                rango = st.date_input(
                    "Seleccione Rango de Fechas",
                    value=(st.session_state["f_ini_aplicado"], st.session_state["f_fin_aplicado"]),
                )
                st.caption("Afecta ingresos, gastos y visitas.")
            with col_f2:
                opciones_cobrador = ["Todos"] + list(mapa_users.values())
                idx = opciones_cobrador.index(st.session_state["cobrador_aplicado"]) \
                    if st.session_state["cobrador_aplicado"] in opciones_cobrador else 0
                sel_cobrador_form = st.selectbox("Filtrar por Personal", opciones_cobrador, index=idx)
                st.caption("Aísla el rendimiento por cobrador.")

            colb1, colb2 = st.columns(2)
            buscar = colb1.form_submit_button("🔍 Buscar / Aplicar filtros", use_container_width=True)
            resetear = colb2.form_submit_button("↺ Ver todo el periodo", use_container_width=True)

        if buscar:
            if isinstance(rango, (tuple, list)) and len(rango) == 2:
                st.session_state["f_ini_aplicado"] = rango[0]
                st.session_state["f_fin_aplicado"] = rango[1]
            st.session_state["cobrador_aplicado"] = sel_cobrador_form
        if resetear:
            st.session_state["f_ini_aplicado"] = fecha_min_datos
            st.session_state["f_fin_aplicado"] = fecha_max_datos
            st.session_state["cobrador_aplicado"] = "Todos"

    # Valores ya aplicados (estables)
    f_ini = st.session_state["f_ini_aplicado"]
    f_fin = st.session_state["f_fin_aplicado"]
    sel_cobrador = st.session_state["cobrador_aplicado"]

    # --- FILTRADO ---
    df_p = df_pagos.copy()
    if not df_p.empty:
        df_p = df_p[(df_p['fecha_pago'] >= f_ini) & (df_p['fecha_pago'] <= f_fin)]
        if sel_cobrador != "Todos":
            df_p = df_p[df_p['nombre_cobrador'] == sel_cobrador]

    df_c = df_caja.copy()
    if not df_c.empty and 'fecha' in df_c.columns:
        df_c = df_c[(df_c['fecha'] >= f_ini) & (df_c['fecha'] <= f_fin)]

    # --- PESTAÑAS ---
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["Rentabilidad Financiera", "Eficiencia Operativa", "Análisis de Riesgo"])

    # ---------- TAB 1: RENTABILIDAD ----------
    with tab1:
        if df_p.empty:
            st.info(
                f"ℹ️ No hay **pagos** entre {f_ini.strftime('%d/%m/%Y')} y {f_fin.strftime('%d/%m/%Y')}. "
                "Usa el botón **↺ Ver todo el periodo** para regresar al rango con datos."
            )

        recaudado, ganancia_bruta, gastos, utilidad = calcular_kpis_financieros(df_p, df_prestamos, df_c)

        with st.container(border=True):
            st.markdown("#### Estado de Resultados (Periodo Seleccionado)")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Ingresos Totales (Caja)", f"{MONEDA} {recaudado:,.0f}",
                      help="Suma total del dinero recolectado en pagos. Fuente: 'pagos'.")
            c2.metric("Margen Bruto (Intereses)", f"{MONEDA} {ganancia_bruta:,.0f}",
                      help="Ganancia por intereses (excluye retorno de capital).")
            c3.metric("Gastos Operativos", f"{MONEDA} {gastos:,.0f}", delta=-gastos if gastos else None,
                      delta_color="inverse", help="Nómina, egresos u otros. Fuente: 'movimientos_caja'.")
            c4.metric("Utilidad Neta", f"{MONEDA} {utilidad:,.0f}",
                      delta="Positivo" if utilidad > 0 else "Negativo",
                      delta_color="normal" if utilidad > 0 else "inverse",
                      help="Margen Bruto menos Gastos Operativos.")

        st.markdown("##### Análisis de Flujo")
        gasto_grafico = -abs(gastos)
        fig = go.Figure(go.Waterfall(
            name="Flujo", orientation="v",
            measure=["relative", "relative", "total"],
            x=["Ganancia Bruta", "Gastos Operativos", "Utilidad Neta"],
            text=[f"+{ganancia_bruta:,.0f}", f"{gasto_grafico:,.0f}", f"={utilidad:,.0f}"],
            textposition="auto",
            y=[ganancia_bruta, gasto_grafico, utilidad],
            connector={"line": {"color": "#636363"}},
            decreasing={"marker": {"color": "#D32F2F"}},
            increasing={"marker": {"color": "#538E38"}},
            totals={"marker": {"color": "#407AE7"}},
        ))
        fig.update_layout(height=350, margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Cómo los gastos reducen la ganancia bruta hasta la utilidad final.")

    # ---------- TAB 2: EFICIENCIA OPERATIVA ----------
    with tab2:
        df_v = df_visitas.copy()
        if not df_v.empty and 'fecha' in df_v.columns:
            df_v = df_v[(df_v['fecha'] >= f_ini) & (df_v['fecha'] <= f_fin)]
            if sel_cobrador != "Todos":
                df_v = df_v[df_v['nombre_cobrador'] == sel_cobrador]

        total_visitas = len(df_v)
        efectivas = len(df_v[df_v['estado_visita'] == ESTADO_PAGADO]) if not df_v.empty else 0
        porc = (efectivas / total_visitas * 100) if total_visitas > 0 else 0

        with st.container(border=True):
            st.markdown("#### Resumen de Campo")
            k1, k2 = st.columns(2)
            k1.metric("Visitas Totales", total_visitas, help="Registros en la bitácora durante el periodo.")
            k2.metric("Tasa de Conversión (Cobro)", f"{porc:.1f}%",
                      help="(Visitas con pago / Total visitas) * 100.")

            col_graph, col_info = st.columns([2, 1])
            with col_graph:
                if not df_v.empty:
                    conteos = df_v['estado_visita'].value_counts().reset_index()
                    conteos.columns = ['Resultado', 'Cantidad']
                    color_map = {'Pagado': '#388E3C', 'No Pago': '#D32F2F', 'Ausente': '#FBC02D', 'Pendiente': '#9E9E9E'}
                    fig_pie = px.pie(conteos, values='Cantidad', names='Resultado',
                                     title="Distribución de Resultados de Visita", hole=0.5,
                                     color='Resultado', color_discrete_map=color_map)
                    fig_pie.update_layout(height=300, margin=dict(t=40, b=10))
                    st.plotly_chart(fig_pie, use_container_width=True)
                    st.caption("Efectividad del personal en campo.")
                else:
                    st.info("No hay registros de visitas en el rango seleccionado.")
            with col_info:
                st.markdown("<br><br>", unsafe_allow_html=True)
                st.markdown("#### Glosario")
                st.info("**Tasa de Conversión:** % de visitas que generaron ingreso real. "
                        "Un valor bajo sugiere problemas en la ruta de cobro o insolvencia.")

        # --- Capital asignado vs colocado ---
        st.markdown("---")
        st.markdown("#### Colocación de Capital por Vendedor")
        st.caption("Capital entregado desde caja vs capital colocado en préstamos (según rango de fechas).")

        todos_vendedores = list(mapa_users.values())
        vendedores_sel = st.multiselect(
            "Marcar Vendedores a comparar:", options=todos_vendedores,
            default=todos_vendedores if len(todos_vendedores) <= 5 else todos_vendedores[:5],
        )

        if vendedores_sel:
            df_pf = df_prestamos.copy()
            if not df_pf.empty:
                df_pf = df_pf[(df_pf['fecha_inicio'] >= f_ini) & (df_pf['fecha_inicio'] <= f_fin)]
                df_pf = df_pf[df_pf['nombre_cobrador'].isin(vendedores_sel)]

            df_colocado = pd.DataFrame(columns=['nombre_cobrador', 'Capital Colocado'])
            if not df_pf.empty:
                df_pf['monto_prestado'] = pd.to_numeric(df_pf['monto_prestado'], errors='coerce').fillna(0)
                df_colocado = df_pf.groupby('nombre_cobrador')['monto_prestado'].sum().reset_index()
                df_colocado.rename(columns={'monto_prestado': 'Capital Colocado'}, inplace=True)

            df_asignado = pd.DataFrame(columns=['nombre_cobrador', 'Capital Asignado'])
            if not df_c.empty and 'tipo' in df_c.columns:
                df_ent = df_c[(df_c['tipo'] == TIPO_ENTREGA_CAPITAL) & (df_c['nombre_cobrador'].isin(vendedores_sel))]
                if not df_ent.empty:
                    df_asignado = df_ent.groupby('nombre_cobrador')['monto'].sum().reset_index()
                    df_asignado.rename(columns={'monto': 'Capital Asignado'}, inplace=True)

            df_cap = pd.merge(df_colocado, df_asignado, on='nombre_cobrador', how='outer').fillna(0)

            if not df_cap.empty and (df_cap['Capital Colocado'].sum() > 0 or df_cap['Capital Asignado'].sum() > 0):
                df_melt = df_cap.melt(id_vars='nombre_cobrador',
                                      value_vars=['Capital Asignado', 'Capital Colocado'],
                                      var_name='Tipo', value_name='Monto (C$)')
                fig_bar = px.bar(df_melt, x='nombre_cobrador', y='Monto (C$)', color='Tipo',
                                 barmode='group', text_auto='.2s',
                                 color_discrete_map={'Capital Asignado': '#1E88E5', 'Capital Colocado': '#43A047'})
                fig_bar.update_layout(xaxis_title="Personal", yaxis_title="Monto (C$)",
                                      legend_title="", margin=dict(t=20, b=20), height=400)
                st.plotly_chart(fig_bar, use_container_width=True)
                st.caption("Qué porcentaje del fondo operativo se coloca en nuevos préstamos.")
            else:
                st.warning("No hay entregas de capital ni préstamos para los vendedores/fechas seleccionados.")
        else:
            st.info("👆 Selecciona al menos un vendedor para ver la comparativa.")

    # ---------- TAB 3: ANÁLISIS DE RIESGO ----------
    with tab3:
        st.warning("Nota: Estado actual de la cartera (Acumulado Histórico). NO depende del filtro de fechas.")
        df_loans = df_prestamos.copy()
        if sel_cobrador != "Todos" and not df_loans.empty:
            df_loans = df_loans[df_loans['nombre_cobrador'] == sel_cobrador]

        if not df_loans.empty:
            lista_clientes = ["Todos los Clientes"] + sorted(df_loans['nombre_cliente'].unique().tolist())
            sel_cliente = st.selectbox("🔍 Analizar un cliente específico:", lista_clientes)
            if sel_cliente != "Todos los Clientes":
                df_loans = df_loans[df_loans['nombre_cliente'] == sel_cliente]
            st.markdown("---")

        if not df_loans.empty:
            df_loans['saldo_pendiente'] = pd.to_numeric(df_loans['saldo_pendiente'], errors='coerce').fillna(0)
            total_calle = df_loans['saldo_pendiente'].sum()
            total_mora = df_loans[df_loans['estado'] == ESTADO_MORA]['saldo_pendiente'].sum()
            indice_mora = (total_mora / total_calle * 100) if total_calle > 0 else 0

            with st.container(border=True):
                m1, m2, m3 = st.columns(3)
                m1.metric("Saldo Total en Calle", f"{MONEDA} {total_calle:,.0f}",
                          help="Suma de saldos pendientes de todos los préstamos.")
                m2.metric("Cartera Vencida (Mora)", f"{MONEDA} {total_mora:,.0f}", delta_color="inverse",
                          help="Saldos pendientes de préstamos en estado 'mora'.")
                m3.metric("Índice de Morosidad", f"{indice_mora:.1f}%",
                          delta="Alto Riesgo" if indice_mora > 20 else "Saludable", delta_color="inverse",
                          help="(Cartera Vencida / Saldo Total) * 100.")

            st.subheader("Top 15 Clientes con Mayor Deuda Vencida")
            morosos = df_loans[df_loans['estado'] == ESTADO_MORA].sort_values('saldo_pendiente', ascending=False).head(15)
            if not morosos.empty:
                st.dataframe(
                    morosos[['nombre_cliente', 'nombre_cobrador', 'fecha_inicio', 'monto_prestado', 'saldo_pendiente']],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "nombre_cliente": "Cliente Titular",
                        "nombre_cobrador": "Cobrador Asignado",
                        "fecha_inicio": st.column_config.DateColumn("Fecha Préstamo", format="DD/MM/YYYY"),
                        "monto_prestado": st.column_config.NumberColumn("Monto Original", format="C$ %.2f"),
                        "saldo_pendiente": st.column_config.NumberColumn("Saldo Deudor", format="C$ %.2f"),
                    }
                )
            else:
                st.success("Cartera saludable: No hay clientes en mora con los filtros actuales. "
                           "(Nota: tus préstamos actuales solo tienen estados 'pagado' y 'activo').")
        else:
            st.warning("No hay préstamos que coincidan con los filtros seleccionados.")


if __name__ == "__main__":
    mostrar_dashboard()
