import streamlit as st
import pandas as pd
import math
import time
from db_connection import get_db_client
from datetime import date, datetime, timedelta

# ==========================================
# 0. ESTILOS CSS (DISEÑO LIMPIO Y HOMOGÉNEO)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
    /* --- ESTILOS DE TARJETAS (Mismo estilo que tu Dashboard principal) --- */
    .metric-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border: 1px solid #f0f0f0;
    }

    /* Variaciones de borde superior para diferenciar secciones */
    .card-blue {
        border-top: 4px solid #42a5f5; /* Azul suave */
    }
    .card-green {
        border-top: 4px solid #66bb6a; /* Verde suave (no saturado) */
    }

    .card-header-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #546e7a; /* Gris azulado profesional */
        margin-bottom: 15px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* --- FILAS DE INFORMACIÓN --- */
    .info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px dashed #eceff1;
    }
    .info-row:last-child {
        border-bottom: none;
    }
    .info-label {
        color: #78909c;
        font-weight: 500;
        font-size: 0.9rem;
    }
    .info-value {
        color: #263238;
        font-weight: 600;
        font-size: 0.95rem;
    }
    .value-highlight {
        color: #4CAF50;
        font-weight: 700;
        font-size: 1rem;
    }

    /* --- BOTÓN "EXTENDER" (Estilo Ghost/Outline - Menos saturado) --- */
    div[class*="st-key-btn_extend_"] button {
        background-color: #ffffff !important;
        border: 2px solid #81c784 !important; /* Borde Verde Pastel */
        color: #4CAF50 !important; /* Texto Verde Oscuro */
        font-weight: 600 !important;
        border-radius: 6px !important;
        transition: all 0.3s ease;
    }
    
    div[class*="st-key-btn_extend_"] button:hover {
        background-color: #e8f5e9 !important; /* Fondo verde muy pálido al pasar mouse */
        border-color: #4caf50 !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }

    /* --- MENSAJES VACÍOS --- */
    .empty-state {
        background-color: #f1f8e9;
        color: #558b2f;
        padding: 15px;
        border-radius: 6px;
        font-size: 0.9rem;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 0. FUNCIONES DE ACCIÓN (Lógica de DB - INTACTA)
# ==========================================
def ajustar_vencimiento_individual(prestamo_id, fecha_actual_venc):
    """
    Suma 1 día a la fecha de vencimiento en Supabase.
    """
    supabase = get_db_client()
    try:
        # Convertimos el valor actual a objeto fecha
        venc_dt = pd.to_datetime(fecha_actual_venc).date()
        # Sumamos un día y formateamos para la DB
        nueva_fecha = (venc_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Actualizamos en la tabla 'prestamos'
        supabase.table("prestamos").update({
            "fecha_vencimiento": nueva_fecha
        }).eq("id", prestamo_id).execute()
        
        return True, nueva_fecha
    except Exception as e:
        return False, str(e)

# ==========================================
# 1. CARGA DE DATOS RELACIONALES (ACTUALIZADA)
# ==========================================
def cargar_data_prestamos_full():
    supabase = get_db_client()
    
    # A. Préstamos (Al traer * ya incluye codigo_prestamo)
    r_prest = supabase.table("prestamos").select("*").execute()
    df_prest = pd.DataFrame(r_prest.data)
    
    # B. Clientes (NUEVO: Añadimos codigo_cliente a la consulta)
    r_cli = supabase.table("clientes").select("id, nombre, cedula, telefono, codigo_cliente").execute()
    df_cli = pd.DataFrame(r_cli.data)
    
    # C. Usuarios
    r_usu = supabase.table("usuarios").select("id, nombre_completo").execute()
    df_usu = pd.DataFrame(r_usu.data)
    
    # D. Pagos
    r_pagos = supabase.table("pagos").select("*").execute()
    df_pagos = pd.DataFrame(r_pagos.data)
    
    return df_prest, df_cli, df_usu, df_pagos

# ==========================================
# 2. VISTA DETALLADA
# ==========================================
def mostrar_detalle_prestamos():
    # INYECTAMOS EL CSS AL INICIO
    inject_custom_css()

    st.markdown("## Explorador de Préstamos")
    st.markdown("Visión completa de cartera, cuotas restantes e historial de pagos.")

    with st.spinner("Procesando cartera..."):
        try:
            df_prest, df_cli, df_usu, df_pagos = cargar_data_prestamos_full()
        except Exception as e:
            st.error(f"Error cargando datos: {e}")
            return

    if df_prest.empty:
        st.info("No hay préstamos registrados.")
        return

    # ==========================================
    # 3. PREPARACIÓN DE LA DATA
    # ==========================================
    
    # A. Merge con Clientes
    df_full = df_prest.merge(
        df_cli, 
        left_on='cliente_id', 
        right_on='id', 
        how='left', 
        suffixes=('', '_cli')
    )
    if 'nombre' in df_full.columns:
        df_full.rename(columns={'nombre': 'cliente_nombre'}, inplace=True)
    else:
        df_full['cliente_nombre'] = "Desconocido"

    # B. Merge con Vendedores
    df_full = df_full.merge(
        df_usu, 
        left_on='cobrador_id', 
        right_on='id', 
        how='left', 
        suffixes=('', '_vendedor')
    )
    if 'nombre_completo' in df_full.columns:
        df_full.rename(columns={'nombre_completo': 'vendedor_nombre'}, inplace=True)
    else:
        df_full['vendedor_nombre'] = "Sin asignar"

    # C. CÁLCULOS Y CONVERSIONES
    if not df_full.empty:
        # Asegurar que existan las columnas de código (por si hay registros muy antiguos)
        if 'codigo_prestamo' not in df_full.columns:
            df_full['codigo_prestamo'] = 'N/A'
        if 'codigo_cliente' not in df_full.columns:
            df_full['codigo_cliente'] = 'N/A'

        # SOLUCIÓN 1: Limpiar decimales fantasmas (.0) y forzar texto para que el buscador no falle
        df_full['codigo_prestamo'] = df_full['codigo_prestamo'].astype(str).str.replace(r'\.0$', '', regex=True)
        df_full['codigo_cliente'] = df_full['codigo_cliente'].astype(str).str.replace(r'\.0$', '', regex=True)

        df_full['saldo_pendiente'] = pd.to_numeric(df_full['saldo_pendiente'], errors='coerce').fillna(0)
        df_full['monto_cuota'] = pd.to_numeric(df_full['monto_cuota'], errors='coerce').fillna(0)
        df_full['monto_total_deuda'] = pd.to_numeric(df_full['monto_total_deuda'], errors='coerce').fillna(0)
        
        if 'fecha_inicio' in df_full.columns:
            df_full['fecha_inicio_dt'] = pd.to_datetime(df_full['fecha_inicio'], errors='coerce').dt.date
        else:
            df_full['fecha_inicio_dt'] = None

        df_full['cuotas_restantes'] = df_full.apply(
            lambda x: math.ceil(x['saldo_pendiente'] / x['monto_cuota']) if x['monto_cuota'] > 0 else 0, axis=1
        )

        df_full['pagado_acumulado'] = df_full['monto_total_deuda'] - df_full['saldo_pendiente']
        df_full['progreso'] = df_full.apply(
            lambda x: ((x['pagado_acumulado'] / x['monto_total_deuda']) * 100) if x['monto_total_deuda'] > 0 else 0.0, axis=1
        )

    # ==========================================
    # 4. FILTROS AVANZADOS (ACTUALIZADOS)
    # ==========================================
    with st.expander("🔎 Filtros de Búsqueda y Fechas", expanded=True):
        c1, c2, c3 = st.columns(3)
        # Indicamos que se puede buscar por código
        search_term = c1.text_input("Buscar (Código, Cliente o ID):")
        
        lista_vendedores = ["Todos"]
        if 'vendedor_nombre' in df_full.columns:
            lista_vendedores += df_full['vendedor_nombre'].dropna().unique().tolist()
        filtro_vendedor = c2.selectbox("Filtrar por Vendedor:", options=lista_vendedores)
        
        lista_estados = []
        if 'estado' in df_full.columns:
            lista_estados = df_full['estado'].unique().tolist()
        filtro_estado = c3.multiselect("Estado:", options=lista_estados, default=lista_estados)

        c4, c5 = st.columns([2, 1])
        # SOLUCIÓN 2: Rango de fechas por defecto a los últimos 30 días
        hoy = datetime.now().date()
        date_range = c4.date_input("📅 Rango de Fecha de Inicio:", value=(hoy - timedelta(days=30), hoy), help="Selecciona una fecha inicio y fin.")
        ocultar_pagados = c5.toggle("Ocultar pagados (Saldo 0)", value=False)

    # --- APLICACIÓN DE FILTROS ---
    df_view = df_full.copy()
    if search_term:
        term = search_term.lower()
        # Permitimos que el buscador lea código de préstamo y de cliente
        df_view = df_view[
            df_view['cliente_nombre'].astype(str).str.lower().str.contains(term, na=False) |
            df_view['codigo_prestamo'].astype(str).str.lower().str.contains(term, na=False) |
            df_view['codigo_cliente'].astype(str).str.lower().str.contains(term, na=False) |
            df_view['id'].astype(str).str.lower().str.contains(term, na=False)
        ]
    if filtro_vendedor != "Todos":
        df_view = df_view[df_view['vendedor_nombre'] == filtro_vendedor]
    if filtro_estado:
        df_view = df_view[df_view['estado'].isin(filtro_estado)]
    if ocultar_pagados:
        df_view = df_view[df_view['saldo_pendiente'] > 0]
    if len(date_range) == 2:
        start_date, end_date = date_range
        df_view = df_view[(df_view['fecha_inicio_dt'] >= start_date) & (df_view['fecha_inicio_dt'] <= end_date)]

    # ==========================================
    # 5. TABLA PRINCIPAL (ACTUALIZADA)
    # ==========================================
    st.markdown(f"### 📋 Listado ({len(df_view)} préstamos encontrados)")
    
    # Reemplazamos las columnas de UUIDs feos por los Códigos
    column_config = {
        "codigo_prestamo": st.column_config.TextColumn("Cód. Préstamo", width="small"),
        "codigo_cliente": st.column_config.TextColumn("Cód. Cliente", width="small"),
        # SOLUCIÓN 3: Agregamos la columna de fecha a la configuración
        "fecha_inicio_dt": st.column_config.DateColumn("Fecha Préstamo", format="DD/MM/YYYY"),
        "cliente_nombre": st.column_config.TextColumn("Cliente", width="medium"),
        "vendedor_nombre": st.column_config.TextColumn("Vendedor", width="medium"),
        "estado": st.column_config.TextColumn("Estado"),
        "monto_total_deuda": st.column_config.NumberColumn("Deuda Total", format="C$ %.2f"),
        "saldo_pendiente": st.column_config.NumberColumn("Saldo Actual", format="C$ %.2f"),
        "cuotas_restantes": st.column_config.NumberColumn("Cuotas Faltan"),
        "progreso": st.column_config.ProgressColumn("Progreso Pago", format="%.0f%%", min_value=0, max_value=100),
    }
    
    # Incluimos 'fecha_inicio_dt' en las columnas visibles
    cols_to_show = ['codigo_prestamo', 'codigo_cliente', 'fecha_inicio_dt', 'cliente_nombre', 'vendedor_nombre', 'estado', 'monto_total_deuda', 'saldo_pendiente', 'cuotas_restantes', 'progreso']
    cols_finales = [c for c in cols_to_show if c in df_view.columns]

    event = st.dataframe(
        df_view[cols_finales],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun", 
        selection_mode="single-row" 
    )

    # ==========================================
    # 6. DETALLE (DRILL-DOWN) + AJUSTE DE FECHA
    # ==========================================
    if event.selection.rows:
        index_seleccionado = event.selection.rows[0]
        row_data = df_view.iloc[index_seleccionado]
        
        # Guardamos el ID real de la base de datos para la lógica (ajuste de fecha, buscar pagos, etc.)
        id_prestamo_sel = row_data['id'] 
        
        # Obtenemos los códigos para mostrarlos en pantalla
        codigo_prest_sel = row_data.get('codigo_prestamo', 'N/A')
        codigo_cli_sel = row_data.get('codigo_cliente', 'N/A')
        cliente_sel = row_data['cliente_nombre']
        fecha_venc_actual = row_data.get('fecha_vencimiento', 'N/A')
        
        st.write("") 
        st.divider()
        # Mostramos el código del préstamo en el título principal
        st.markdown(f"### 👤 Gestión del Préstamo: **{codigo_prest_sel}** | {cliente_sel}")
        
        pagos_asociados = df_pagos[df_pagos['prestamo_id'] == id_prestamo_sel].copy()
        
        c1, c2 = st.columns([1, 2], gap="large")
        
        with c1:
            # --- TARJETA 1: DATOS OPERATIVOS (ACTUALIZADA) ---
            st.markdown(f"""
            <div class="metric-card card-blue">
                <div class="card-header-title">Resumen Operativo</div>
                <div class="info-row">
                    <span class="info-label">Cód. Préstamo</span>
                    <span class="info-value">{codigo_prest_sel}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Cód. Cliente</span>
                    <span class="info-value">{codigo_cli_sel}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha Inicio</span>
                    <span class="info-value">{row_data.get('fecha_inicio', 'N/A')}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Vencimiento</span>
                    <span class="info-value">{fecha_venc_actual}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Cuota Diaria</span>
                    <span class="info-value">C$ {row_data.get('monto_cuota', 0):,.2f}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Total Pagado</span>
                    <span class="value-highlight">C$ {row_data.get('pagado_acumulado', 0):,.2f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # --- SECCIÓN DE ACCIÓN ---
            st.markdown("##### Ajuste Rápido")
            st.caption("Extensión administrativa de 24 horas.")
            
            if st.button("➕ Extender Plazo (+1 Día)", 
                         key=f"btn_extend_{id_prestamo_sel}", 
                         type="primary", 
                         use_container_width=True):
                if fecha_venc_actual != 'N/A':
                    with st.spinner("⏳ Actualizando calendario..."):
                        exito, resultado = ajustar_vencimiento_individual(id_prestamo_sel, fecha_venc_actual)
                        if exito:
                            st.success(f"✅ Nuevo vencimiento: {resultado}")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"❌ Error: {resultado}")
                else:
                    st.error("Fecha inválida.")

        with c2:
            # --- TARJETA 2: BITÁCORA ---
            st.markdown("""
            <div class="metric-card card-green" style="padding-bottom: 5px;">
                <div class="card-header-title">Bitácora de Pagos</div>
            </div>
            """, unsafe_allow_html=True)

            if not pagos_asociados.empty:
                if 'fecha_pago' in pagos_asociados.columns:
                    pagos_asociados['fecha_pago'] = pd.to_datetime(pagos_asociados['fecha_pago'])
                    pagos_asociados = pagos_asociados.sort_values(by='fecha_pago', ascending=False)
                
                st.dataframe(
                    pagos_asociados[['fecha_pago', 'monto', 'fecha_hora']],
                    column_config={
                        "fecha_pago": st.column_config.DateColumn("Fecha Pago"),
                        "monto": st.column_config.NumberColumn("Monto Abonado", format="C$ %.2f"),
                        "fecha_hora": st.column_config.DatetimeColumn("Registro Sistema", format="D MMM YYYY, h:mm a")
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=350 
                )
            else:
                st.markdown("""
                <div class="empty-state">
                    ℹ️ Este préstamo no tiene pagos registrados en el sistema todavía.
                </div>
                """, unsafe_allow_html=True)