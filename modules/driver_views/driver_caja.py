import streamlit as st
import pandas as pd
from datetime import datetime, date
from db_connection import get_db_client

# ==========================================
# 1. LOGICA DE DATOS (INTACTA)
# ==========================================
def cargar_historial_unificado(usuario_id):
    """
    Consulta las 3 fuentes de dinero, normaliza y ordena.
    """
    supabase = get_db_client()
    lista_maestra = []

    try:
        # 1. MOVIMIENTOS ADMIN
        resp_admin = supabase.table("movimientos_caja")\
            .select("fecha, tipo, monto, descripcion")\
            .eq("usuario_id", usuario_id)\
            .order("fecha", desc=True).limit(50).execute()
        
        for m in resp_admin.data:
            es_ingreso = m['monto'] > 0
            lista_maestra.append({
                "fecha_raw": m['fecha'], 
                "tipo": "ADMIN",
                "titulo": "Fondos Recibido" if es_ingreso else "Cierre/Retiro",
                "subtitulo": m.get('descripcion', 'Admin'),
                "monto": m['monto'],
                "icono": "🏦",
                "clase": "positivo" if es_ingreso else "negativo"
            })

        # 2. COBROS
        resp_pagos = supabase.table("pagos")\
            .select("fecha_hora, monto, clientes(nombre)")\
            .eq("cobrador_id", usuario_id)\
            .order("fecha_hora", desc=True).limit(50).execute()
        
        for p in resp_pagos.data:
            cliente_nom = p['clientes']['nombre'] if p['clientes'] else "Cliente"
            lista_maestra.append({
                "fecha_raw": p['fecha_hora'],
                "tipo": "COBRO",
                "titulo": "Cobro Realizado",
                "subtitulo": cliente_nom,
                "monto": abs(p['monto']),
                "icono": "💰",
                "clase": "positivo"
            })

        # 3. PRÉSTAMOS
        resp_prestamos = supabase.table("prestamos")\
            .select("fecha_inicio, monto_prestado, clientes(nombre)")\
            .eq("cobrador_id", usuario_id)\
            .order("fecha_inicio", desc=True).limit(50).execute()
        
        for pr in resp_prestamos.data:
            cliente_nom = pr['clientes']['nombre'] if pr['clientes'] else "Cliente"
            fecha_iso = f"{pr['fecha_inicio']}T12:00:00"
            
            lista_maestra.append({
                "fecha_raw": fecha_iso,
                "tipo": "PRESTAMO",
                "titulo": "Préstamo Nuevo",
                "subtitulo": cliente_nom,
                "monto": -abs(pr['monto_prestado']),
                "icono": "💸",
                "clase": "negativo"
            })

        # Ordenar
        lista_maestra.sort(key=lambda x: x['fecha_raw'], reverse=True)
        return lista_maestra

    except Exception as e:
        st.error(f"Error historial: {e}")
        return []

def get_fecha_etiqueta(fecha_str):
    """Devuelve 'HOY', 'AYER' o la fecha formateada"""
    try:
        dt = datetime.fromisoformat(fecha_str.replace('Z', ''))
        hoy = datetime.now().date()
        fecha_dato = dt.date()
        
        if fecha_dato == hoy:
            return "HOY"
        elif (hoy - fecha_dato).days == 1:
            return "AYER"
        else:
            return fecha_dato.strftime("%d/%m/%Y")
    except:
        return fecha_str[:10]

def check_fecha_coincide(fecha_raw, fecha_filtro):
    """Auxiliar para comparar fecha raw con objeto date del filtro"""
    try:
        dt = datetime.fromisoformat(fecha_raw.replace('Z', '')).date()
        return dt == fecha_filtro
    except:
        return False

