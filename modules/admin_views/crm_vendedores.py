import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from db_connection import get_db_client

# ==========================================
# DEFINICIÓN DE PALETA DE MARCA (STRICT)
# ==========================================
BRAND_PRIMARY = "#4CAF50"       # Verde CreceMás (Barras, positivos)
BRAND_BG_MAIN = "#F7F3E9"       # Crema Fondo (Fondo general)
BRAND_BG_SECONDARY = "#E6F4EA"  # Verde Suave (Contenedores)
BRAND_TEXT = "#0F3D3E"          # Azul Petróleo (Texto, títulos, ejes)

# ==========================================
# FUNCIONES AUXILIARES DE ESTILO
# ==========================================
def inyectar_css_marca():
    """Fuerza los colores de texto de la marca en elementos de Streamlit."""
    st.markdown(f"""
        <style>
        /* Forzar color de texto principal en títulos y párrafos */
        h1, h2, h3, h4, h5, p, span, div, label {{
            color: {BRAND_TEXT} !important;
        }}
        /* Ajustar color de captions (letras pequeñas) */
        .stCaption {{
            color: {BRAND_TEXT} !important;
            opacity: 0.8;
        }}
        /* Ajustar métricas (KPIs) */
        [data-testid="stMetricLabel"] {{
             color: {BRAND_TEXT} !important;
        }}
        [data-testid="stMetricValue"] {{
             color: {BRAND_PRIMARY} !important; /* Valor principal en Verde Marca */
        }}
        [data-testid="stMetricDelta"] {{
             color: {BRAND_TEXT} !important; /* Deltas en color texto neutro */
        }}
        </style>
        """, unsafe_allow_html=True)

