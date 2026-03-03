import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from db_connection import get_db_client

# ==========================================
# 1. CARGA DE DATOS (VALIDADA Y SEGURA)
# ==========================================
@st.cache_data(ttl=60)
def cargar_datos_inteligentes():
    supabase = get_db_client()
    
    # AJUSTE MATEMÁTICO: Ventana de 365 días para contexto histórico
    fecha_limite = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    # A. PAGOS
    r_pagos = supabase.table("pagos").select("id, prestamo_id, cobrador_id, monto, fecha_pago").gte("fecha_pago", fecha_limite).execute()
    
    # B. PRÉSTAMOS
    r_prestamos = supabase.table("prestamos").select(
        "id, cliente_id, cobrador_id, monto_prestado, monto_total_deuda, saldo_pendiente, estado, fecha_inicio"
    ).execute()
    
    # C. VISITAS
    r_visitas = supabase.table("bitacora_visitas").select("*").gte("fecha", fecha_limite).execute()
    
    # D. MOVIMIENTOS CAJA
    r_caja = supabase.table("movimientos_caja").select("*").gte("fecha", fecha_limite).execute()

    # E. USUARIOS
    r_usuarios = supabase.table("usuarios").select("id, nombre_completo").execute()

    # F. CLIENTES (NUEVO)
    r_clientes = supabase.table("clientes").select("id, nombre").execute()

    # --- DATAFRAMES Y LIMPIEZA ---
    df_pagos = pd.DataFrame(r_pagos.data) if r_pagos.data else pd.DataFrame()
    df_prestamos = pd.DataFrame(r_prestamos.data) if r_prestamos.data else pd.DataFrame()
    df_visitas = pd.DataFrame(r_visitas.data) if r_visitas.data else pd.DataFrame()
    df_caja = pd.DataFrame(r_caja.data) if r_caja.data else pd.DataFrame()
    
    # Mapeo Nombres
    mapa_usuarios = {u['id']: u['nombre_completo'] for u in r_usuarios.data} if r_usuarios.data else {}
    mapa_clientes = {c['id']: c.get('nombre', 'Desconocido') for c in r_clientes.data} if r_clientes.data else {}

    if not df_pagos.empty: 
        df_pagos['nombre_cobrador'] = df_pagos['cobrador_id'].map(mapa_usuarios).fillna('Desconocido')
    if not df_visitas.empty: 
        df_visitas['nombre_cobrador'] = df_visitas['cobrador_id'].map(mapa_usuarios).fillna('Desconocido')
    if not df_prestamos.empty:
        df_prestamos['nombre_cobrador'] = df_prestamos['cobrador_id'].map(mapa_usuarios).fillna('Sin Asignar')
        # Cruce de clientes
        df_prestamos['nombre_cliente'] = df_prestamos['cliente_id'].map(mapa_clientes).fillna('Cliente Desconocido')
        
    if not df_caja.empty and 'usuario_id' in df_caja.columns:
        # Crucial para el gráfico: mapear a quién se le dio el capital desde la caja
        df_caja['nombre_cobrador'] = df_caja['usuario_id'].map(mapa_usuarios).fillna('Desconocido')

    # Devolvemos mapa_clientes también
    return df_pagos, df_prestamos, df_visitas, df_caja, mapa_usuarios, mapa_clientes

# ==========================================
# 2. LÓGICA FINANCIERA
# ==========================================
def calcular_kpis_financieros(df_pagos, df_prestamos, df_caja):
    if df_pagos.empty or df_prestamos.empty:
        return 0, 0, 0, 0

    monto_deuda = df_prestamos['monto_total_deuda'].fillna(0)
    monto_prestado = df_prestamos['monto_prestado'].fillna(0)
    
    # Cálculo del margen de ganancia por préstamo individual
    df_prestamos['margen'] = ((monto_deuda - monto_prestado) / monto_deuda.replace(0, 1)).fillna(0)
    
    # Cruce de pagos con el margen del préstamo asociado
    df_merge = pd.merge(df_pagos, df_prestamos[['id', 'margen']], left_on='prestamo_id', right_on='id', how='left')
    df_merge['margen'] = df_merge['margen'].fillna(0)
    
    # Separación: Cuánto del pago es retorno de capital y cuánto es ganancia (interés)
    df_merge['ganancia_interes'] = df_merge['monto'] * df_merge['margen']
    
    ganancia_bruta = df_merge['ganancia_interes'].sum()
    recaudado_total = df_merge['monto'].sum()

    gastos_operativos = 0
    if not df_caja.empty:
        # Filtro estricto de salidas de dinero operativas
        tipos_gasto = ['pago_nomina', 'egreso', 'otros'] 
        
        # CORRECCIÓN DE SEGURIDAD: Usamos abs() para asegurar que los gastos siempre sean 
        # un número positivo (magnitud) y así la resta de la utilidad funcione perfecto siempre.
        gastos_operativos = abs(df_caja[df_caja['tipo'].isin(tipos_gasto)]['monto'].sum())

    # La fórmula ahora siempre restará correctamente
    utilidad_neta = ganancia_bruta - gastos_operativos
    return recaudado_total, ganancia_bruta, gastos_operativos, utilidad_neta