# ==========================================
# 2. VISTA (REDISEÑADA)
# ==========================================
def mostrar_caja_driver(usuario_id):
    # --- CSS FINTECH MODERNO ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* Variables base */
        :root {
            --primary: #4CAF50;
            --bg-main: #F7F3E9;
            --bg-sec: #E6F4EA;
            --text-dark: #0F3D3E;
            --text-grey: #64748B;
            --white: #FFFFFF;
            --radius: 16px;
        }

        .stApp {
            background-color: var(--bg-main);
            font-family: 'Inter', sans-serif;
            color: var(--text-dark);
        }

        /* 1. Tarjeta de Saldo */
        .balance-card {
            background: linear-gradient(135deg, #4CAF50 0%, #4CAF50 100%);
            color: white;
            padding: 24px;
            border-radius: var(--radius);
            box-shadow: 0 10px 25px rgba(76, 175, 80, 0.25);
            text-align: center;
            margin-bottom: 24px;
            position: relative;
        }
        .balance-label {
            font-size: 13px; font-weight: 500; opacity: 0.9;
            letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;
        }
        .balance-amount {
            font-size: 42px; font-weight: 800; letter-spacing: -1px;
        }
        
        /* 2. Resumen Métricas */
        .metric-card {
            background: var(--white);
            border-radius: var(--radius);
            padding: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.03);
            border: 1px solid rgba(0,0,0,0.04);
            text-align: left;
            transition: transform 0.2s;
            height: 100%; /* Asegura altura completa en la columna */
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .metric-card:hover { transform: translateY(-2px); }
        .metric-title { font-size: 11px; color: var(--text-grey); font-weight: 600; text-transform: uppercase; margin-bottom: 6px; }
        .metric-value { font-size: 18px; font-weight: 700; }
        .val-pos { color: var(--primary); }
        .val-neg { color: #D32F2F; }

        /* 3. Filtros y Date Input */
        div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
            background-color: var(--bg-sec) !important;
            border-radius: 12px !important;
            border: none !important;
            color: var(--text-dark) !important;
            font-weight: 500;
        }
        /* Ajuste específico para el input de fecha para que parezca selectbox */
        div[data-testid="stDateInput"] > label { display: none; }

        /* 4. Lista de Transacciones */
        .tx-list { display: flex; flex-direction: column; gap: 12px; }
        .tx-card {
            background: var(--white);
            border-radius: var(--radius);
            padding: 16px;
            display: flex; align-items: center; justify-content: space-between;
            box-shadow: 0 2px 8px rgba(0,0,0,0.03);
            border: 1px solid rgba(0,0,0,0.02);
            transition: all 0.2s ease;
        }
        .tx-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
        .tx-left { display: flex; align-items: center; gap: 14px; }
        .tx-icon-box {
            width: 44px; height: 44px; border-radius: 50%;
            background-color: var(--bg-sec);
            display: flex; align-items: center; justify-content: center;
            font-size: 20px;
        }
        .tx-details { display: flex; flex-direction: column; }
        .tx-title { font-size: 14px; font-weight: 700; color: var(--text-dark); margin-bottom: 2px; }
        .tx-sub { font-size: 12px; color: var(--text-grey); font-weight: 500; }
        .tx-amount { font-size: 16px; font-weight: 700; text-align: right; }
        
        /* 5. Headers de Fecha */
        .date-badge {
            display: inline-block; background-color: #E0E0E0; color: #424242;
            padding: 6px 14px; border-radius: 20px;
            font-size: 11px; font-weight: 700; text-transform: uppercase;
            margin: 20px 0 10px 0; opacity: 0.8;
        }

        /* Botón de recarga */
        div.stButton > button {
            background-color: var(--white);
            color: var(--text-dark);
            border: 1px solid rgba(0,0,0,0.1);
            border-radius: 12px;
            height: 46px; /* Altura fija para alineación */
            width: 100%;
        }
        div.stButton > button:hover {
            border-color: var(--primary); color: var(--primary);
        }
        </style>
    """, unsafe_allow_html=True)

    st.subheader("🏦 Mi Bóveda")
    
    supabase = get_db_client()

    # 1. SALDO GRANDE
    try:
        resp = supabase.table("usuarios").select("saldo_actual").eq("id", usuario_id).single().execute()
        saldo = float(resp.data.get("saldo_actual", 0.0))
    except:
        saldo = 0.0

    st.markdown(f"""
        <div class="balance-card">
            <div class="balance-label">Efectivo Disponible</div>
            <div class="balance-amount">C$ {saldo:,.2f}</div>
        </div>
    """, unsafe_allow_html=True)

    # Cargar datos base
    historial_completo = cargar_historial_unificado(usuario_id)

    # 2. RESUMEN RÁPIDO Y BOTÓN (Alineados verticalmente al centro)
    cobrado_hoy = sum(h['monto'] for h in historial_completo if h['monto'] > 0 and get_fecha_etiqueta(h['fecha_raw']) == "HOY" and h['tipo'] == 'COBRO')
    prestado_hoy = sum(h['monto'] for h in historial_completo if h['monto'] < 0 and get_fecha_etiqueta(h['fecha_raw']) == "HOY" and h['tipo'] == 'PRESTAMO')

    # CORRECCIÓN DE ALINEACIÓN: vertical_alignment="center"
    col1, col2, col3 = st.columns([1, 1, 0.25], vertical_alignment="center")
    
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Cobrado Hoy</div>
                <div class="metric-value val-pos">+ C$ {cobrado_hoy:,.0f}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Prestado Hoy</div>
                <div class="metric-value val-neg">C$ {prestado_hoy:,.0f}</div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        # El botón ahora estará centrado verticalmente respecto a las tarjetas
        if st.button("🔄", help="Actualizar Saldos"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # 3. FILTROS CON CALENDARIO
    col_filtro_1, col_filtro_2 = st.columns(2)
    
    with col_filtro_1:
        filtro_tipo = st.selectbox(
            "Tipo de movimiento",
            ["Todos", "💰 Cobros", "💸 Préstamos", "🏦 Admin"],
            label_visibility="collapsed"
        )
    
    with col_filtro_2:
        # Agregamos opción de Calendario
        opciones_tiempo = ["Todo el historial", "📅 Solo Hoy", "⏮️ Solo Ayer", "📆 Seleccionar Fecha"]
        filtro_tiempo = st.selectbox(
            "Periodo",
            opciones_tiempo,
            label_visibility="collapsed"
        )

    # Lógica para mostrar el DatePicker si se selecciona la opción
    fecha_seleccionada = None
    if filtro_tiempo == "📆 Seleccionar Fecha":
        st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
        fecha_seleccionada = st.date_input("Selecciona la fecha", value="today", label_visibility="collapsed")

    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    # 4. APLICACIÓN DE LÓGICA DE FILTROS
    historial_filtrado = historial_completo

    # Filtro Tipo
    if filtro_tipo == "💰 Cobros":
        historial_filtrado = [h for h in historial_filtrado if h['tipo'] == "COBRO"]
    elif filtro_tipo == "💸 Préstamos":
        historial_filtrado = [h for h in historial_filtrado if h['tipo'] == "PRESTAMO"]
    elif filtro_tipo == "🏦 Admin":
        historial_filtrado = [h for h in historial_filtrado if h['tipo'] == "ADMIN"]

    # Filtro Tiempo (Lógica mejorada para soportar calendario)
    if filtro_tiempo == "📅 Solo Hoy":
        historial_filtrado = [h for h in historial_filtrado if get_fecha_etiqueta(h['fecha_raw']) == "HOY"]
    elif filtro_tiempo == "⏮️ Solo Ayer":
        historial_filtrado = [h for h in historial_filtrado if get_fecha_etiqueta(h['fecha_raw']) == "AYER"]
    elif filtro_tiempo == "📆 Seleccionar Fecha" and fecha_seleccionada:
        # Filtramos comparando la fecha raw con la fecha seleccionada en el calendario
        historial_filtrado = [h for h in historial_filtrado if check_fecha_coincide(h['fecha_raw'], fecha_seleccionada)]

    # 5. RENDERIZADO DE LA LISTA
    if not historial_filtrado:
        st.info("No se encontraron movimientos para este filtro.")
    else:
        ultimo_grupo = None
        
        st.markdown('<div class="tx-list">', unsafe_allow_html=True)
        
        for h in historial_filtrado:
            grupo_fecha = get_fecha_etiqueta(h['fecha_raw'])
            
            # Encabezado de fecha
            if grupo_fecha != ultimo_grupo:
                st.markdown(f"<div style='text-align:center'><span class='date-badge'>{grupo_fecha}</span></div>", unsafe_allow_html=True)
                ultimo_grupo = grupo_fecha

            # Fila de transacción
            signo = "+" if h['monto'] > 0 else ""
            clase_monto = "val-pos" if h['clase'] == "positivo" else "val-neg"
            
            st.markdown(f"""
            <div class="tx-card">
                <div class="tx-left">
                    <div class="tx-icon-box">{h['icono']}</div>
                    <div class="tx-details">
                        <span class="tx-title">{h['titulo']}</span>
                        <span class="tx-sub">{h['subtitulo']}</span>
                    </div>
                </div>
                <div class="tx-amount {clase_monto}">
                    {signo}C$ {h['monto']:,.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)