import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from db_connection import get_db_client

# ==========================================
# 0. ESTILOS CSS (PROFESIONAL / CORPORATIVO)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
    /* Botones principales */
    div.stButton > button[kind="primary"] {
        background-color: #4CAF50 !important; /* Verde bosque corporativo */
        border-color: #4CAF50 !important;
        color: white !important;
        font-weight: 600;
        border-radius: 6px;
        transition: all 0.3s ease;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #1b5e20 !important; /* Verde más oscuro al pasar mouse */
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    div.stButton > button[kind="secondary"] {
        background-color: white !important;
        color: #c62828 !important; /* Rojo oscuro profesional */
        border: 1px solid #c62828 !important;
        border-radius: 6px;
    }
    
    /* Contenedor de Calculadora */
    .calc-container {
        background-color: #f5f5f5;
        padding: 20px;
        border-radius: 8px;
        border-left: 5px solid #424242;
        margin-top: 15px;
        margin-bottom: 25px; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Cajas de Estado */
    .reintento-box {
        background-color: #e3f2fd;
        border-left: 4px solid #1976d2; 
        padding: 12px;
        margin-bottom: 10px;
        border-radius: 4px;
        color: #0d47a1;
        font-size: 0.9rem;
    }

    .alerta-mora-box {
        background-color: #ffebee;
        border: 1px solid #ffcdd2;
        border-left: 4px solid #d32f2f; 
        padding: 15px;
        border-radius: 6px;
        margin-bottom: 15px;
    }
    
    .notificacion-pago-box {
        background-color: #f1f8e9;
        border: 1px solid #dcedc8;
        border-left: 4px solid #388e3c; 
        padding: 15px;
        border-radius: 6px;
        margin-bottom: 15px;
    }
    
    /* NUEVO: Alerta de saldo pendiente en rojo pálido */
    .alerta-saldo-box {
        background-color: #ffcdd2; /* Rojo pálido tipo paleta */
        border-left: 4px solid #c62828;
        color: #b71c1c;
        padding: 10px 15px;
        border-radius: 6px;
        margin-bottom: 10px;
        font-weight: 500;
        font-size: 0.95rem;
    }
    
    .titulo-box {
        font-weight: 700;
        font-size: 15px;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #333;
    }
    
    .texto-secundario {
        color: #616161;
        font-size: 13px;
    }
    
    /* Texto de resultados dentro de la caja gris */
    .resultado-destacado {
        font-size: 18px;
        color: #1b5e20;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. FUNCIONES LÓGICAS (BACKEND INTACTO)
# ==========================================

def obtener_mapa_usuarios():
    supabase = get_db_client()
    try:
        resp = supabase.table("usuarios").select("id, nombre_completo, username").execute()
        mapa = {u['id']: (u.get('nombre_completo') or u.get('username')) for u in resp.data}
        return mapa
    except:
        return {}

def obtener_nombre_cobrador(cobrador_id):
    supabase = get_db_client()
    try:
        resp = supabase.table("usuarios").select("nombre_completo, username").eq("id", cobrador_id).execute()
        if resp.data:
            return resp.data[0].get('nombre_completo') or resp.data[0].get('username')
        return "Desconocido"
    except:
        return "ID Desc."

def obtener_nombre_cliente(cliente_id):
    if not cliente_id: return "Cliente Desconocido"
    supabase = get_db_client()
    try:
        resp = supabase.table("clientes").select("nombre, codigo_cliente").eq("id", cliente_id).execute()
        
        if resp.data:
            cliente = resp.data[0]
            nombre = cliente.get('nombre', 'Sin Nombre')
            codigo = cliente.get('codigo_cliente')
            
            if codigo:
                return f"{codigo} - {nombre}"
            return nombre
            
        return "Cliente Desconocido"
    except:
        return "Cliente Desconocido"

def verificar_deuda_activa(cliente_id):
    if not cliente_id: return 0
    supabase = get_db_client()
    try:
        resp = supabase.table("prestamos").select("saldo_pendiente").eq("cliente_id", cliente_id).eq("estado", "activo").execute()
        if resp.data:
            return sum(float(p['saldo_pendiente']) for p in resp.data)
        return 0
    except:
        return 0

def obtener_siguiente_codigo_cliente(supabase):
    resp = supabase.table("clientes").select("codigo_cliente").not_.is_("codigo_cliente", "null").execute()
    max_num = 0
    if resp.data:
        for c in resp.data:
            try:
                num = int(c['codigo_cliente'].replace("CM", ""))
                if num > max_num:
                    max_num = num
            except:
                pass
    return f"CM{max_num + 1}"

def asegurar_codigo_cliente(supabase, cliente_id):
    resp = supabase.table("clientes").select("codigo_cliente").eq("id", cliente_id).execute()
    if resp.data and resp.data[0].get("codigo_cliente"):
        return resp.data[0]["codigo_cliente"]
            
    nuevo_codigo = obtener_siguiente_codigo_cliente(supabase)
    supabase.table("clientes").update({"codigo_cliente": nuevo_codigo}).eq("id", cliente_id).execute()
    return nuevo_codigo

def generar_codigo_prestamo(supabase, cliente_id, codigo_cliente):
    resp = supabase.table("prestamos").select("id").eq("cliente_id", cliente_id).execute()
    numero_prestamo = len(resp.data) + 1
    return f"{codigo_cliente}-{numero_prestamo:02d}"

def ejecutar_aprobacion_final(solicitud, cliente_id, es_fusion=False, datos_editados=None):
    supabase = get_db_client()
    try:
        monto = float(datos_editados['monto']) if datos_editados else float(solicitud['monto_solicitado'])
        tasa_prop = float(datos_editados['tasa']) if datos_editados else float(solicitud['tasa_propuesta'])
        plazo = int(datos_editados['plazo']) if datos_editados else int(solicitud['plazo_dias'])
        modalidad = datos_editados['modalidad'] if datos_editados else solicitud.get('modalidad', 'Diario')
        
        id_cobrador_vendedor = solicitud['cobrador_id'] 
        datos_json = solicitud.get('datos_nuevo_cliente') or {}
        
        codigo_cliente_final = None 

        if es_fusion:
            codigo_cliente_final = asegurar_codigo_cliente(supabase, cliente_id)
            supabase.table("clientes").update({
                "ultima_cantidad_prestada": monto,
                "referencias": datos_json.get('referencias', ''),
                "telefono": datos_json.get('telefono', ''),
                "creado_por": id_cobrador_vendedor
            }).eq("id", cliente_id).execute()
            
        elif not cliente_id:
            codigo_cliente_final = obtener_siguiente_codigo_cliente(supabase)
            nuevo_cliente = {
                "codigo_cliente": codigo_cliente_final,
                "nombre": datos_json.get('nombre', 'Sin Nombre'),
                "cedula": datos_json.get('cedula', 'N/A'),
                "telefono": datos_json.get('telefono', ''),
                "direccion": datos_json.get('direccion', ''),
                "referencias": datos_json.get('referencias', ''),
                
                # 👇 ¡Líneas agregadas con éxito! 👇
                "contacto_emergencia": datos_json.get('contacto_emergencia', ''),
                "telefono_emergencia": datos_json.get('telefono_emergencia', ''),
                # 👆 ============================ 👆
                
                "estado_cartera": "activo",
                "ultima_cantidad_prestada": monto,
                "creado_por": id_cobrador_vendedor,
                "fecha_registro": str(datetime.now())
            }
            resp_cliente = supabase.table("clientes").insert(nuevo_cliente).execute()
            cliente_id = resp_cliente.data[0]['id']
        else:
            codigo_cliente_final = asegurar_codigo_cliente(supabase, cliente_id)
            supabase.table("clientes").update({
                "ultima_cantidad_prestada": monto,
                "creado_por": id_cobrador_vendedor 
            }).eq("id", cliente_id).execute()

        tasa_decimal = tasa_prop / 100
        total_deuda = monto * (1 + tasa_decimal)
        
        if modalidad == 'Semanal':
            cuota = total_deuda / (plazo / 7 if (plazo/7) > 0 else 1)
        else:
            cuota = total_deuda / plazo

        codigo_prestamo_final = generar_codigo_prestamo(supabase, cliente_id, codigo_cliente_final)

        nuevo_prestamo = {
            "codigo_prestamo": codigo_prestamo_final,
            "cliente_id": cliente_id,
            "cobrador_id": id_cobrador_vendedor,
            "monto_prestado": monto,
            "tasa_interes": tasa_prop,
            "plazo_dias": plazo,
            "monto_total_deuda": total_deuda,
            "saldo_pendiente": total_deuda,
            "monto_cuota": cuota,
            "modalidad": modalidad,
            "estado": "activo",
            "fecha_inicio": datetime.now().strftime('%Y-%m-%d'),
            "fecha_vencimiento": (datetime.now() + timedelta(days=plazo)).strftime('%Y-%m-%d')
        }
        supabase.table("prestamos").insert(nuevo_prestamo).execute()
        supabase.table("solicitudes").update({"estado": "aprobada"}).eq("id", solicitud['id']).execute()
        
        st.success(f"Aprobada. Cliente: {codigo_cliente_final} | Préstamo: {codigo_prestamo_final}")
        time.sleep(1.5) 
        st.rerun()
    except Exception as e:
        st.error(f"Error técnico: {e}")

def rechazar_solicitud(solicitud_id, motivo=""):
    supabase = get_db_client()
    try:
        supabase.table("solicitudes").update({
            "estado": "rechazada",
            "motivo_rechazo": motivo
        }).eq("id", solicitud_id).execute()
        st.toast("Solicitud rechazada.")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

def resolver_alerta(solicitud_id, cliente_id, accion):
    supabase = get_db_client()
    try:
        if accion == "desbloquear":
            supabase.table("clientes").update({"estado_cartera": "activo"}).eq("id", cliente_id).execute()
            msg = "Cliente reactivado exitosamente."
        elif accion == "mantener_bloqueo":
            msg = "Bloqueo mantenido por decisión administrativa."

        supabase.table("solicitudes").update({
            "estado": "resuelto_alerta",
            "motivo_rechazo": f"Acción Admin: {accion}" 
        }).eq("id", solicitud_id).execute()

        st.success(msg)
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Error al resolver alerta: {e}")

def archivar_notificacion(solicitud_id):
    supabase = get_db_client()
    try:
        supabase.table("solicitudes").update({
            "estado": "rechazada", 
            "motivo_rechazo": "PAGO_REVISADO_ADMIN"
        }).eq("id", solicitud_id).execute()
        
        st.toast("Notificación archivada.")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Error al archivar: {e}")

def archivar_notificacion_auto(solicitud_id):
    supabase = get_db_client()
    try:
        supabase.table("solicitudes").update({
            "estado": "archivada", # Ya no dice rechazada, para no manchar métricas
            "motivo_rechazo": "VISTO_POR_ADMIN_AUTO"
        }).eq("id", solicitud_id).execute()
        
        st.toast("Notificación de préstamo archivada.")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Error al archivar: {e}")        

def alternar_permiso_horario(usuario_id, estado_actual):
    supabase = get_db_client()
    try:
        supabase.table("usuarios").update({"permiso_fuera_horario": not estado_actual}).eq("id", usuario_id).execute()
        st.toast("Permiso actualizado correctamente.")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Error al actualizar permiso: {e}")

def aprobar_solicitud_permiso(solicitud_id, cobrador_id):
    supabase = get_db_client()
    try:
        supabase.table("usuarios").update({"permiso_fuera_horario": True}).eq("id", cobrador_id).execute()
        supabase.table("solicitudes").update({
            "estado": "aprobada", 
            "motivo_rechazo": "Permiso Concedido"
        }).eq("id", solicitud_id).execute()
        
        st.success("✅ Permiso de horario concedido exitosamente.")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Error al aprobar permiso: {e}")

# ==========================================
# 2. COMPONENTES VISUALES
# ==========================================

def procesar_fila_notificacion_pago(notif):
    cliente_nombre = obtener_nombre_cliente(notif.get('id_cliente_existente'))
    cobrador_nombre = obtener_nombre_cobrador(notif.get('cobrador_id'))
    fecha = (notif.get('fecha_solicitud') or '')[:16].replace('T', ' ')
    monto_pagado = float(notif.get('monto_solicitado') or 0)
    
    datos_extra = notif.get('datos_nuevo_cliente') or {}
    nota = datos_extra.get('nota', 'Sin nota')
    
    # MODIFICADO: Ahora es una fila expandible en lugar de una tarjeta enorme
    titulo_expander = f"💰 PAGO REGISTRADO | {fecha[:10]} | {cliente_nombre} | C$ {monto_pagado:,.2f}"
    
    with st.expander(titulo_expander, expanded=False):
        st.markdown(f"""
            <div style="padding: 10px; border-left: 3px solid #4CAF50; background-color: #fafafa; border-radius: 4px; margin-bottom: 10px;">
                <p class="texto-secundario" style="margin-bottom: 5px;"><strong>Cobrador:</strong> {cobrador_nombre} | <strong>Hora exacta:</strong> {fecha}</p>
                <div style="font-size: 16px; font-weight: 700; color: #1b5e20; margin-bottom: 5px;">Monto Ingresado: C$ {monto_pagado:,.2f}</div>
                <p style="color: #616161; font-style: italic; margin: 0;">Nota: "{nota}"</p>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("Archivar Notificación", key=f"archivar_{notif['id']}", type="primary", use_container_width=True):
            archivar_notificacion(notif['id'])
    st.write("") # Pequeño espacio entre filas

def procesar_fila_notificacion_auto(sol):
    cliente_nombre = obtener_nombre_cliente(sol.get('id_cliente_existente'))
    if sol.get('tipo_solicitud') == 'notificacion_auto_nuevo': # Por si es un cliente nuevo
        datos_cliente = sol.get('datos_nuevo_cliente') or {}
        cliente_nombre = datos_cliente.get('nombre', 'Nuevo Cliente')

    cobrador_nombre = obtener_nombre_cobrador(sol.get('cobrador_id'))
    fecha = (sol.get('fecha_solicitud') or '')[:16].replace('T', ' ')
    monto = float(sol.get('monto_solicitado') or 0)
    
    titulo_expander = f"⚡ AUTO-APROBADO | {fecha[:10]} | {cliente_nombre} | C$ {monto:,.2f}"
    
    with st.expander(titulo_expander, expanded=False):
        st.markdown(f"""
            <div style="padding: 10px; border-left: 3px solid #1976d2; background-color: #e3f2fd; border-radius: 4px; margin-bottom: 10px;">
                <div class="titulo-box" style="color: #0d47a1;">PRÉSTAMO CREADO SIN APROBACIÓN (PERMISO ESPECIAL)</div>
                <p class="texto-secundario" style="margin-bottom: 5px;"><strong>Cobrador:</strong> {cobrador_nombre} | <strong>Hora:</strong> {fecha}</p>
                <div style="font-size: 16px; font-weight: 700; color: #1565c0; margin-bottom: 5px;">Monto Prestado: C$ {monto:,.2f}</div>
                <p style="color: #424242; font-size: 13px;">Este préstamo ya está activo en la base de datos y el saldo fue entregado. Solo requiere archivar esta notificación para limpiar la bandeja.</p>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("Entendido / Archivar", key=f"arch_auto_{sol['id']}", type="primary", use_container_width=True):
            archivar_notificacion_auto(sol['id'])
    st.write("")

def procesar_fila_alerta(alerta):
    cliente_nombre = obtener_nombre_cliente(alerta.get('id_cliente_existente'))
    cobrador_nombre = obtener_nombre_cobrador(alerta.get('cobrador_id'))
    fecha = (alerta.get('fecha_solicitud') or '')[:10]
    
    st.markdown(f"""
        <div class="alerta-mora-box">
            <div class="titulo-box" style="color: #c62828;">BLOQUEO AUTOMÁTICO: {cliente_nombre}</div>
            <p class="texto-secundario"><strong>Vendedor:</strong> {cobrador_nombre} | <strong>Fecha:</strong> {fecha}</p>
            <p style="color: #424242;">Causa: Acumulación de <strong>3 cuotas vencidas consecutivas</strong>.</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Desbloquear Cliente", key=f"unlock_{alerta['id']}", use_container_width=True):
            resolver_alerta(alerta['id'], alerta.get('id_cliente_existente'), "desbloquear")
    with c2:
        if st.button("Mantener Bloqueo", key=f"keep_{alerta['id']}", use_container_width=True):
             resolver_alerta(alerta['id'], alerta.get('id_cliente_existente'), "mantener_bloqueo")
    st.divider()

def procesar_fila_permiso(sol):
    cobrador_nombre = obtener_nombre_cobrador(sol.get('cobrador_id'))
    fecha = (sol.get('fecha_solicitud') or '')[:16].replace('T', ' ')
    
    st.markdown(f"""
        <div class="notificacion-pago-box" style="border-left-color: #fbc02d; background-color: #fff9c4;">
            <div class="titulo-box" style="color: #f57f17;">🚨 SOLICITUD DE ACCESO FUERA DE HORARIO</div>
            <p class="texto-secundario"><strong>Chofer:</strong> {cobrador_nombre} | <strong>Fecha:</strong> {fecha}</p>
            <p style="color: #424242;">Este cobrador está intentando acceder a la ruta fuera de la jornada habitual (8:00 AM - 4:00 PM).</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Rechazar Acceso", key=f"rej_perm_{sol['id']}", use_container_width=True):
            rechazar_solicitud(sol['id'], "Acceso denegado por el administrador")
    with c2:
        if st.button("Aprobar Permiso", key=f"apr_perm_{sol['id']}", type="primary", use_container_width=True):
            aprobar_solicitud_permiso(sol['id'], sol['cobrador_id'])
    st.divider()

def procesar_fila_solicitud(sol, info_reintento=None):
    es_nuevo = sol.get('tipo_solicitud') == 'nuevo'
    tipo_solicitud_texto = "NUEVO" if es_nuevo else "RECURRENTE"
    
    datos_cliente = sol.get('datos_nuevo_cliente') or {}
    nombre_cliente = datos_cliente.get('nombre', 'Sin Nombre') if es_nuevo else obtener_nombre_cliente(sol.get('id_cliente_existente'))
    
    monto = float(sol.get('monto_solicitado') or 0)
    tasa = float(sol.get('tasa_propuesta') or 0)
    plazo = int(sol.get('plazo_dias') or 1)
    modalidad = sol.get('modalidad', 'Diario')
    total_deuda = monto * (1 + (tasa / 100))
    cuota = total_deuda / (plazo / 7 if modalidad == 'Semanal' and plazo >= 7 else plazo)
    
    fecha_corta = (sol.get('fecha_solicitud') or '')[:10]
    
    etiqueta_estado = "[MODIFICADA]" if info_reintento else "[PENDIENTE]"
    
    # MODIFICADO: Título estructurado como pidió el cliente (Fecha | Tipo | CMxx - Nombre | Monto)
    titulo_fila = f"{etiqueta_estado} {fecha_corta} | {tipo_solicitud_texto} | {nombre_cliente} | C$ {monto:,.2f}"
    
    with st.expander(titulo_fila, expanded=False):
        if info_reintento:
            st.markdown(f"""
            <div class="reintento-box">
                <div class="titulo-box">SOLICITUD CORREGIDA POR VENDEDOR</div>
                Detalle de corrección sobre rechazo previo: <br>
                <em>Motivo anterior:</em> <b>"{info_reintento[1]}"</b>
            </div>
            """, unsafe_allow_html=True)

        nombre_cobrador = obtener_nombre_cobrador(sol.get('cobrador_id'))
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Perfil del Cliente")
            st.markdown(f"**Nombre:** {nombre_cliente}")
            if es_nuevo:
                st.markdown(f"**Cédula:** {datos_cliente.get('cedula', '--')}")
                st.markdown(f"**Teléfono:** {datos_cliente.get('telefono', '--')}")
                st.markdown(f"**Dirección:** {datos_cliente.get('direccion', '--')}")
                st.markdown(f"**Referencias:** {datos_cliente.get('referencias', '--')}")
                st.markdown(f"**Contacto Emergencia:** {datos_cliente.get('contacto_emergencia', '--')}")
                st.markdown(f"**Tel. Emergencia:** {datos_cliente.get('telefono_emergencia', '--')}")
            else:
                st.info("Cliente Existente / Recurrente")
                deuda_existente = verificar_deuda_activa(sol.get('id_cliente_existente'))
                if deuda_existente > 0:
                    # MODIFICADO: Uso de la alerta roja pálida (estilo paleta) en lugar de amarilla
                    st.markdown(f"""
                    <div class="alerta-saldo-box">
                        ⚠️ Saldo Actual Pendiente: C$ {deuda_existente:,.2f}
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown(f"**Agente:** {nombre_cobrador}")
        with c2:
            st.caption("Propuesta Económica")
            st.markdown(f"**Capital:** C$ {monto:,.2f}")
            st.markdown(f"**Plazo:** {plazo} días | **Tasa:** {tasa}%")
            st.markdown(f"**Modalidad:** {modalidad}")
            st.markdown(f"**Cuota:** C$ {cuota:,.2f}")

        st.divider()

        if st.session_state.get(f"alerta_duplicado_{sol['id']}"):
            st.error(f"Coincidencia de Cédula detectada: {st.session_state.get(f'nombre_duplicado_{sol['id']}')}")
            if st.button("Fusionar Historial y Aprobar", key=f"fus_{sol['id']}", type="primary"):
                ejecutar_aprobacion_final(sol, st.session_state.get(f"id_duplicado_{sol['id']}"), es_fusion=True)
        else:
            col_actions = st.columns([6, 1.5, 1.5]) 
            with col_actions[1]:
                with st.popover("Rechazar", use_container_width=True):
                    st.markdown("**Motivo del rechazo:**")
                    opciones_rechazo = [
                        "Capacidad de Pago Insuficiente",
                        "Historial Crediticio Negativo",
                        "Datos/Domicilio No Verificables",
                        "Zona de Alto Riesgo / Fuera de Ruta"
                    ]
                    razon_seleccionada = st.radio("Seleccione una opción:", opciones_rechazo, key=f"rad_rej_{sol['id']}")
                    detalle_extra = st.text_input("Observaciones adicionales:", key=f"txt_rej_{sol['id']}")
                    
                    if st.button("Confirmar Rechazo", key=f"btn_rej_{sol['id']}", type="secondary", use_container_width=True):
                        motivo_final = f"{razon_seleccionada}"
                        if detalle_extra: motivo_final += f" - {detalle_extra}"
                        rechazar_solicitud(sol['id'], motivo_final)
            
            with col_actions[2]:
                if st.button("Aprobar", key=f"apr_{sol['id']}", type="primary", use_container_width=True):
                    ejecutar_aprobacion_final(sol, sol.get('id_cliente_existente'))

# ==========================================
# 3. VISTA PRINCIPAL
# ==========================================

def mostrar_solicitudes():
    inject_custom_css()
    st.markdown("### Centro de Aprobaciones y Notificaciones")
    st.markdown("Gestión de créditos pendientes, alertas de riesgo, pagos y permisos.")
    
    supabase = get_db_client()
    
    resp_all = supabase.table("solicitudes").select("*").order("fecha_solicitud", desc=True).limit(200).execute()
    all_data = resp_all.data or []
    
    pendientes = [x for x in all_data if x.get('estado') == 'pendiente']
    alertas_mora = [x for x in pendientes if x.get('tipo_solicitud') == 'alerta_mora']
    notificaciones_pago = [x for x in pendientes if x.get('tipo_solicitud') == 'info_pago']
    solicitudes_permiso = [x for x in pendientes if x.get('tipo_solicitud') == 'permiso_horario']
    
    # 👇 NUEVA LÍNEA: Filtramos los auto-aprobados 👇
    notificaciones_auto = [x for x in pendientes if x.get('tipo_solicitud') in ['notificacion_auto', 'notificacion_auto_nuevo']]

    # Asegúrate de excluir esta nueva solicitud de la lista normal de préstamos a aprobar
    solicitudes_prestamo = [x for x in pendientes if x.get('tipo_solicitud') not in ['alerta_mora', 'info_pago', 'permiso_horario', 'notificacion_auto', 'notificacion_auto_nuevo']]

    rechazadas = [x for x in all_data if x.get('estado') == 'rechazada']
    historial = [x for x in all_data if x.get('estado') not in ['pendiente', 'resuelto_alerta']]

    tab_pendientes, tab_historial, tab_permisos = st.tabs(["Solicitudes Pendientes", "Historial de Operaciones", "Accesos de Choferes"])
    
    with tab_pendientes:
        if alertas_mora:
            st.error(f"Atención: {len(alertas_mora)} Alertas de Bloqueo requieren revisión.")
            for alerta in alertas_mora:
                procesar_fila_alerta(alerta)

        if notificaciones_pago:
            st.info(f"Pagos reportados pendientes de archivo: {len(notificaciones_pago)}")
            for notif in notificaciones_pago:
                procesar_fila_notificacion_pago(notif)

        if solicitudes_permiso:
            st.warning(f"⚠️ Tienes {len(solicitudes_permiso)} solicitudes de acceso fuera de horario.")
            for sol in solicitudes_permiso:
                procesar_fila_permiso(sol)        
        
        if notificaciones_auto:
            st.info(f"Préstamos Auto-Aprobados para tu revisión: {len(notificaciones_auto)}")
            for notif in notificaciones_auto:
                procesar_fila_notificacion_auto(notif)    


        if solicitudes_prestamo:
            st.markdown(f"#### Solicitudes de Crédito ({len(solicitudes_prestamo)})")
            for sol in solicitudes_prestamo:
                es_reintento = None
                if sol.get('tipo_solicitud') == 'recurrente' and sol.get('id_cliente_existente'):
                    match = next((r for r in rechazadas if r.get('id_cliente_existente') == sol.get('id_cliente_existente')), None)
                    if match:
                        es_reintento = (True, match.get('motivo_rechazo', 'Sin motivo'))
                elif sol.get('tipo_solicitud') == 'nuevo':
                    datos_s = sol.get('datos_nuevo_cliente') or {}
                    nom_nuevo = datos_s.get('nombre', '').strip().upper()
                    if nom_nuevo:
                        match = next((r for r in rechazadas if (r.get('datos_nuevo_cliente') or {}).get('nombre', '').strip().upper() == nom_nuevo), None)
                        if match:
                            es_reintento = (True, match.get('motivo_rechazo', 'Sin motivo'))

                procesar_fila_solicitud(sol, info_reintento=es_reintento)
        
        if not alertas_mora and not solicitudes_prestamo and not notificaciones_pago:
            st.success("Bandeja limpia. No hay tareas pendientes.")

    with tab_historial:
        if historial:
            mapa_cobradores = obtener_mapa_usuarios()
            data_procesada = []
            dict_rechazados = {}

            for item in historial:
                tipo = item.get('tipo_solicitud')
                estado_raw = item.get('estado', '')
                
                datos_n = item.get('datos_nuevo_cliente') or {}
                nota_cliente = datos_n.get('nota', '')
                motivo_r = item.get('motivo_rechazo', '')
                
                if tipo == 'alerta_mora':
                    cliente_nom = obtener_nombre_cliente(item.get('id_cliente_existente'))
                    monto_show, tasa_show = 0, 0
                    estado_show = "ALERTA RESUELTA"
                elif tipo == 'info_pago':
                    cliente_nom = obtener_nombre_cliente(item.get('id_cliente_existente'))
                    monto_show = float(item.get('monto_solicitado') or 0)
                    tasa_show = 0
                    estado_show = "PAGO REVISADO"
                else:
                    cliente_nom = datos_n.get('nombre', 'Nuevo') if tipo == 'nuevo' else obtener_nombre_cliente(item.get('id_cliente_existente'))
                    monto_show = float(item.get('monto_solicitado') or 0)
                    tasa_show = float(item.get('tasa_propuesta') or 0)
                    estado_show = estado_raw.upper()

                if estado_raw == 'rechazada':
                    dict_rechazados[item['id']] = f"{cliente_nom} (C$ {monto_show:,.2f})"

                data_procesada.append({
                    "Fecha": (item.get('fecha_solicitud') or '')[:10],
                    "Cliente": cliente_nom,
                    "Vendedor": mapa_cobradores.get(item.get('cobrador_id'), 'Desconocido'),
                    "Monto": monto_show,
                    "Estado": estado_show,
                    "Detalle": motivo_r or nota_cliente
                })
            
            df = pd.DataFrame(data_procesada)
            st.dataframe(
                df.style.map(lambda v: 'color: #d32f2f; font-weight: bold' if v == 'RECHAZADA' else ('color: #388e3c; font-weight: bold' if v == 'APROBADA' else ''), subset=['Estado']),
                use_container_width=True, hide_index=True
            )
            
            if dict_rechazados:
                st.write("")
                with st.expander("Panel de Renegociación (Solicitudes Rechazadas)", expanded=False):
                    id_sel = st.selectbox("Seleccione cliente para reevaluar:", options=list(dict_rechazados.keys()), format_func=lambda x: dict_rechazados[x])
                    if id_sel:
                        sol_obj = next(i for i in historial if i['id'] == id_sel)
                        if sol_obj.get('tipo_solicitud') not in ['alerta_mora', 'info_pago']:
                            col1, col2, col3 = st.columns(3)
                            n_monto = col1.number_input("Monto Ajustado", value=float(sol_obj.get('monto_solicitado') or 0), step=100.0)
                            n_tasa = col2.number_input("Tasa Interés %", value=float(sol_obj.get('tasa_propuesta') or 0), step=1.0)
                            n_plazo = col3.number_input("Plazo (Días)", value=int(sol_obj.get('plazo_dias') or 1), step=1)
                            
                            total_calculado = n_monto * (1 + (n_tasa/100))
                            mod_res = sol_obj.get('modalidad', 'Diario')
                            cuota_res = total_calculado / (n_plazo / 7 if mod_res == 'Semanal' and n_plazo >= 7 else n_plazo)
                            
                            st.markdown(f"""
                            <div class="calc-container">
                                <div class="titulo-box" style="margin-bottom: 10px;">PROYECCIÓN FINANCIERA</div>
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <div>
                                        <span class="texto-secundario">Total a recuperar:</span><br>
                                        <span class="resultado-destacado">C$ {total_calculado:,.2f}</span>
                                    </div>
                                    <div>
                                        <span class="texto-secundario">Cuota estimada ({mod_res}):</span><br>
                                        <span class="resultado-destacado">C$ {cuota_res:,.2f}</span>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.write("") 
                            
                            c_space1, c_btn, c_space2 = st.columns([1, 2, 1])
                            with c_btn:
                                if st.button("Aprobar con Nuevas Condiciones", type="primary", use_container_width=True):
                                    ejecutar_aprobacion_final(sol_obj, sol_obj.get('id_cliente_existente'), 
                                                              datos_editados={'monto': n_monto, 'tasa': n_tasa, 'plazo': n_plazo, 'modalidad': mod_res})
                        else:
                            st.warning("Esta opción solo está disponible para solicitudes de crédito.")
        else:
            st.info("No se encontró historial de operaciones.")

    with tab_permisos:
        st.markdown("#### Gestión de Acceso Fuera de Horario")
        st.info("Activa o desactiva el permiso para que los cobradores puedan usar la aplicación fuera de la jornada habitual (8:00 AM - 4:00 PM).")
        
        try:
            resp_usuarios = supabase.table("usuarios").select("id, nombre_completo, username, permiso_fuera_horario").eq("rol", "driver").execute()
            choferes = resp_usuarios.data or []
            
            if choferes:
                for c in choferes:
                    nombre = c.get('nombre_completo') or c.get('username')
                    estado = c.get('permiso_fuera_horario', False)
                    
                    col_info, col_btn = st.columns([3, 1])
                    with col_info:
                        st.markdown(f"**{nombre}**")
                        if estado:
                            st.markdown("<span style='color: #4CAF50; font-weight: bold;'>✅ Acceso Extraordinario Habilitado</span>", unsafe_allow_html=True)
                        else:
                            st.markdown("<span style='color: #616161;'>Bloqueo por horario normal activo</span>", unsafe_allow_html=True)
                    
                    with col_btn:
                        if estado:
                            if st.button("Revocar Acceso", key=f"rev_{c['id']}", use_container_width=True):
                                alternar_permiso_horario(c['id'], estado)
                        else:
                            if st.button("Conceder Acceso", key=f"con_{c['id']}", type="primary", use_container_width=True):
                                alternar_permiso_horario(c['id'], estado)
                    st.divider()
            else:
                st.write("No hay cobradores registrados en el sistema.")
        except Exception as e:
            st.error(f"Error al cargar usuarios: {e}")