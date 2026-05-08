import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from db_connection import get_db_client

# Definimos tu zona horaria local (UTC-6 para Nicaragua/Centroamérica)
TZ_LOCAL = timezone(timedelta(hours=-6))

# ==========================================
# 1. ESTILOS HÍBRIDOS (UI LIMPIA)
# ==========================================
def cargar_estilos_hibridos():
    st.markdown("""
        <style>
        /* Estilos del Formulario de Cobro */
        .payment-summary { 
            background-color: #FFFFFF; padding: 20px; border-radius: 16px; 
            text-align: center; border: 1px solid #f0f0f0; margin-bottom: 15px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.02);
        }
        .summary-label { color: #8D99AE; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 5px; }
        .big-money { font-size: 32px; font-weight: 700; color: #0F3D3E; margin-bottom: 8px; }
        .cuota-pill { background-color: #E6F4EA; color: #4CAF50; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .method-badge { background-color: #FFF3E0; color: #EF6C00; padding: 8px 16px; border-radius: 8px; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 15px; display: inline-block; }
        
        /* Estilos de las Tarjetas de Detalles */
        .metric-card { background-color: #ffffff; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); margin-bottom: 20px; border: 1px solid #f0f0f0; }
        .card-blue { border-top: 4px solid #42a5f5; }
        .card-header-title { font-size: 1.1rem; font-weight: 700; color: #546e7a; margin-bottom: 15px; text-transform: uppercase; }
        .info-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed #eceff1; }
        .info-row:last-child { border-bottom: none; }
        .info-label { color: #78909c; font-weight: 500; font-size: 0.9rem; }
        .info-value { color: #263238; font-weight: 600; font-size: 0.95rem; }
        .empty-state { background-color: #f1f8e9; color: #558b2f; padding: 15px; border-radius: 6px; font-size: 0.9rem; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. POP-UP DE CONFIRMACIÓN
# ==========================================
@st.dialog("✅ Transacción Extraordinaria Exitosa")
def mostrar_popup_exito(cliente_nombre, monto, nuevo_saldo, driver_nombre):
    st.balloons()
    html_content = f"""
    <div style="text-align: center; padding: 10px;">
        <h3 style="color: #0F3D3E; margin: 0; font-weight: 700;">Pago Registrado</h3>
        <h1 style="color: #4CAF50; font-size: 40px; font-weight: 800; margin: 10px 0;">C$ {monto:,.2f}</h1>
        <div style="background: #FAFAFA; padding: 15px; border-radius: 12px; text-align: left; border: 1px solid #eee;">
            <p style="margin: 0; color: #888; font-size: 14px;">Cliente: <span style="color: #0F3D3E; font-weight: 600; float: right;">{cliente_nombre}</span></p>
            <hr style="margin: 10px 0; border: 0; border-top: 1px solid #eee;">
            <p style="margin: 0; color: #888; font-size: 14px;">Nuevo Saldo Real: <span style="color: #D32F2F; font-weight: 700; float: right;">C$ {nuevo_saldo:,.2f}</span></p>
        </div>
        <p style="font-size: 12px; color: #999; margin-top: 15px;">Sumado a la caja de: <b>{driver_nombre}</b></p>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)
    if st.button("Finalizar", type="primary", use_container_width=True):
        st.rerun()

