import streamlit as st
import requests
import time
import uuid  # 🔑 para generar la llave de idempotencia del pago
from datetime import datetime, timedelta, timezone
from db_connection import get_db_client

# ==========================================
# 👇 NUEVO 1: ZONA HORARIA LOCAL (UTC-6)
# ==========================================
TZ_LOCAL = timezone(timedelta(hours=-6))

# ==========================================
# 0. CONFIGURACIÓN TELEGRAM (ADMIN)
# ==========================================
TELEGRAM_TOKEN = "8318393313:AAHaN9NtFFw4R29DbRKGG3_HFTwfa4P7-w8"
TELEGRAM_CHAT_ID = "8535378746"

def enviar_reporte_telegram(mensaje, foto_bytes=None):
    try:
        if foto_bytes:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            files = {'photo': ('pago.jpg', foto_bytes)}
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': mensaje, 'parse_mode': 'Markdown'}
            requests.post(url, files=files, data=data, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensaje, 'parse_mode': 'Markdown'}
            requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error Telegram: {e}")

# ==========================================
# 1. ESTILOS CSS (DISEÑO FINTECH PREMIUM)
# ==========================================
def cargar_estilos():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* --- GENERAL SETTINGS --- */
        .stApp { 
            background-color: #F7F3E9; 
            font-family: 'Inter', sans-serif;
            color: #0F3D3E;
        }
        
        h1, h2, h3, p, div { color: #0F3D3E; }
        
        /* --- INPUTS & BUSCADOR --- */
        div[data-testid="stTextInput"] { margin-bottom: 20px; }
        div[data-testid="stTextInput"] input { 
            border-radius: 20px !important; 
            border: 1px solid #E0E0E0 !important; 
            padding: 15px 20px !important; 
            background-color: #FFFFFF !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.03) !important;
            color: #0F3D3E !important;
            font-size: 15px;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: #4CAF50 !important;
            box-shadow: 0 4px 12px rgba(76, 175, 80, 0.15) !important;
        }

        /* --- TARJETAS DE CLIENTES --- */
        .client-list-card { 
            background: #FFFFFF; 
            padding: 20px 24px; 
            border-radius: 18px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.04); 
            margin-bottom: 16px; 
            border: 1px solid rgba(0,0,0,0.02);
            transition: transform 0.2s ease;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            height: 100%;
        }
        
        .client-name { 
            font-size: 18px; 
            font-weight: 700; 
            color: #0F3D3E; 
            letter-spacing: -0.5px;
            margin-bottom: 4px;
        }
        
        .client-meta {
            font-size: 13px; 
            color: #8D99AE; 
            display: flex; 
            align-items: center; 
            gap: 5px;
            margin-bottom: 12px;
        }

        .debt-container {
            display: flex;
            align-items: baseline;
            gap: 8px;
        }
        
        .debt-label { font-size: 12px; font-weight: 600; color: #8D99AE; text-transform: uppercase; }
        .client-debt { font-size: 16px; color: #4CAF50; font-weight: 700; } 
        .last-payment { font-size: 11px; color: #FFA000; font-weight: 600; margin-top: 5px; }

        /* --- BOTONES --- */
        .stButton button { 
            border-radius: 14px !important; 
            height: 48px !important; 
            font-weight: 600 !important; 
            font-size: 15px !important;
            border: none !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.08) !important;
        }
        
        button[kind="primary"] {
            background-color: #6ec071 !important;
            color: white !important;
        }
        button[kind="primary"]:hover {
            background-color: #4CAF50 !important;
            box-shadow: 0 6px 15px rgba(46, 125, 50, 0.25) !important;
            transform: translateY(-1px);
        }

        button[kind="secondary"] {
            background-color: white !important;
            color: #666 !important;
            border: 1px solid #eee !important;
        }

        /* --- FORMULARIO DE PAGO --- */
        .payment-summary { 
            background-color: #FFFFFF; 
            padding: 30px; 
            border-radius: 24px; 
            text-align: center; 
            border: 1px solid rgba(0,0,0,0.03); 
            margin-bottom: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.04);
        }
        .summary-label {
            color: #8D99AE; 
            font-size: 13px; 
            text-transform: uppercase; 
            letter-spacing: 1.5px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .big-money { 
            font-size: 42px; 
            font-weight: 700; 
            color: #0F3D3E; 
            letter-spacing: -1px;
            margin-bottom: 10px;
        }
        .cuota-pill {
            background-color: #E6F4EA;
            color: #4CAF50;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            display: inline-block;
        }

        .method-badge {
            background-color: #E6F4EA;
            color: #4CAF50;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            display: inline-block;
            margin-bottom: 15px;
            border: none;
        }
        
        div[data-testid="stCameraInput"] {
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid #eee;
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. POP-UP DE CONFIRMACIÓN
# ==========================================
@st.dialog("✅ Transacción Exitosa")
def mostrar_popup_exito(cliente_nombre, monto, nuevo_saldo, cobrador_nombre):
    st.balloons()
    
    html_content = f"""
<div style="text-align: center; padding: 20px 10px;">
    <div style="color: #4CAF50; font-size: 50px; margin-bottom: 10px;">✨</div>
    <h3 style="color: #0F3D3E; margin: 0; font-weight: 700; letter-spacing: -0.5px;">Pago Registrado</h3>
    <h1 style="color: #4CAF50; font-size: 48px; font-weight: 800; margin: 10px 0 25px 0;">C$ {monto:,.2f}</h1>
    <div style="background: #FAFAFA; padding: 20px; border-radius: 16px; text-align: left; border: 1px solid #f0f0f0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
            <span style="color: #888; font-size: 14px;">Cliente</span>
            <span style="color: #0F3D3E; font-weight: 600;">{cliente_nombre}</span>
        </div>
        <div style="width: 100%; height: 1px; background: #eee; margin-bottom: 12px;"></div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #888; font-size: 14px;">Nuevo Saldo</span>
            <span style="color: #D32F2F; font-weight: 700; font-size: 18px;">C$ {nuevo_saldo:,.2f}</span>
        </div>
    </div>
    <p style="font-size: 12px; color: #999; margin-top: 25px;">
        Procesado por {cobrador_nombre}
    </p>
</div>
    """
    
    st.markdown(html_content, unsafe_allow_html=True)
    
    if st.button("Finalizar", type="primary", use_container_width=True):
        st.rerun()

# ==========================================
# 3. LÓGICA DE PROCESAMIENTO
# ==========================================
def procesar_pago(prestamo, monto, metodo, nota, foto, user_id, idempotency_key=None):
    supabase = get_db_client()
    cliente = prestamo['clientes']
    
    # 👇 Uso de zona horaria local para evitar saltos de día por la hora UTC del servidor
    hoy = datetime.now(TZ_LOCAL).strftime("%Y-%m-%d")
    ahora = datetime.now(TZ_LOCAL).strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # =======================================================
        # 🔑 GUARDIA DE IDEMPOTENCIA
        # Si ya existe un pago con esta misma llave, NO registramos otro.
        # Esto blinda contra doble clic / rerun aunque el candado falle.
        # =======================================================
        if idempotency_key:
            try:
                ya_existe = supabase.table("pagos").select("id").eq("idempotency_key", idempotency_key).execute()
                if ya_existe.data:
                    st.warning("⚠️ Este pago ya fue registrado. Evitamos duplicarlo.")
                    # Cerramos la transacción y limpiamos para volver a la lista
                    st.session_state['transaccion_activa'] = None
                    if 'pago_key' in st.session_state:
                        del st.session_state['pago_key']
                    time.sleep(1)
                    st.rerun()
                    return
            except Exception as e:
                # Si la columna aún no existe en la DB, no bloqueamos el flujo (solo avisamos en consola)
                print(f"Aviso idempotencia pago (verificación): {e}")

        # 1. Obtenemos datos del cobrador
        resp_cobrador = supabase.table("usuarios").select("nombre_completo, username, saldo_actual").eq("id", user_id).single().execute()
        nombre_cobrador = resp_cobrador.data.get('nombre_completo') or resp_cobrador.data.get('username') if resp_cobrador.data else "Driver"
        
        # 👇 NUEVO 2: CÁLCULO DE SALDO REAL
        # Buscamos todos los pagos hechos y restamos a la deuda original para evitar desfaces
        r_pagos = supabase.table("pagos").select("monto").eq("prestamo_id", prestamo['id']).execute()
        total_pagado = sum([p['monto'] for p in (r_pagos.data or [])])
        monto_total_deuda = prestamo.get('monto_total_deuda', prestamo.get('monto', 0))
        
        if monto_total_deuda > 0:
            saldo_anterior_real = monto_total_deuda - total_pagado
        else:
            saldo_anterior_real = prestamo['saldo_pendiente']

        nuevo_saldo = saldo_anterior_real - monto

        # 3. Insertar el pago (con la llave única)
        datos_pago = {
            "prestamo_id": prestamo['id'],
            "cliente_id": cliente['id'],
            "cobrador_id": user_id,
            "monto": monto,
            "fecha_hora": ahora,
            "fecha_pago": hoy,
            "idempotency_key": idempotency_key,  # 🔑 la DB rechaza un 2do pago con esta misma llave
        }
        # 🔑 Si la DB rechaza por llave duplicada (índice único), lo capturamos sin romper la app
        try:
            supabase.table("pagos").insert(datos_pago).execute()
        except Exception as e_dup:
            print(f"Insert pago bloqueado por idempotencia: {e_dup}")
            st.warning("⚠️ Este pago ya fue registrado. Evitamos duplicarlo.")
            st.session_state['transaccion_activa'] = None
            if 'pago_key' in st.session_state:
                del st.session_state['pago_key']
            time.sleep(1)
            st.rerun()
            return

        # 4. Actualizar Préstamo
        nuevo_estado = "pagado" if nuevo_saldo <= 0 else "activo"
        supabase.table("prestamos").update({
            "saldo_pendiente": nuevo_saldo,
            "estado": nuevo_estado
        }).eq("id", prestamo['id']).execute()
        
        # 👇 NUEVO 3: SUMAR A LA CAJA DEL DRIVER
        saldo_caja_anterior = resp_cobrador.data.get('saldo_actual', 0) if resp_cobrador.data else 0
        nuevo_saldo_caja = saldo_caja_anterior + monto
        supabase.table("usuarios").update({
            "saldo_actual": nuevo_saldo_caja
        }).eq("id", user_id).execute()

        # 5. Actualizar Bitácora
        visita_data = {"cliente_id": cliente['id'], "cobrador_id": user_id, "fecha": hoy, "estado_visita": "Pagado"}
        check = supabase.table("bitacora_visitas").select("id").eq("cliente_id", cliente['id']).eq("fecha", hoy).execute()
        if check.data:
            supabase.table("bitacora_visitas").update(visita_data).eq("id", check.data[0]['id']).execute()
        else:
            supabase.table("bitacora_visitas").insert(visita_data).execute()

        # 6. Notificación Admin
        notificacion_admin = {
            "cobrador_id": user_id,
            "id_cliente_existente": cliente['id'],
            "tipo_solicitud": "info_pago",
            "monto_solicitado": monto,
            "tasa_propuesta": 0,
            "plazo_dias": 0,
            "estado": "pendiente",
            "fecha_solicitud": ahora,
            "datos_nuevo_cliente": {
                "nota": nota,
                "mensaje": "Pago registrado por Driver"
            }
        }
        supabase.table("solicitudes").insert(notificacion_admin).execute()

        # 7. Telegram Reporte
        foto_bytes = foto.getvalue() if foto else None
        mensaje = (
            f"💰 *NUEVO PAGO (Efectivo)*\n"
            f"👤 Cliente: *{cliente['nombre']}*\n"
            f"💵 Monto: *C$ {monto:,.2f}*\n"
            f"📉 Restante Cliente (Real): C$ {nuevo_saldo:,.2f}\n"
            f"--------------------------\n"
            f"🏍️ Cobrado por: *{nombre_cobrador}*\n"
            f"👜 Caja Actual Driver: C$ {nuevo_saldo_caja:,.2f}"
        )
        enviar_reporte_telegram(mensaje, foto_bytes)

        # 8. PREPARAR POPUP Y SALIR
        st.session_state['datos_exito'] = {
            'cliente': cliente['nombre'],
            'monto': monto,
            'nuevo_saldo': nuevo_saldo,
            'cobrador': nombre_cobrador
        }
        st.session_state['transaccion_activa'] = None 
        # 🔑 borramos la llave para que el próximo pago tenga una nueva
        if 'pago_key' in st.session_state:
            del st.session_state['pago_key']
        # 🔒 liberamos el candado
        st.session_state['procesando_pago'] = False
        st.rerun() 

    except Exception as e:
        # 🔒 si algo falla, liberamos el candado para que pueda reintentar
        st.session_state['procesando_pago'] = False
        st.error(f"⚠️ Error CRÍTICO al guardar: {e}")

# ==========================================
# 4. VISTA: FORMULARIO DE PAGO
# ==========================================
def mostrar_formulario_pago(prestamo, user_id):
    cliente = prestamo['clientes']
    supabase = get_db_client()

    # 🔒 candado anti doble-clic para el pago
    if 'procesando_pago' not in st.session_state:
        st.session_state['procesando_pago'] = False

    # 🔑 llave única para ESTE pago. Se genera una sola vez por formulario abierto
    # y se borra al terminar (o al volver) -> cada pago tiene su propia llave.
    if 'pago_key' not in st.session_state:
        st.session_state['pago_key'] = str(uuid.uuid4())
    
    col_nav, col_title = st.columns([0.2, 0.8])
    with col_nav:
        if st.button("⬅ Volver", key="btn_back"):
            st.session_state['transaccion_activa'] = None
            # 🔑 al volver, descartamos la llave y el candado de este pago
            if 'pago_key' in st.session_state:
                del st.session_state['pago_key']
            st.session_state['procesando_pago'] = False
            st.rerun()
    with col_title:
        st.markdown(f"<h3 style='margin:0; padding-top: 10px; font-weight: 700;'>{cliente['nombre']}</h3>", unsafe_allow_html=True)

    # 👇 CÁLCULO DE SALDO REAL EN VISTA DEL FORMULARIO
    r_pagos = supabase.table("pagos").select("monto").eq("prestamo_id", prestamo['id']).execute()
    total_pagado = sum([p['monto'] for p in (r_pagos.data or [])])
    monto_total_deuda = prestamo.get('monto_total_deuda', prestamo.get('monto', prestamo['saldo_pendiente']))
    
    if monto_total_deuda > 0:
        saldo_real = monto_total_deuda - total_pagado
    else:
        saldo_real = prestamo['saldo_pendiente']

    cuota = prestamo['monto_cuota']
    
    # Manejo seguro para evitar divisiones por cero al calcular progreso
    monto_total_prestamo = monto_total_deuda if monto_total_deuda > 0 else 1
    porcentaje_avance = min(100, max(0, int((total_pagado / monto_total_prestamo) * 100)))
    
    st.write("") 

    # Tarjeta de resumen
    st.markdown(f"""
        <div class="payment-summary">
            <div class="summary-label">Saldo Pendiente Real</div>
            <div class="big-money">C$ {saldo_real:,.2f}</div>
            <div class="cuota-pill">Cuota Sugerida: C$ {cuota:,.2f}</div>
        </div>
    """, unsafe_allow_html=True)

    # Barra de progreso de Streamlit
    st.markdown(f"<p style='font-size: 13px; color: #8D99AE; font-weight: 600; margin-bottom: -10px;'>Progreso del Préstamo: {porcentaje_avance}%</p>", unsafe_allow_html=True)
    st.progress(porcentaje_avance / 100.0)
    st.write("")

    # Alerta de renovación
    if saldo_real <= (cuota * 2) and saldo_real > 0:
        st.info("🎯 **¡Atención!** Este cliente está a punto de cancelar su préstamo. ¡Buen momento para ofrecer una renovación!", icon="🎉")

    st.markdown('<div class="method-badge">MÉTODO: EFECTIVO</div>', unsafe_allow_html=True)
    
    st.write("**Detalles del Pago**")
    monto = st.number_input("Monto Recibido (C$)", min_value=1.0, value=float(cuota), step=10.0)
    nota = st.text_input("Nota del cobro (Opcional)")
    
    st.write("")
    st.write("**Comprobante**")
    
    activar_camara = st.toggle("📸 Activar cámara para tomar foto")
    foto = None
    
    if activar_camara:
        foto = st.camera_input("Tomar foto", label_visibility="collapsed")
    
    st.write("") 
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 🔒 botón deshabilitado mientras procesa
    click_pago = st.button(
        "REGISTRAR PAGO",
        type="primary",
        use_container_width=True,
        disabled=st.session_state['procesando_pago']
    )
    if click_pago and not st.session_state['procesando_pago']:
        st.session_state['procesando_pago'] = True   # 🔒 candado ON
        procesar_pago(prestamo, monto, "Efectivo", nota, foto, user_id,
                      idempotency_key=st.session_state['pago_key'])   # 🔑

# ==========================================
# 5. VISTA: LISTA DE CLIENTES
# ==========================================
def mostrar_lista_clientes(user_id):
    supabase = get_db_client()
    # 👇 Usamos zona horaria local
    hoy = datetime.now(TZ_LOCAL).strftime("%Y-%m-%d")
    
    # Consultar saldo del driver en vivo
    try:
        resp_driver = supabase.table("usuarios").select("saldo_actual").eq("id", user_id).single().execute()
        saldo_driver = resp_driver.data.get('saldo_actual', 0) if resp_driver.data else 0
    except:
        saldo_driver = 0
        
    col_title, col_badge = st.columns([0.5, 0.5])
    with col_title:
        st.markdown("<h2 style='font-weight: 800; margin-bottom: 25px;'>Cartera</h2>", unsafe_allow_html=True)
    with col_badge:
        st.markdown(f"<div style='background-color:#E8F5E9; color:#2E7D32; padding:8px 12px; border-radius:10px; text-align:right; font-weight:bold; margin-top:20px;'>👜 Dinero en Mano: C$ {saldo_driver:,.0f}</div>", unsafe_allow_html=True)
    
    busqueda = st.text_input("", placeholder="🔍  Buscar cliente por nombre...", label_visibility="collapsed")

    try:
        resp = supabase.table("prestamos").select("*, clientes(*)").eq("cobrador_id", user_id).eq("estado", "activo").execute()
        prestamos = resp.data or []
        
        visitas = supabase.table("bitacora_visitas").select("cliente_id").eq("fecha", hoy).eq("estado_visita", "Pagado").execute()
        pagados_ids = [v['cliente_id'] for v in visitas.data]
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return

    lista = []
    if prestamos:
        term = busqueda.lower()
        for p in prestamos:
            nombre_cliente = p['clientes']['nombre'].lower() if p['clientes'] else ""
            if term in nombre_cliente and p['cliente_id'] not in pagados_ids:
                lista.append(p)

    if not lista:
        if busqueda:
            st.info("No se encontraron coincidencias.")
        else:
            st.markdown("<p style='text-align:center; color:#888; margin-top:30px;'>Utiliza el buscador para encontrar un cliente.</p>", unsafe_allow_html=True)
    
    if lista:
        st.markdown(f"<p style='color:#8D99AE; font-size:13px; font-weight:600; margin-bottom:20px;'>ENCONTRADOS: {len(lista)}</p>", unsafe_allow_html=True)
        
        # 👇 CÁLCULO MASIVO DE SALDO REAL PARA LA LISTA (Para evitar N+1 Consultas)
        prestamo_ids = [p['id'] for p in lista]
        pagos_dict = {pid: 0 for pid in prestamo_ids}
        
        if prestamo_ids:
            res_pagos = supabase.table("pagos").select("prestamo_id, monto").in_("prestamo_id", prestamo_ids).execute()
            if res_pagos.data:
                for pg in res_pagos.data:
                    pagos_dict[pg['prestamo_id']] += pg['monto']
        
        for p in lista:
            c = p['clientes']
            prestamo_id = p['id']
            direccion = c.get('direccion', 'Sin dirección')
            fecha_ult = p.get('fecha_ultimo_pago') or 'Sin registro'
            
            monto_total_deuda = p.get('monto_total_deuda', p.get('monto', 0))
            if monto_total_deuda > 0:
                saldo_real = monto_total_deuda - pagos_dict.get(prestamo_id, 0)
            else:
                saldo_real = p['saldo_pendiente']
            
            with st.container():
                col_card, col_action = st.columns([0.7, 0.3])
                
                with col_card:
                    st.markdown(f"""
                    <div class="client-list-card">
                        <div class="client-name">{c['nombre']}</div>
                        <div class="client-meta">📍 {direccion}</div>
                        <div class="debt-container">
                            <span class="debt-label">Pendiente:</span>
                            <span class="client-debt">C$ {saldo_real:,.0f}</span>
                        </div>
                        <div class="last-payment">⏱️ Últ. pago: {fecha_ult}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_action:
                    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True) 
                    if st.button("COBRAR", key=f"cob_{prestamo_id}", type="primary", use_container_width=True):
                        st.session_state['transaccion_activa'] = p
                        # 🔑 nuevo cobro => generamos una llave nueva y liberamos candado
                        st.session_state['pago_key'] = str(uuid.uuid4())
                        st.session_state['procesando_pago'] = False
                        st.rerun()

# ==========================================
# 6. MAIN
# ==========================================
def mostrar_cobro():
    cargar_estilos()
    user_id = st.session_state.get('user_id')
    
    if 'datos_exito' in st.session_state:
        d = st.session_state['datos_exito']
        mostrar_popup_exito(d['cliente'], d['monto'], d['nuevo_saldo'], d['cobrador'])
        del st.session_state['datos_exito'] 
    
    if st.session_state.get('transaccion_activa'):
        mostrar_formulario_pago(st.session_state['transaccion_activa'], user_id)
    else:
        mostrar_lista_clientes(user_id)