# ==========================================
# 3. INTERFAZ PROFESIONAL
# ==========================================
def mostrar_dashboard():
    # Encabezado sobrio
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown("## Tablero de Control Administrativo")
        st.markdown("Monitor de rendimiento financiero y operativo.")
    with col_h2:
        st.markdown(f"**Fecha de Corte:** {datetime.now().strftime('%d/%m/%Y')}")
    
    with st.spinner("Procesando base de datos..."):
        try:
            # Recibimos el mapa_clientes aquí
            raw_pagos, raw_prestamos, raw_visitas, raw_caja, mapa_users, mapa_clientes = cargar_datos_inteligentes()
        except Exception as e:
            st.error(f"Error de conexión: {e}")
            return

    # --- SECCIÓN DE FILTROS OCULTABLE ---
    with st.expander("⚙️ Configuración de Análisis (Filtros)", expanded=False):
        col_f1, col_f2 = st.columns(2)
        hoy = datetime.now().date()
        with col_f1:
            rango = st.date_input("Seleccione Rango de Fechas", value=(hoy - timedelta(days=30), hoy), max_value=hoy)
            f_ini, f_fin = (rango[0], rango[1]) if isinstance(rango, tuple) and len(rango)==2 else (hoy, hoy)
            st.caption("Nota: Este filtro afecta los cálculos de ingresos, gastos y visitas.")
        with col_f2:
            sel_cobrador = st.selectbox("Filtrar por Personal", ["Todos"] + list(mapa_users.values()))
            st.caption("Nota: Permite aislar el rendimiento individual por cobrador.")

    # --- FILTRADO DE DATAFRAMES ---
    df_p = raw_pagos.copy()
    if not df_p.empty:
        df_p['fecha_pago'] = pd.to_datetime(df_p['fecha_pago']).dt.date
        df_p = df_p[(df_p['fecha_pago'] >= f_ini) & (df_p['fecha_pago'] <= f_fin)]
    
    df_c = raw_caja.copy()
    if not df_c.empty:
        df_c['fecha'] = pd.to_datetime(df_c['fecha']).dt.date
        df_c = df_c[(df_c['fecha'] >= f_ini) & (df_c['fecha'] <= f_fin)]

    if sel_cobrador != "Todos":
        df_p = df_p[df_p['nombre_cobrador'] == sel_cobrador]

    # --- PESTAÑAS DE NAVEGACIÓN ---
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["Rentabilidad Financiera", "Eficiencia Operativa", "Análisis de Riesgo"])

    # 1. RENTABILIDAD FINANCIERA
    with tab1:
        recaudado, ganancia_bruta, gastos, utilidad = calcular_kpis_financieros(df_p, raw_prestamos, df_c)
        
        with st.container(border=True):
            st.markdown("#### Estado de Resultados (Periodo Seleccionado)")
            c1, c2, c3, c4 = st.columns(4)
            
            c1.metric(
                "Ingresos Totales (Caja)", 
                f"C$ {recaudado:,.0f}", 
                help="Suma total del dinero físico recolectado en pagos durante el rango de fechas seleccionado. Fuente: Tabla 'pagos'."
            )
            c2.metric(
                "Margen Bruto (Intereses)", 
                f"C$ {ganancia_bruta:,.0f}", 
                help="Porción del ingreso que corresponde a ganancia (excluyendo retorno de capital prestado). Cálculo: Pago * % Interés del préstamo."
            )
            c3.metric(
                "Gastos Operativos", 
                f"C$ {gastos:,.0f}", 
                delta=-gastos, 
                delta_color="inverse",
                help="Salidas de dinero registradas como nómina, egresos administrativos u otros gastos. Fuente: Tabla 'movimientos_caja'."
            )
            c4.metric(
                "Utilidad Neta", 
                f"C$ {utilidad:,.0f}", 
                delta="Positivo" if utilidad > 0 else "Negativo", 
                delta_color="normal" if utilidad > 0 else "inverse",
                help="Resultado final: Margen Bruto menos Gastos Operativos. Representa la ganancia real limpia del negocio."
            )

        st.markdown("##### Análisis de Flujo")
        
        # CORRECCIÓN GRÁFICA: Obligamos a que el valor del gasto sea estrictamente negativo para la gráfica
        gasto_grafico = -abs(gastos)
        
        fig = go.Figure(go.Waterfall(
            name = "Flujo", orientation = "v",
            measure = ["relative", "relative", "total"],
            x = ["Ganancia Bruta", "Gastos Operativos", "Utilidad Neta"],
            text = [f"+{ganancia_bruta:,.0f}", f"{gasto_grafico:,.0f}", f"={utilidad:,.0f}"],
            textposition = "auto",
            y = [ganancia_bruta, gasto_grafico, utilidad],
            connector = {"line":{"color":"#636363"}},
            decreasing = {"marker":{"color":"#D32F2F"}}, # El gasto saldrá rojo 
            increasing = {"marker":{"color":"#538E38"}}, 
            totals = {"marker":{"color":"#407AE7"}}      
        ))
        fig.update_layout(height=350, margin=dict(t=20,b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Interpretación Gráfica: Muestra cómo los gastos reducen la ganancia bruta para llegar a la utilidad final disponible.")

    # 2. EFICIENCIA OPERATIVA
    with tab2:
        df_v = raw_visitas.copy()
        if not df_v.empty:
            df_v['fecha'] = pd.to_datetime(df_v['fecha']).dt.date
            df_v = df_v[(df_v['fecha'] >= f_ini) & (df_v['fecha'] <= f_fin)]
            if sel_cobrador != "Todos":
                df_v = df_v[df_v['nombre_cobrador'] == sel_cobrador]

        total_visitas = len(df_v)
        efectivas = len(df_v[df_v['estado_visita'] == 'Pagado']) if not df_v.empty else 0
        porc = (efectivas / total_visitas * 100) if total_visitas > 0 else 0
        
        with st.container(border=True):
            st.markdown("#### Resumen de Campo")
            k1, k2 = st.columns(2)
            k1.metric(
                "Visitas Totales", 
                total_visitas,
                help="Número total de registros en la bitácora de visitas durante el periodo seleccionado."
            )
            k2.metric(
                "Tasa de Conversión (Cobro)", 
                f"{porc:.1f}%",
                help="Indicador de productividad: (Visitas con pago / Total visitas) * 100."
            )

            col_graph, col_info = st.columns([2,1])
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
                    st.caption("Visualización de la efectividad del personal en campo.")
                else:
                    st.info("No existen registros de visitas en el rango de fechas seleccionado.")
            
            with col_info:
                st.markdown("<br><br>", unsafe_allow_html=True)
                st.markdown("#### Glosario de Métricas")
                st.info("""
                **Tasa de Conversión:** Mide qué porcentaje de las visitas generaron ingreso real. 
                
                Un porcentaje bajo sugiere problemas en la ruta de cobro o insolvencia de los clientes visitados.
                """)

        # --- SECCIÓN: CAPITAL ASIGNADO VS COLOCADO ---
        st.markdown("---")
        st.markdown("#### Colocación de Capital por Vendedor")
        st.caption("Análisis del capital entregado desde caja (Fondo Operativo) vs el capital colocado en préstamos durante el rango de fechas seleccionado.")
        
        todos_vendedores = list(mapa_users.values())
        vendedores_seleccionados = st.multiselect(
            "Marcar Vendedores a comparar:", 
            options=todos_vendedores, 
            default=todos_vendedores if len(todos_vendedores) <= 5 else todos_vendedores[:5],
            help="Selecciona los vendedores que deseas analizar en el gráfico inferior."
        )

        if vendedores_seleccionados:
            df_prestamos_filtro = raw_prestamos.copy()
            if not df_prestamos_filtro.empty:
                df_prestamos_filtro['fecha_inicio'] = pd.to_datetime(df_prestamos_filtro['fecha_inicio']).dt.date
                df_prestamos_filtro = df_prestamos_filtro[(df_prestamos_filtro['fecha_inicio'] >= f_ini) & (df_prestamos_filtro['fecha_inicio'] <= f_fin)]
                df_prestamos_filtro = df_prestamos_filtro[df_prestamos_filtro['nombre_cobrador'].isin(vendedores_seleccionados)]
                
            df_colocado = pd.DataFrame(columns=['nombre_cobrador', 'Capital Colocado'])
            if not df_prestamos_filtro.empty:
                df_colocado = df_prestamos_filtro.groupby('nombre_cobrador')['monto_prestado'].sum().reset_index()
                df_colocado.rename(columns={'monto_prestado': 'Capital Colocado'}, inplace=True)
            
            df_asignado = pd.DataFrame(columns=['nombre_cobrador', 'Capital Asignado'])
            if not df_c.empty and 'tipo' in df_c.columns:
                df_entregas = df_c[(df_c['tipo'] == 'entrega_capital') & (df_c['nombre_cobrador'].isin(vendedores_seleccionados))]
                if not df_entregas.empty:
                    df_asignado = df_entregas.groupby('nombre_cobrador')['monto'].sum().reset_index()
                    df_asignado.rename(columns={'monto': 'Capital Asignado'}, inplace=True)
            
            df_capital = pd.merge(df_colocado, df_asignado, on='nombre_cobrador', how='outer').fillna(0)

            if not df_capital.empty and (df_capital['Capital Colocado'].sum() > 0 or df_capital['Capital Asignado'].sum() > 0):
                df_melted = df_capital.melt(id_vars='nombre_cobrador', 
                                            value_vars=['Capital Asignado', 'Capital Colocado'], 
                                            var_name='Tipo', 
                                            value_name='Monto (C$)')

                fig_barras = px.bar(
                    df_melted, 
                    x='nombre_cobrador', 
                    y='Monto (C$)', 
                    color='Tipo', 
                    barmode='group',
                    text_auto='.2s',
                    color_discrete_map={
                        'Capital Asignado': '#1E88E5', 
                        'Capital Colocado': '#43A047'  
                    }
                )
                
                fig_barras.update_layout(
                    xaxis_title="Personal Asignado", 
                    yaxis_title="Monto (C$)",
                    legend_title="",
                    margin=dict(t=20, b=20),
                    height=400
                )
                
                st.plotly_chart(fig_barras, use_container_width=True)
                st.caption("El gráfico ayuda a identificar qué porcentaje del fondo operativo está siendo efectivamente colocado en nuevos préstamos por cada vendedor.")
            else:
                st.warning("No hay entregas de capital ni nuevos préstamos registrados para los vendedores seleccionados en las fechas indicadas.")
        else:
            st.info("👆 Selecciona al menos un vendedor en la lista superior para ver la comparativa.")

    # 3. ANÁLISIS DE RIESGO
    with tab3:
        st.warning("Nota Técnica: Los datos mostrados a continuación corresponden al estado actual de la cartera (Acumulado Histórico) y no se ven afectados por el filtro de fechas.")
        
        df_loans = raw_prestamos.copy()
        if sel_cobrador != "Todos":
            df_loans = df_loans[df_loans['nombre_cobrador'] == sel_cobrador]
            
        # ==========================================
        # FILTRO POR CLIENTE
        # ==========================================
        if not df_loans.empty:
            lista_clientes = ["Todos los Clientes"] + sorted(df_loans['nombre_cliente'].unique().tolist())
            sel_cliente = st.selectbox("🔍 Analizar un cliente específico:", lista_clientes)
            
            if sel_cliente != "Todos los Clientes":
                df_loans = df_loans[df_loans['nombre_cliente'] == sel_cliente]
                
            st.markdown("---")
            
        if not df_loans.empty:
            total_calle = df_loans['saldo_pendiente'].sum()
            total_mora = df_loans[df_loans['estado'] == 'mora']['saldo_pendiente'].sum()
            indice_mora = (total_mora / total_calle * 100) if total_calle > 0 else 0
            
            with st.container(border=True):
                m1, m2, m3 = st.columns(3)
                m1.metric(
                    "Saldo Total en Calle", 
                    f"C$ {total_calle:,.0f}",
                    help="Suma total de los saldos pendientes de todos los préstamos activos (Capital + Intereses por cobrar)."
                )
                m2.metric(
                    "Cartera Vencida (Mora)", 
                    f"C$ {total_mora:,.0f}", 
                    delta_color="inverse",
                    help="Suma de saldos pendientes de préstamos marcados con estado 'mora'."
                )
                m3.metric(
                    "Índice de Morosidad", 
                    f"{indice_mora:.1f}%", 
                    delta="Alto Riesgo" if indice_mora > 20 else "Saludable", 
                    delta_color="inverse",
                    help="Relación porcentual: (Cartera Vencida / Saldo Total) * 100. Indica la salud financiera de la cartera."
                )
            
            st.subheader("Top 15 Clientes con Mayor Deuda Vencida")
            morosos = df_loans[df_loans['estado'] == 'mora'].sort_values('saldo_pendiente', ascending=False).head(15)
            
            if not morosos.empty:
                st.dataframe(
                    morosos[['nombre_cliente', 'nombre_cobrador', 'fecha_inicio', 'monto_prestado', 'saldo_pendiente']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "nombre_cliente": "Cliente Titular",
                        "nombre_cobrador": "Cobrador Asignado",
                        "fecha_inicio": st.column_config.DateColumn("Fecha Préstamo", format="DD/MM/YYYY"),
                        "monto_prestado": st.column_config.NumberColumn("Monto Original", format="C$ %.2f"),
                        "saldo_pendiente": st.column_config.NumberColumn("Saldo Deudor", format="C$ %.2f"),
                    }
                )
                st.caption("Esta tabla muestra los clientes con estado 'mora' ordenados por el monto que deben actualmente.")
            else:
                st.success("Cartera saludable: No se registran clientes en estado de mora con los filtros actuales.")
        else:
            st.warning("No hay préstamos activos registrados que coincidan con los filtros seleccionados.")