import streamlit as st
import requests
import time
import math
from datetime import datetime, timedelta
from db_connection import get_db_client

# ==========================================
# 0. CONFIGURACIÓN
# ==========================================
try:
    TELEGRAM_TOKEN = st.secrets["telegram"]["token"]
    # ⚠️ FORZAMOS EL ID DEL GRUPO A LA FUERZA AQUÍ:
    TELEGRAM_CHAT_ID = "-5258765663" 
except:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = "-5258765663" # También lo ponemos aquí por si acaso

def enviar_telegram(mensaje):
    if not TELEGRAM_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error Telegram: {e}")

# ==========================================
# 1. FUNCIONES LÓGICAS
# ==========================================
def obtener_nombre_cobrador(user_id):
    supabase = get_db_client()
    try:
        resp = supabase.table("usuarios").select("nombre_completo").eq("id", user_id).execute()
        return resp.data[0]['nombre_completo'] if resp.data else "Agente"
    except:
        return "Agente"

def ir_a_cobrar(prestamo):
    # 1. Guardamos los datos del cliente
    st.session_state['transaccion_activa'] = prestamo
    
    # 2. LA LLAVE MAESTRA: Cambiamos tu variable Y la del widget de Streamlit
    st.session_state['menu_option'] = '💰 Cobrar'
    st.session_state['radio_menu_driver'] = '💰 Cobrar'  # <--- ESTA LÍNEA ES LA QUE FALTABA
    
    # 3. Notificamos y recargamos
    st.toast("✅ Redirigiendo a cobro...", icon="💳")
    time.sleep(0.4)
    st.rerun()
    
def cambiar_favorito(cliente_id, estado_actual_es_favorito):
    supabase = get_db_client()
    try:
        nuevo_valor = not estado_actual_es_favorito
        supabase.table("clientes").update({"es_favorito": nuevo_valor}).eq("id", cliente_id).execute()
        msg = "⭐ Añadido a favoritos" if nuevo_valor else "🗑️ Quitado de favoritos"
        st.toast(msg)
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