# ==========================================
# 3. LÓGICA DE PROCESAMIENTO (MODIFICADA Y CORREGIDA)
# ==========================================
def procesar_pago_admin(prestamo, monto, nota, admin_id, id_driver_destino, nombre_driver, fecha_pago, saldo_actual_real):
    supabase = get_db_client()
    cliente = prestamo['clientes']
    
    # Ajustado con la zona horaria local
    ahora = datetime.now(TZ_LOCAL).strftime("%Y-%m-%d %H:%M:%S")
    fecha_pago_str = fecha_pago.strftime("%Y-%m-%d")
    
    try:
        # Calculamos el saldo real restante
        nuevo_saldo = saldo_actual_real - monto

        # 1. Insertar pago
        datos_pago = {
            "prestamo_id": prestamo['id'],
            "cliente_id": cliente['id'],
            "cobrador_id": id_driver_destino, 
            "monto": monto,
            "fecha_hora": ahora,
            "fecha_pago": fecha_pago_str,
        }
        supabase.table("pagos").insert(datos_pago).execute()

        # --- 👇 CORRECCIÓN 1: ACTUALIZAR EL SALDO DEL PRÉSTAMO 👇 ---
        nuevo_estado = "pagado" if nuevo_saldo <= 0 else "activo"
        
        supabase.table("prestamos").update({
            "saldo_pendiente": nuevo_saldo,
            "estado": nuevo_estado
        }).eq("id", prestamo['id']).execute()
        # --- 👆 FIN CORRECCIÓN 1 👆 ---

        # --- 👇 CORRECCIÓN 2: SUMAR EL DINERO A LA CAJA DEL DRIVER 👇 ---
        resp_driver = supabase.table("usuarios").select("saldo_actual").eq("id", id_driver_destino).single().execute()
        if resp_driver.data:
            saldo_caja_anterior = resp_driver.data.get('saldo_actual', 0)
            nuevo_saldo_caja = saldo_caja_anterior + monto
            
            supabase.table("usuarios").update({
                "saldo_actual": nuevo_saldo_caja
            }).eq("id", id_driver_destino).execute()
        # --- 👆 FIN CORRECCIÓN 2 👆 ---

        # 2. Forzar Bitácora para la fecha seleccionada
        visita_data = {
            "cliente_id": cliente['id'], 
            "cobrador_id": id_driver_destino, 
            "fecha": fecha_pago_str, 
            "estado_visita": "Pagado"
        }
        check = supabase.table("bitacora_visitas").select("id").eq("cliente_id", cliente['id']).eq("fecha", fecha_pago_str).execute()
        if check.data:
            supabase.table("bitacora_visitas").update(visita_data).eq("id", check.data[0]['id']).execute()
        else:
            supabase.table("bitacora_visitas").insert(visita_data).execute()

        # 3. Guardar datos para Popup y limpiar vista
        st.session_state['datos_exito_admin'] = {
            'cliente': cliente['nombre'],
            'monto': monto,
            'nuevo_saldo': nuevo_saldo,
            'cobrador': nombre_driver
        }
        st.session_state['prestamo_admin_seleccionado'] = None
        st.rerun()

    except Exception as e:
        st.error(f"⚠️ Error al guardar el pago: {e}")