def aplicar_tema_plotly(fig):
    """Aplica los colores de la marca al layout de los gráficos Plotly."""
    fig.update_layout(
        paper_bgcolor=BRAND_BG_MAIN, # Fondo del canvas igual al de la app
        plot_bgcolor=BRAND_BG_MAIN,  # Fondo del área de trazado
        font={'color': BRAND_TEXT},  # Color de fuente global
        # Título del gráfico general
        title={'font': {'color': BRAND_TEXT}},
        
        xaxis={
            'tickfont': {'color': BRAND_TEXT}, 
            'title': {'font': {'color': BRAND_TEXT}}, 
            'gridcolor': '#e0e0e0'
        },
        yaxis={
            'tickfont': {'color': BRAND_TEXT}, 
            'title': {'font': {'color': BRAND_TEXT}}, 
            'gridcolor': '#e0e0e0'
        },
        legend={'font': {'color': BRAND_TEXT}, 'bgcolor': 'rgba(0,0,0,0)'},
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

# ==========================================
# 1. CARGA DE DATOS (BACKEND)
# ==========================================
@st.cache_data(ttl=300) # Opcional: Caché de 5 minutos para optimizar
def cargar_datos_crm():
    supabase = get_db_client()
    
    # A. Usuarios (Agregamos auto_aprobacion a la consulta)
    r_usuarios = supabase.table("usuarios").select("id, nombre_completo, rol, auto_aprobacion").execute()
    df_usuarios = pd.DataFrame(r_usuarios.data)
    
    # B. Clientes
    r_clientes = supabase.table("clientes").select("id, nombre").execute()
    df_clientes = pd.DataFrame(r_clientes.data)
    if not df_clientes.empty:
        df_clientes.rename(columns={'nombre': 'nombre_completo'}, inplace=True)
    
    # C. Préstamos 
    r_prestamos = supabase.table("prestamos").select("*").execute()
    df_prestamos = pd.DataFrame(r_prestamos.data)
    
    # D. Pagos 
    r_pagos = supabase.table("pagos").select("*").execute()
    df_pagos = pd.DataFrame(r_pagos.data)
    
    # E. Visitas
    r_visitas = supabase.table("bitacora_visitas").select("*").execute()
    df_visitas = pd.DataFrame(r_visitas.data)
    
    # F. Solicitudes
    r_solicitudes = supabase.table("solicitudes").select("*").execute()
    df_solicitudes = pd.DataFrame(r_solicitudes.data)

    return df_usuarios, df_clientes, df_prestamos, df_pagos, df_visitas, df_solicitudes

# ==========================================
# CALLBACK PARA TAB 4 (ACTUALIZAR PERMISOS)
# ==========================================
def actualizar_permisos(id_chofer, toggle_key, nombre_chofer):
    """Función que se ejecuta automáticamente cuando el admin hace click en el toggle."""
    nuevo_estado = st.session_state[toggle_key]
    
    try:
        supabase = get_db_client()
        # Actualizamos Supabase
        supabase.table("usuarios").update({"auto_aprobacion": nuevo_estado}).eq("id", id_chofer).execute()
        
        # Limpiamos la caché para que la interfaz tome los datos frescos
        cargar_datos_crm.clear() 
        
        st.toast(f"✅ Permisos actualizados para {nombre_chofer}")
        
    except Exception as e:
        st.error(f"Error al actualizar permisos: {e}")


# ==========================================
# 2. VISTA PRINCIPAL (DASHBOARD)
# ==========================================
def mostrar_crm_vendedores():
    # INYECTAR CSS AL INICIO
    inyectar_css_marca()
    
    st.markdown("## Tablero de Control - Fuerza de Ventas")
    st.markdown("---")
    
    with st.spinner("Sincronizando información del servidor..."):
        try:
            df_users, df_clients, df_prest, df_pay, df_visit, df_solic = cargar_datos_crm()
        except Exception as e:
            st.error(f"Error crítico en la conexión a base de datos: {e}")
            return

    # ==========================================
    # 3. FILTROS EN EXPANDER
    # ==========================================
    with st.expander("⚙️ Filtros Organizacionales y de Análisis", expanded=False):
        
        # --- FILA 1: JERARQUÍA ---
        col_gestor, col_cliente = st.columns(2)
        
        with col_gestor:
            lista_cobradores = df_users[df_users['rol'] == 'driver'] if 'rol' in df_users.columns else df_users
            opciones_cobrador = ["Todos los Gestores"] + lista_cobradores['nombre_completo'].dropna().tolist() if not lista_cobradores.empty else ["Todos"]
            seleccion_cobrador = st.selectbox("1. Responsable de Cartera:", opciones_cobrador)
        
        # Aplicar Filtro Gestor
        cobrador_id = None
        if seleccion_cobrador != "Todos los Gestores":
            cobrador_data = df_users[df_users['nombre_completo'] == seleccion_cobrador].iloc[0]
            cobrador_id = cobrador_data['id']
            
            if 'cobrador_id' in df_prest.columns: df_prest = df_prest[df_prest['cobrador_id'] == cobrador_id]
            if 'cobrador_id' in df_pay.columns: df_pay = df_pay[df_pay['cobrador_id'] == cobrador_id]
            if 'cobrador_id' in df_visit.columns: df_visit = df_visit[df_visit['cobrador_id'] == cobrador_id]
            if 'cobrador_id' in df_solic.columns: df_solic = df_solic[df_solic['cobrador_id'] == cobrador_id]

        with col_cliente:
            if not df_prest.empty:
                ids_clientes = df_prest['cliente_id'].unique()
                clientes_disp = df_clients[df_clients['id'].isin(ids_clientes)]
                opciones_cliente = ["Todos los Clientes"] + clientes_disp['nombre_completo'].tolist() if not clientes_disp.empty else ["Sin datos"]
            else:
                opciones_cliente = ["Sin cartera asignada"]
                
            seleccion_cliente = st.selectbox("2. Filtrar por Cliente:", opciones_cliente)

        # Aplicar Filtro Cliente
        cliente_id_sel = None
        if seleccion_cliente not in ["Todos los Clientes", "Sin cartera asignada", "Sin datos"]:
            cliente_data = df_clients[df_clients['nombre_completo'] == seleccion_cliente].iloc[0]
            cliente_id_sel = cliente_data['id']
            
            df_prest = df_prest[df_prest['cliente_id'] == cliente_id_sel]
            if 'cliente_id' in df_pay.columns: df_pay = df_pay[df_pay['cliente_id'] == cliente_id_sel]
            if 'cliente_id' in df_visit.columns: df_visit = df_visit[df_visit['cliente_id'] == cliente_id_sel]
            if 'id_cliente_existente' in df_solic.columns: df_solic = df_solic[df_solic['id_cliente_existente'] == cliente_id_sel]

        st.markdown("---")
        
        # --- FILA 2: ANÁLISIS ---
        col_filtro1, col_filtro2 = st.columns(2)
        
        estados_disponibles = df_prest['estado'].unique().tolist() if not df_prest.empty else []
        with col_filtro1:
            estados_sel = st.multiselect(
                "Estado Financiero:", 
                options=estados_disponibles, 
                default=estados_disponibles,
                help="Seleccione los estados de crédito que desea incluir en los indicadores."
            )
        
        fecha_hoy = datetime.now()
        with col_filtro2:
            rango_fechas = st.date_input(
                "Rango Temporal:", 
                [fecha_hoy - timedelta(days=30), fecha_hoy],
                help="Define el periodo para el cálculo de ingresos y préstamos otorgados."
            )

    # --- LÓGICA DE FILTRADO DE DATAFRAMES ---
    
    # 1. Filtrar Préstamos (Por Estado y Fecha Inicio)
    df_prest_filtrado = df_prest.copy()
    if estados_sel:
        df_prest_filtrado = df_prest_filtrado[df_prest_filtrado['estado'].isin(estados_sel)]
    
    if isinstance(rango_fechas, list) and len(rango_fechas) == 2:
         df_prest_filtrado['fecha_inicio'] = pd.to_datetime(df_prest_filtrado['fecha_inicio']).dt.date
         df_prest_filtrado = df_prest_filtrado[
             (df_prest_filtrado['fecha_inicio'] >= rango_fechas[0]) & 
             (df_prest_filtrado['fecha_inicio'] <= rango_fechas[1])
         ]
        
    # 2. Filtrar Pagos (Por Fecha de Pago)
    df_pay_filtrado = df_pay.copy()
    if not df_pay_filtrado.empty and 'fecha_pago' in df_pay_filtrado.columns:
        df_pay_filtrado['fecha_pago'] = pd.to_datetime(df_pay_filtrado['fecha_pago']).dt.date
        if isinstance(rango_fechas, list) and len(rango_fechas) == 2:
            df_pay_filtrado = df_pay_filtrado[
                (df_pay_filtrado['fecha_pago'] >= rango_fechas[0]) & 
                (df_pay_filtrado['fecha_pago'] <= rango_fechas[1])
            ]

    # ==========================================
    # 4. INDICADORES CLAVE (KPIs)
    # ==========================================
    st.subheader("Resumen Ejecutivo Financiero")
    
    # --- Cálculos Base ---
    saldo_visible = df_prest_filtrado['saldo_pendiente'].sum() if not df_prest_filtrado.empty else 0
    clientes_visible = df_prest_filtrado['cliente_id'].nunique()
    
    mora_visible = df_prest_filtrado[df_prest_filtrado['estado'] == 'mora']['saldo_pendiente'].sum()
    pct_mora = (mora_visible / saldo_visible * 100) if saldo_visible > 0 else 0
    
    # --- Nuevos Cálculos Financieros ---
    recaudado_visible = df_pay_filtrado['monto'].sum() if not df_pay_filtrado.empty else 0
    
    intereses_visible = 0
    flujo_neto = 0
    prestado_visible = 0

    if not df_pay_filtrado.empty and not df_prest.empty:
        # Cálculo de intereses basado en cruce
        df_kpi_pagos = df_pay_filtrado.merge(
            df_prest[['id', 'monto_prestado', 'monto_total_deuda']], 
            left_on='prestamo_id', right_on='id', how='left'
        )
        df_kpi_pagos['monto_total_deuda'] = df_kpi_pagos['monto_total_deuda'].replace(0, np.nan)
        df_kpi_pagos['pct_interes'] = (df_kpi_pagos['monto_total_deuda'] - df_kpi_pagos['monto_prestado']) / df_kpi_pagos['monto_total_deuda']
        intereses_visible = (df_kpi_pagos['monto'] * df_kpi_pagos['pct_interes']).fillna(0).sum()

    if not df_prest_filtrado.empty:
        prestado_visible = df_prest_filtrado['monto_prestado'].sum()
        
    # Flujo = Cobros Totales - Préstamos Otorgados en el periodo filtrado
    flujo_neto = recaudado_visible - prestado_visible

    # --- Renderizado de 5 Columnas ---
    k1, k2, k3, k4, k5 = st.columns(5)
    
    k1.metric(
        label="Cartera Activa", 
        value=f"C$ {saldo_visible:,.0f}",
        help=f"Distribuida en {clientes_visible} clientes."
    )
    k2.metric(
        label="Cartera Vencida (Mora)", 
        value=f"C$ {mora_visible:,.0f}",
        delta=f"{pct_mora:.1f}% del total",
        delta_color="inverse", 
        help="Monto total de créditos marcados como 'mora'."
    )
    k3.metric(
        label="Cobros Totales", 
        value=f"C$ {recaudado_visible:,.0f}",
        help="Dinero que entró en el rango de fechas seleccionado."
    )
    k4.metric(
        label="Intereses (Ganancia)", 
        value=f"C$ {intereses_visible:,.0f}",
        help="Proporción estimada de ganancia sobre los cobros realizados."
    )
    k5.metric(
        label="Flujo de Caja Neto", 
        value=f"C$ {flujo_neto:,.0f}",
        help="Cobros Totales MENOS el dinero entregado en nuevos préstamos en este periodo."
    )
    
    st.markdown("---")

    # ==========================================
    # 5. PESTAÑAS DE GESTIÓN DETALLADA
    # ==========================================
    
    # Agregamos "Configuración de Gestores" al final
    tab1, tab2, tab3, tab4 = st.tabs([
        "Análisis de Recaudación y Visitas", 
        "Detalle de Cartera de Créditos", 
        "Control de Solicitudes", 
        "Configuración de Gestores" # <--- NUEVA PESTAÑA
    ])

    # --- TAB 1: GRÁFICOS ---
    with tab1:
        st.markdown("#### Tendencia Financiera Diaria (Cobros, Intereses y Flujo)")
        
        if not df_pay_filtrado.empty and not df_prest.empty:

            # 1. CRUCE DE DATOS: Calcular el interés implícito de cada pago
            df_pagos_prestamo = df_pay_filtrado.merge(
                df_prest[['id', 'monto_prestado', 'monto_total_deuda']], 
                left_on='prestamo_id', 
                right_on='id', 
                how='left'
            )
            
            df_pagos_prestamo['monto_total_deuda'] = df_pagos_prestamo['monto_total_deuda'].replace(0, np.nan)
            df_pagos_prestamo['pct_interes'] = (df_pagos_prestamo['monto_total_deuda'] - df_pagos_prestamo['monto_prestado']) / df_pagos_prestamo['monto_total_deuda']
            df_pagos_prestamo['interes_cobrado'] = df_pagos_prestamo['monto'] * df_pagos_prestamo['pct_interes']
            df_pagos_prestamo['interes_cobrado'] = df_pagos_prestamo['interes_cobrado'].fillna(0)

            # 2. AGRUPAR INGRESOS
            trend_ingresos = df_pagos_prestamo.groupby('fecha_pago').agg(
                cobros_totales=('monto', 'sum'),
                intereses=('interes_cobrado', 'sum')
            ).reset_index()

            # 3. AGRUPAR EGRESOS
            df_prest_filtrado_fechas = df_prest_filtrado.copy()
            if 'fecha_inicio' in df_prest_filtrado_fechas.columns:
                trend_egresos = df_prest_filtrado_fechas.groupby('fecha_inicio')['monto_prestado'].sum().reset_index()
                trend_egresos.rename(columns={'fecha_inicio': 'fecha_pago'}, inplace=True)
            else:
                trend_egresos = pd.DataFrame(columns=['fecha_pago', 'monto_prestado'])

            # 4. UNIR TODO
            trend_ingresos['fecha_pago'] = pd.to_datetime(trend_ingresos['fecha_pago'])
            trend_egresos['fecha_pago'] = pd.to_datetime(trend_egresos['fecha_pago'])
            
            trend = pd.merge(trend_ingresos, trend_egresos, on='fecha_pago', how='outer').fillna(0)
            trend['resultado_dia'] = trend['cobros_totales'] - trend['monto_prestado']
            trend = trend.sort_values('fecha_pago')

            # 5. CREAR EL GRÁFICO COMBINADO
            fig_trend = go.Figure()

            fig_trend.add_trace(go.Bar(
                x=trend['fecha_pago'], y=trend['cobros_totales'],
                name='Cobros Totales', marker_color=BRAND_PRIMARY
            ))

            fig_trend.add_trace(go.Bar(
                x=trend['fecha_pago'], y=trend['intereses'],
                name='Intereses (Ganancia)', marker_color='#A5D6A7'
            ))

            fig_trend.add_trace(go.Scatter(
                x=trend['fecha_pago'], y=trend['resultado_dia'],
                name='Flujo Diario (Cobros - Préstamos)',
                mode='lines+markers',
                line=dict(color=BRAND_TEXT, width=3),
                marker=dict(size=8)
            ))

            fig_trend.update_layout(
                barmode='group',
                xaxis_title='',
                yaxis_title='Monto (C$)',
                legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
                margin=dict(t=10, b=0, l=0, r=0),
                hovermode="x unified"
            )
            
            fig_trend = aplicar_tema_plotly(fig_trend)
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.caption("🟢 **Cobros Totales:** Dinero recaudado. 🟩 **Intereses:** Porción de ganancia estimada del cobro. 🌑 **Flujo Diario:** Cobros menos los préstamos otorgados ese día.")

        else:
            st.info("No hay suficientes datos de pagos o préstamos para graficar el periodo seleccionado.")

        st.markdown("<br><hr><br>", unsafe_allow_html=True)

        # GRÁFICO INFERIOR
        col_espacio1, col_centro, col_espacio2 = st.columns([1, 2, 1])
        
        with col_centro:
            st.markdown("<h4 style='text-align: center;'>Efectividad de Visitas</h4>", unsafe_allow_html=True)
            
            if not df_visit.empty:
                df_visit['fecha'] = pd.to_datetime(df_visit['fecha']).dt.date
                if isinstance(rango_fechas, list) and len(rango_fechas) == 2:
                    df_visit = df_visit[(df_visit['fecha'] >= rango_fechas[0]) & (df_visit['fecha'] <= rango_fechas[1])]
                
                if not df_visit.empty:
                    counts = df_visit['estado_visita'].value_counts()
                    fig_pie = px.pie(
                        values=counts.values, 
                        names=counts.index, 
                        color_discrete_sequence=[BRAND_PRIMARY, BRAND_TEXT], 
                        hole=0.4
                    )
                    fig_pie = aplicar_tema_plotly(fig_pie)
                    fig_pie.update_layout(margin=dict(t=20, b=20, l=0, r=0))
                    
                    st.plotly_chart(fig_pie, use_container_width=True)
                    st.markdown("<p style='text-align: center; font-size: 0.8em; opacity: 0.8;'>Distribución porcentual según el resultado reportado en campo.</p>", unsafe_allow_html=True)
                else:
                    st.info("Sin registros de visitas en este periodo.")
            else:
                st.info("La base de datos de visitas está vacía.")

    # --- TAB 2: TABLA DE CARTERA ---
    with tab2:
        st.markdown(f"#### Inventario de Créditos ({len(df_prest_filtrado)} registros)")
        
        if not df_prest_filtrado.empty:
            df_show = df_prest_filtrado.merge(
                df_clients, left_on='cliente_id', right_on='id', 
                how='left', suffixes=('', '_cliente') 
            )
            
            st.markdown("##### Distribución del Saldo por Estado Financiero")
            df_estado = df_show.groupby('estado')['saldo_pendiente'].sum().reset_index()
            df_estado = df_estado[df_estado['saldo_pendiente'] > 0]
            
            if not df_estado.empty:
                fig_estado = px.pie(
                    df_estado, 
                    values='saldo_pendiente', 
                    names='estado',
                    hole=0.45,
                    color_discrete_sequence=[BRAND_PRIMARY, BRAND_TEXT, '#A5D6A7', '#81C784', '#388E3C'] 
                )
                
                fig_estado.update_traces(
                    textposition='inside', 
                    textinfo='percent+label',
                    hovertemplate='<b>Estado:</b> %{label}<br><b>Saldo Total:</b> C$ %{value:,.2f}<extra></extra>'
                )
                
                fig_estado.update_layout(
                    margin=dict(t=20, b=20, l=0, r=0),
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                    height=350
                )
                
                fig_estado = aplicar_tema_plotly(fig_estado)
                
                col_izq, col_graf, col_der = st.columns([1, 2, 1])
                with col_graf:
                    st.plotly_chart(fig_estado, use_container_width=True)
            else:
                st.info("No hay saldo pendiente acumulado en los registros actuales para graficar.")

            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("##### Detalle General")
            columnas_deseadas = ['id', 'nombre_completo', 'monto_prestado', 'saldo_pendiente', 'fecha_inicio', 'estado']
            cols_finales = [c for c in columnas_deseadas if c in df_show.columns]
            
            st.dataframe(
                df_show[cols_finales], 
                use_container_width=True, hide_index=True,
                column_config={
                    "id": st.column_config.TextColumn("Código", width="small"),
                    "nombre_completo": st.column_config.TextColumn("Cliente Titular"),
                    "monto_prestado": st.column_config.NumberColumn("Monto Original", format="C$ %.2f"),
                    "saldo_pendiente": st.column_config.NumberColumn("Saldo Actual", format="C$ %.2f"),
                    "fecha_inicio": st.column_config.DateColumn("Fecha Otorgamiento"),
                    "estado": st.column_config.TextColumn("Estado")
                }
            )
        else:
            st.warning("No existen créditos que coincidan con la configuración de filtros actual.")

    # --- TAB 3: SOLICITUDES ---
    with tab3:
        st.markdown("#### Bandeja de Entrada y Análisis de Solicitudes")
        
        if not df_solic.empty:
            df_sol_show = df_solic.copy()
            
            if not df_clients.empty:
                df_sol_show = df_sol_show.merge(
                    df_clients[['id', 'nombre_completo']], 
                    left_on='id_cliente_existente', right_on='id', 
                    how='left', suffixes=('', '_db')
                )
            else:
                df_sol_show['nombre_completo_db'] = None

            def normalizar_nombre(row):
                if pd.notna(row.get('nombre_completo_db')): return row['nombre_completo_db']
                datos_json = row.get('datos_nuevo_cliente')
                if datos_json and isinstance(datos_json, dict):
                    return datos_json.get('nombre_completo') or datos_json.get('nombre') or "Solicitante Nuevo"
                return "Solicitante No Identificado"

            df_sol_show['nombre_reporte'] = df_sol_show.apply(normalizar_nombre, axis=1)

            if 'fecha_solicitud' in df_sol_show.columns and isinstance(rango_fechas, list) and len(rango_fechas) == 2:
                df_sol_show['fecha_solicitud'] = pd.to_datetime(df_sol_show['fecha_solicitud']).dt.date
                df_sol_show = df_sol_show[
                    (df_sol_show['fecha_solicitud'] >= rango_fechas[0]) & 
                    (df_sol_show['fecha_solicitud'] <= rango_fechas[1])
                ]

            if not df_sol_show.empty:
                st.markdown("##### Resumen de Gestión")
                
                df_sol_show['estado'] = df_sol_show['estado'].fillna('sin_estado').str.lower()
                df_sol_show['tipo_solicitud'] = df_sol_show['tipo_solicitud'].fillna('sin_tipo')
                
                tot_sol = len(df_sol_show)
                tot_aprob = len(df_sol_show[df_sol_show['estado'] == 'aprobada'])
                tot_rech = len(df_sol_show[df_sol_show['estado'] == 'rechazada'])
                tot_pend = tot_sol - tot_aprob - tot_rech 
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Solicitudes", tot_sol)
                c2.metric("Aprobadas", tot_aprob)
                c3.metric("Rechazadas", tot_rech)
                c4.metric("Otras / Pendientes", tot_pend)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                col_graf1, col_graf2 = st.columns(2)
                
                with col_graf1:
                    st.markdown("<h6 style='text-align: center;'>Proporción por Estado</h6>", unsafe_allow_html=True)
                    df_est = df_sol_show['estado'].value_counts().reset_index()
                    df_est.columns = ['estado', 'cantidad']
                    
                    fig_est = px.pie(
                        df_est, values='cantidad', names='estado', hole=0.4,
                        color_discrete_sequence=[BRAND_PRIMARY, '#e57373', BRAND_TEXT, '#81C784']
                    )
                    fig_est.update_traces(textposition='inside', textinfo='percent+label')
                    fig_est.update_layout(margin=dict(t=10, b=10, l=0, r=0), height=300, showlegend=False)
                    fig_est = aplicar_tema_plotly(fig_est)
                    st.plotly_chart(fig_est, use_container_width=True)
                    
                with col_graf2:
                    st.markdown("<h6 style='text-align: center;'>Volumen por Tipo de Solicitud</h6>", unsafe_allow_html=True)
                    df_tip = df_sol_show['tipo_solicitud'].value_counts().reset_index()
                    df_tip.columns = ['tipo', 'cantidad']
                    
                    fig_tip = px.bar(
                        df_tip, x='tipo', y='cantidad', text_auto=True,
                        color_discrete_sequence=[BRAND_PRIMARY]
                    )
                    fig_tip.update_layout(
                        margin=dict(t=10, b=10, l=0, r=0), 
                        height=300, xaxis_title="", yaxis_title="Cantidad de Solicitudes"
                    )
                    fig_tip = aplicar_tema_plotly(fig_tip)
                    st.plotly_chart(fig_tip, use_container_width=True)

                st.markdown("<hr>", unsafe_allow_html=True)

            st.markdown("##### Detalle de Registros")
            cols_sol = ['nombre_reporte', 'monto_solicitado', 'fecha_solicitud', 'estado', 'tipo_solicitud']
            cols_finales_sol = [c for c in cols_sol if c in df_sol_show.columns]

            st.dataframe(
                df_sol_show[cols_finales_sol], 
                use_container_width=True, hide_index=True,
                column_config={
                    "nombre_reporte": st.column_config.TextColumn("Solicitante"),
                    "monto_solicitado": st.column_config.NumberColumn("Monto Solicitado", format="C$ %.2f"),
                    "fecha_solicitud": st.column_config.DateColumn("Fecha Registro"),
                    "estado": st.column_config.TextColumn("Estado Actual", width="small"),
                    "tipo_solicitud": st.column_config.TextColumn("Tipo", width="small")
                }
            )
        else:
            st.info("La bandeja de solicitudes se encuentra vacía o no hay datos para las fechas seleccionadas.")

    # --- TAB 4: CONFIGURACIÓN DE GESTORES (RUTA VERDE) ---
    with tab4:
        st.markdown("#### Configuración de Permisos")
        st.info("Activa o desactiva la capacidad de cada gestor para auto-aprobar préstamos directamente desde su dispositivo.")
        
        if not df_users.empty and 'rol' in df_users.columns:
            df_drivers = df_users[df_users['rol'] == 'driver']
            
            if not df_drivers.empty:
                col_nombre_hdr, col_toggle_hdr = st.columns([3, 1])
                col_nombre_hdr.markdown("**Nombre del Gestor**")
                col_toggle_hdr.markdown("**Permiso de Auto-Aprobación**")
                st.markdown("---")
                
                for index, row in df_drivers.iterrows():
                    estado_actual = bool(row.get('auto_aprobacion', False))
                    id_chofer = row['id']
                    nombre_chofer = row['nombre_completo']
                    toggle_key = f"toggle_{id_chofer}" 
                    
                    col_nombre, col_toggle = st.columns([3, 1])
                    
                    with col_nombre:
                        st.markdown(f"<p style='margin-top: 10px;'>{nombre_chofer}</p>", unsafe_allow_html=True)
                        
                    with col_toggle:
                        # Se utiliza el parámetro on_change con el callback definido arriba
                        st.toggle(
                            "Habilitar", 
                            value=estado_actual, 
                            key=toggle_key,
                            on_change=actualizar_permisos,
                            args=(id_chofer, toggle_key, nombre_chofer)
                        )
                    
                    st.markdown("<hr style='margin: 0px; opacity: 0.3;'>", unsafe_allow_html=True)
            else:
                st.warning("No se encontraron gestores (rol='driver') registrados en el sistema.")
        else:
            st.warning("No hay información de usuarios disponible.")