# ==========================================
# 2. VISTA PRINCIPAL
# ==========================================
def mostrar_dashboard():
    # --- CABECERA ---
    meses = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 
             7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
    hoy_dt = datetime.now()
    fecha_format = f"{hoy_dt.day} de {meses[hoy_dt.month]}, {hoy_dt.year}"

    st.title("Ruta de Cobranza")
    st.caption(f"📅 {fecha_format}")

    # --- CARGA DE DATOS ---
    supabase = get_db_client()
    user_id = st.session_state.get('user_id')
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    hoy_obj = datetime.now()

    if not user_id:
        st.warning("🔒 Sesión expirada.")
        return

    try:
        resp = supabase.table("prestamos").select("*, clientes(*)").eq("cobrador_id", user_id).in_("estado", ["activo", "mora"]).execute()
        prestamos = resp.data or []
        visitas = supabase.table("bitacora_visitas").select("cliente_id, estado_visita").eq("fecha", hoy_str).execute()
        mapa_visitas = {v['cliente_id']: v['estado_visita'] for v in visitas.data}
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return

    if not prestamos:
        st.info("🌴 No tienes ruta asignada hoy.")
        return

    # --- CÁLCULOS KPI ---
    total_cuotas_dia = 0    
    recaudado_hoy = 0       
    clientes_total = len(prestamos)
    clientes_visitados_ok = 0
    
    for p in prestamos:
        c_id = p['cliente_id']
        cuota = p.get('monto_cuota', 0)
        estado = mapa_visitas.get(c_id, "Pendiente")
        
        total_cuotas_dia += cuota
        if estado == "Pagado":
            recaudado_hoy += cuota
            clientes_visitados_ok += 1
            
    falta_cobrar = total_cuotas_dia - recaudado_hoy
    
    # Cálculo porcentajes
    if total_cuotas_dia > 0:
        progreso_float = recaudado_hoy / total_cuotas_dia
        progreso_porcentaje = int(progreso_float * 100)
    else:
        progreso_float = 0.0
        progreso_porcentaje = 0

    # --- DASHBOARD METRICAS ---
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Recaudado", f"C$ {recaudado_hoy:,.0f}", f"{progreso_porcentaje}%")
    col2.metric("📉 Falta", f"C$ {falta_cobrar:,.0f}", delta_color="inverse")
    col3.metric("✅ Clientes", f"{clientes_visitados_ok}/{clientes_total}")
    
    st.progress(max(0.0, min(1.0, progreso_float)))
    st.divider()

    # --- FILTROS ---
    filtro = st.radio(
        "Filtrar:", 
        ["Todos", "Pendientes", "Cobrados", "Favoritos", "Morosos"], 
        horizontal=True
    )
    st.write("")

    lista_final = []
    for p in prestamos:
        c_id = p['cliente_id']
        estado = mapa_visitas.get(c_id, "Pendiente")
        es_fav = p['clientes'].get('es_favorito', False)
        
        mostrar = False
        if filtro == "Todos": mostrar = True
        elif filtro == "Pendientes" and estado == "Pendiente": mostrar = True
        elif filtro == "Cobrados" and estado == "Pagado": mostrar = True
        elif filtro == "Favoritos" and es_fav: mostrar = True
        elif filtro == "Morosos" and estado == "No Pago": mostrar = True
        
        if mostrar: lista_final.append(p)

    st.caption(f"Mostrando {len(lista_final)} clientes")

    # --- LISTA DE CLIENTES ---
    for p in lista_final:
        c = p['clientes']
        c_id = p['cliente_id']
        p_id = p['id']
        
        nombre = c.get('nombre', 'Cliente')
        direccion = c.get('direccion', 'Sin dirección')
        es_fav = c.get('es_favorito', False)
        estado = mapa_visitas.get(c_id, "Pendiente")
        
        saldo = p.get('saldo_pendiente', 0)
        cuota = p.get('monto_cuota', 1)
        monto_original = p.get('monto_solicitado', saldo)

        # Tarjeta Nativa
        with st.container(border=True):
            
            # Cabecera
            c_head, c_status = st.columns([0.7, 0.3])
            with c_head:
                st.subheader(nombre)
                st.caption(f"📍 {direccion}")
            
            with c_status:
                if estado == "Pagado":
                    st.success("✅ Pagado")
                elif estado == "No Pago":
                    st.error("🚫 Moroso")
                else:
                    st.warning("🟡 Pendiente")

            # Datos Financieros
            c_cuota, c_saldo, c_fav = st.columns([0.4, 0.4, 0.2])
            c_cuota.metric("Cuota", f"C$ {cuota:,.0f}")
            c_saldo.metric("Saldo", f"C$ {saldo:,.0f}")
            
            with c_fav:
                st.write("") 
                # Botón Favorito
                icon_fav = "⭐" if es_fav else "☆"
                if st.button(icon_fav, key=f"fav_{p_id}", help="Favorito"):
                    cambiar_favorito(c_id, es_fav)

            # Detalles
            with st.expander("📊 Ver detalles"):
                if cuota > 0 and saldo > 0:
                    pagos_restantes = math.ceil(saldo / cuota)
                    fecha_estimada = hoy_obj + timedelta(days=pagos_restantes)
                    pagado_aprox = monto_original - saldo
                    progreso_cli = pagado_aprox / monto_original if monto_original > 0 else 0
                    
                    k1, k2 = st.columns(2)
                    k1.info(f"Restan: {pagos_restantes} cuotas")
                    k2.info(f"Fin: {fecha_estimada.strftime('%d/%m/%Y')}")
                    st.progress(max(0.0, min(1.0, progreso_cli)))
                else:
                    st.success("¡Crédito finalizado!")

            # BOTONES DE ACCIÓN (Con colores CSS aplicados)
            st.write("")
            if estado == "Pagado":
                st.button("✅ Completado", key=f"paid_{p_id}", disabled=True, use_container_width=True)
            else:
                b1, b2 = st.columns(2)
                
                # BOTÓN COBRAR
                if b1.button("💳 COBRAR", key=f"pay_{p_id}", type="primary", use_container_width=True):
                    ir_a_cobrar(p)
                
                # BOTÓN NO PAGO (Deshabilitado si ya es moroso hoy)
                ya_es_moroso = (estado == "No Pago")
                if b2.button("🚫 NO PAGO", key=f"nopay_{p_id}", type="secondary", disabled=ya_es_moroso, use_container_width=True):
                    
                    # Lógica No Pago usando UPSERT en lugar de INSERT
                    supabase.table("bitacora_visitas").upsert({
                        "cliente_id": c_id, "cobrador_id": user_id, "fecha": hoy_str, "estado_visita": "No Pago"
                    }).execute()
                    
                    historial_resp = supabase.table("bitacora_visitas").select("estado_visita").eq("cliente_id", c_id).order("fecha", desc=True).limit(3).execute()
                    historial = historial_resp.data or []
                    es_credit_hold = False
                    
                    if len(historial) == 3 and all(h['estado_visita'] == 'No Pago' for h in historial):
                        es_credit_hold = True
                        supabase.table("clientes").update({"estado_cartera": "credit_hold"}).eq("id", c_id).execute()
                        alerta_data = {
                            "cobrador_id": user_id, "tipo_solicitud": "alerta_mora", "id_cliente_existente": c_id,
                            "monto_solicitado": 0, "tasa_propuesta": 0, "plazo_dias": 0, "estado": "pendiente",
                            "fecha_solicitud": datetime.now().isoformat(), "motivo_rechazo": "AUTOMÁTICO: 3 días consecutivos 'No Pago' reportados."
                        }
                        supabase.table("solicitudes").insert(alerta_data).execute()

                    nuevo_saldo = p['saldo_pendiente']
                    supabase.table("prestamos").update({"saldo_pendiente": nuevo_saldo, "estado": "mora"}).eq("id", p_id).execute()

                    agente = obtener_nombre_cobrador(user_id)
                    msg_telegram = f"🚨 *REPORTE DE NO PAGO*\n👤 {nombre}\n📉 Saldo: C$ {nuevo_saldo:,.2f}\n📍 {direccion}\n👷 {agente}"
                    if es_credit_hold:
                        msg_telegram += "\n⛔ **CLIENTE BLOQUEADO (3 Faltas)**"
                        st.error("⛔ ¡Cliente bloqueado por 3 faltas!")
                    else:
                        st.warning("Incidencia reportada.")
                    
                    enviar_telegram(msg_telegram)
                    time.sleep(1.0)
                    st.rerun()