# ==========================================
# 4. VISTA DIVIDIDA: FORMULARIO + HISTORIAL
# ==========================================
def mostrar_dashboard_cobro_admin(prestamo, admin_id, id_driver, nombre_driver):
    cliente = prestamo['clientes']
    supabase = get_db_client()
    
    if st.button("⬅ Volver al listado"):
        st.session_state['prestamo_admin_seleccionado'] = None
        st.rerun()
        
    st.markdown(f"<h2 style='color: #0F3D3E; margin-top: 10px;'>Gestión de Cobro: {cliente['nombre']}</h2>", unsafe_allow_html=True)
    
    col_izq, col_der = st.columns([1.2, 1], gap="large")
    
    # --- CÁLCULO DE SALDO REAL BASADO EN PAGOS ---
    # Consultamos todos los pagos de este préstamo
    r_pagos = supabase.table("pagos").select("monto, fecha_pago, fecha_hora").eq("prestamo_id", prestamo['id']).order("fecha_hora", desc=True).execute()
    todos_los_pagos = r_pagos.data if r_pagos.data else []
    
    total_pagado = sum([p['monto'] for p in todos_los_pagos])
    monto_total_deuda = prestamo.get('monto_total_deuda', 0)
    
    if monto_total_deuda > 0:
        saldo_real = monto_total_deuda - total_pagado
    else:
        # Fallback en caso de que la deuda total no esté bien registrada
        saldo_real = prestamo.get('saldo_pendiente', 0)
    
    # --- COLUMNA IZQUIERDA: FORMULARIO DE COBRO ---
    with col_izq:
        st.markdown('<div class="method-badge">🛠️ MODO ADMIN: COBRO EXTRAORDINARIO</div>', unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class="payment-summary">
                <div class="summary-label">Saldo Real Pendiente</div>
                <div class="big-money">C$ {saldo_real:,.2f}</div>
                <div class="cuota-pill">Cuota Sugerida: C$ {prestamo['monto_cuota']:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("### Registrar Pago")
        # Ajustado con la zona horaria local
        fecha_pago = st.date_input("📅 Fecha a la que corresponde el pago", value=datetime.now(TZ_LOCAL).date())
        monto = st.number_input("💵 Monto Recibido (C$)", min_value=1.0, value=float(prestamo['monto_cuota']), step=10.0)
        nota = st.text_input("📝 Nota del cobro (Ej: Abono del día lunes)")
        
        st.info(f"💡 El dinero se sumará a la caja del driver: **{nombre_driver}**")
        
        if st.button("✅ FORZAR REGISTRO DE PAGO", type="primary", use_container_width=True):
            procesar_pago_admin(prestamo, monto, nota, admin_id, id_driver, nombre_driver, fecha_pago, saldo_real)

    # --- COLUMNA DERECHA: DETALLES E HISTORIAL ---
    with col_der:
        st.markdown(f"""
        <div class="metric-card card-blue">
            <div class="card-header-title">Detalles del Préstamo</div>
            <div class="info-row"><span class="info-label">Cód. Préstamo</span><span class="info-value">{prestamo.get('codigo_prestamo', 'N/A')}</span></div>
            <div class="info-row"><span class="info-label">Deuda Original</span><span class="info-value">C$ {monto_total_deuda:,.2f}</span></div>
            <div class="info-row"><span class="info-label">Total Abonado</span><span class="info-value">C$ {total_pagado:,.2f}</span></div>
            <div class="info-row"><span class="info-label">Fecha Inicio</span><span class="info-value">{prestamo.get('fecha_inicio', 'N/A')}</span></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### Últimos 10 Pagos Registrados")
        
        ultimos_10 = todos_los_pagos[:10]
        if ultimos_10:
            df_pagos = pd.DataFrame(ultimos_10)
            # Manejo de la fecha dependiendo de cuál campo esté lleno
            df_pagos['Fecha_Real'] = df_pagos['fecha_pago'].fillna(df_pagos['fecha_hora'])
            df_pagos['Fecha_Real'] = pd.to_datetime(df_pagos['Fecha_Real']).dt.strftime('%d/%m/%Y')
            df_pagos.rename(columns={'Fecha_Real': 'Fecha', 'monto': 'Abono (C$)'}, inplace=True)
            st.dataframe(df_pagos[['Fecha', 'Abono (C$)']], hide_index=True, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">No hay pagos previos registrados.</div>', unsafe_allow_html=True)

# ==========================================
# 5. MAIN DEL MÓDULO (SELECTOR Y BUSCADOR)
# ==========================================
def mostrar_modulo_cobros_admin():
    cargar_estilos_hibridos()
    admin_id = st.session_state.get('user_id')
    supabase = get_db_client()

    if 'datos_exito_admin' in st.session_state:
        d = st.session_state['datos_exito_admin']
        mostrar_popup_exito(d['cliente'], d['monto'], d['nuevo_saldo'], d['cobrador'])
        del st.session_state['datos_exito_admin']

    if st.session_state.get('prestamo_admin_seleccionado'):
        p = st.session_state['prestamo_admin_seleccionado']
        id_driver = st.session_state.get('driver_destino_id')
        nombre_driver = st.session_state.get('driver_destino_nombre')
        mostrar_dashboard_cobro_admin(p, admin_id, id_driver, nombre_driver)
        return

    # --- PANTALLA PRINCIPAL: SELECCIÓN ---
    st.title("💸 Pagos Extraordinarios")
    st.write("Registra pagos atrasados o extraordinarios asignándolos a la caja de un driver específico.")

    r_drivers = supabase.table("usuarios").select("id, nombre_completo, username").eq("rol", "driver").execute()
    lista_drivers = r_drivers.data if r_drivers.data else []
    
    if not lista_drivers:
        st.warning("No hay drivers configurados en el sistema.")
        return

    opciones_drivers = { (d.get('nombre_completo') or d.get('username')): d['id'] for d in lista_drivers }
    
    st.markdown("### Selecciona el destinatario")
    col1, col2 = st.columns([1, 1], gap="medium")
    
    with col1:
        driver_seleccionado_nombre = st.selectbox("1️⃣ ¿A qué Driver le sumamos el dinero?", options=list(opciones_drivers.keys()))
        driver_id = opciones_drivers[driver_seleccionado_nombre]

    with col2:
        busqueda = st.text_input("2️⃣ Buscar Cliente (Opcional):", placeholder="Filtrar por nombre...")

    try:
        r_prestamos = supabase.table("prestamos").select("*, clientes(*)").eq("cobrador_id", driver_id).eq("estado", "activo").execute()
        prestamos = r_prestamos.data or []
        
        if busqueda:
            term = busqueda.lower()
            resultados = [p for p in prestamos if p['clientes'] and term in p['clientes']['nombre'].lower()]
        else:
            resultados = [p for p in prestamos if p['clientes']]
        
        if resultados:
            st.write("") 
            st.markdown(f"**Préstamos activos asignados a {driver_seleccionado_nombre} ({len(resultados)}):**")
            
            # --- CÁLCULO DE SALDO REAL MASIVO ---
            # Para no hacer una consulta por cada préstamo, jalamos todos los pagos de un solo golpe
            prestamo_ids = [p['id'] for p in resultados]
            pagos_dict = {pid: 0 for pid in prestamo_ids}
            
            if prestamo_ids:
                res_pagos = supabase.table("pagos").select("prestamo_id, monto").in_("prestamo_id", prestamo_ids).execute()
                if res_pagos.data:
                    for pg in res_pagos.data:
                        pagos_dict[pg['prestamo_id']] += pg['monto']
            
            for p in resultados:
                c = p['clientes']
                
                total_pagado_prestamo = pagos_dict.get(p['id'], 0)
                monto_total = p.get('monto_total_deuda', 0)
                
                if monto_total > 0:
                    saldo_real_mostrar = monto_total - total_pagado_prestamo
                else:
                    saldo_real_mostrar = p.get('saldo_pendiente', 0)
                
                with st.container():
                    st.markdown(f"""
                    <div style='background: white; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.02);'>
                        <div>
                            <h4 style='margin:0; color:#0F3D3E; font-size: 1.1rem;'>{c['nombre']}</h4>
                            <span style='color: #666; font-size: 0.9rem;'>Deuda Real: <b>C$ {saldo_real_mostrar:,.0f}</b> | Cuota: C$ {p['monto_cuota']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Realizar pago ➔", key=f"gestionar_{p['id']}", type="secondary"):
                        st.session_state['prestamo_admin_seleccionado'] = p
                        st.session_state['driver_destino_id'] = driver_id
                        st.session_state['driver_destino_nombre'] = driver_seleccionado_nombre
                        st.rerun()
        else:
            if busqueda:
                st.info(f"No se encontraron clientes que coincidan con '{busqueda}'.")
            else:
                st.info(f"El driver {driver_seleccionado_nombre} no tiene préstamos activos en este momento.")
            
    except Exception as e:
        st.error(f"Error consultando clientes: {e}")