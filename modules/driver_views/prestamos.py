import streamlit as st
import time 
import pandas as pd
from db_connection import get_db_client
from datetime import datetime, timedelta
from utils.telegram_sender import enviar_alerta_telegram 

# ==========================================
# 0. ESTILOS CSS (DISEÑO FINTECH)
# ==========================================
def cargar_estilos_ventas():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        .stApp { 
            background-color: #F7F3E9; 
            font-family: 'Inter', sans-serif;
            color: #0F3D3E;
        }

        /* --- CONTENEDORES --- */
        div[data-testid="stVerticalBlock"] > div {
            border-radius: 12px;
        }
        
        /* --- INPUTS & SELECTS --- */
        .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { 
            border-radius: 12px !important; 
            border: 1px solid #E0E0E0 !important; 
            background-color: #FFFFFF !important;
            color: #0F3D3E !important;
        }
        
        .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
            border-color: #4CAF50 !important;
            box-shadow: 0 4px 12px rgba(76, 175, 80, 0.1) !important;
        }

        /* --- BOTONES --- */
        .stButton button { 
            border-radius: 12px !important; 
            height: 48px !important; 
            font-weight: 600 !important; 
            transition: all 0.3s ease !important;
        }
        
        button[kind="primary"] {
            background-color: #4CAF50 !important;
            color: white !important;
            box-shadow: 0 4px 10px rgba(76, 175, 80, 0.2) !important;
            border: none !important;
        }
        button[kind="primary"]:hover {
            background-color: #4CAF50 !important;
            transform: translateY(-2px);
        }

        /* --- METRICAS SIMULADOR --- */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
            border: 1px solid #f0f0f0;
            text-align: center;
        }
        div[data-testid="stMetricLabel"] { font-size: 14px; color: #888; }
        div[data-testid="stMetricValue"] { font-size: 20px; color: #4CAF50; font-weight: 700; }

        /* --- ALERTA OBLIGATORIOS --- */
        .mandatory-note {
            font-size: 12px;
            color: #D32F2F;
            background-color: #FFEBEE;
            padding: 8px 12px;
            border-radius: 8px;
            display: inline-block;
            margin-bottom: 15px;
            font-weight: 600;
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. FUNCIONES LÓGICAS Y DE BÚSQUEDA
# ==========================================

def obtener_clientes_existentes():
    """Busca todos los clientes para el dropdown"""
    try:
        supabase = get_db_client()
        response = supabase.table("clientes").select("id, nombre, cedula").order("nombre").execute()
        return response.data if response.data else []
    except:
        return []

def buscar_coincidencias(nombre, cedula, telefono):
    """Busca si existe ALGUN cliente con el mismo nombre, cédula O teléfono."""
    if not any([nombre, cedula, telefono]): return []
    supabase = get_db_client()
    try:
        or_conditions = []
        if cedula and len(cedula) > 3: or_conditions.append(f"cedula.eq.{cedula.strip()}")
        if telefono and len(telefono) > 5: or_conditions.append(f"telefono.eq.{telefono.strip()}")
        if nombre and len(nombre) > 3:
            clean_name = nombre.strip().replace(" ", "%")
            or_conditions.append(f"nombre.ilike.*{clean_name}*") 
        if not or_conditions: return []
        query_string = ",".join(or_conditions)
        r = supabase.table("clientes").select("*").or_(query_string).execute()
        return r.data 
    except Exception as e:
        print(f"Error buscando duplicados: {e}")
        return []

def obtener_siguiente_codigo_cliente(supabase):
    resp = supabase.table("clientes").select("codigo_cliente").execute()
    max_num = 0
    if resp.data:
        for c in resp.data:
            cod = c.get('codigo_cliente')
            if cod and isinstance(cod, str) and cod.startswith("CM"):
                try:
                    num = int(cod.replace("CM", ""))
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

# ==========================================
# 2. POP-UP DE CONFIRMACIÓN (CON REFRESH RÁPIDO)
# ==========================================

def limpiar_formulario():
    """Limpia los inputs del formulario y variables de sesión conflictivas."""
    keys = [
        "input_nombre",
        "input_cedula",
        "input_telefono",
        "input_direccion",
        "input_referencias",
        "input_contacto_emerg",
        "input_tel_emerg",
        "input_monto",
        "input_tasa",
        "input_plazo",
        "input_modalidad",
        "cliente_existente_selectbox",
        "tipo_cliente_radio",
        "alerta_duplicado_activa",
        "datos_duplicados_encontrados"
    ]
    
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]

@st.dialog("✅ Transacción Completada")
def mostrar_popup_solicitud_exito(tipo, nombre_cliente, monto, auto_aprobado):
    st.balloons()
    
    if auto_aprobado:
        icono = "✨"
        titulo = "Préstamo Auto-Aprobado"
        color = "#4CAF50"
        subtitulo = "El dinero se descontó de tu caja"
    else:
        icono = "⏳"
        titulo = "Solicitud Enviada"
        color = "#FFA000"
        subtitulo = "Pendiente de revisión por Administración"

    # 🔧 EL CAMBIO ESTÁ AQUÍ: Todo el HTML sin sangría (pegado a la izquierda)
    html_content = f"""
<div style="text-align: center; padding: 20px 10px;">
<div style="color: {color}; font-size: 50px; margin-bottom: 10px;">{icono}</div>
<h3 style="color: #0F3D3E; margin: 0; font-weight: 700; letter-spacing: -0.5px;">{titulo}</h3>
<h1 style="color: {color}; font-size: 42px; font-weight: 800; margin: 10px 0 5px 0;">C$ {monto:,.2f}</h1>
<p style="color: #888; font-size: 13px; margin-bottom: 25px;">{subtitulo}</p>

<div style="background: #FAFAFA; padding: 20px; border-radius: 16px; text-align: left; border: 1px solid #f0f0f0;">
<div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
<span style="color: #888; font-size: 14px;">Cliente</span>
<span style="color: #0F3D3E; font-weight: 600; text-align: right;">{nombre_cliente}</span>
</div>
<div style="width: 100%; height: 1px; background: #eee; margin-bottom: 12px;"></div>
<div style="display: flex; justify-content: space-between; align-items: center;">
<span style="color: #888; font-size: 14px;">Tipo</span>
<span style="color: #0F3D3E; font-weight: 600; font-size: 14px;">{tipo}</span>
</div>
</div>
</div>
"""
    
    # Renderizamos el HTML corregido
    st.markdown(html_content, unsafe_allow_html=True)
    
    if st.button("Finalizar", type="primary", use_container_width=True):
        limpiar_formulario()
        
        if 'solicitud_exito' in st.session_state:
            del st.session_state['solicitud_exito']
            
        st.rerun()

# ==========================================
# 3. LÓGICA DE GUARDADO
# ==========================================

def guardar_solicitud_sql(tipo, id_existente, json_nuevo, monto, tasa, dias, modalidad, duplicado_ignorado=False):
    supabase = get_db_client()
    cobrador_id = st.session_state.get('user_id') 
    nombre_chofer = st.session_state.get('username', 'Chofer Desconocido')
    
    if not cobrador_id:
        st.error("❌ Error de sesión: No se identificó al cobrador.")
        return False

    try:
        user_req = supabase.table("usuarios").select("auto_aprobacion, saldo_actual").eq("id", cobrador_id).execute()
        if not user_req.data: 
            return False
            
        es_confianza = user_req.data[0].get("auto_aprobacion", False)
        saldo_chofer = float(user_req.data[0].get("saldo_actual", 0.0))

        nombre_real_cliente = ""
        if tipo == "nuevo" and json_nuevo:
            nombre_real_cliente = json_nuevo.get('nombre', 'Nuevo Cliente')
        else:
            cli_data = supabase.table("clientes").select("nombre").eq("id", id_existente).execute()
            nombre_real_cliente = cli_data.data[0]['nombre'] if cli_data.data else f"ID: {id_existente}"

        # =======================================================
        # 🟢 RUTA VERDE (AUTO-APROBACIÓN DIRECTA)
        # =======================================================
        if es_confianza:
            if saldo_chofer < monto:
                st.error(f"❌ No tienes saldo suficiente para auto-aprobar este préstamo. Saldo actual: C$ {saldo_chofer:,.2f}")
                return False
                
            cliente_final_id = id_existente
            codigo_cliente_final = None 

            if tipo == "nuevo" and json_nuevo:
                codigo_cliente_final = obtener_siguiente_codigo_cliente(supabase)
                json_nuevo['codigo_cliente'] = codigo_cliente_final
                json_nuevo['estado_cartera'] = "activo"
                json_nuevo['ultima_cantidad_prestada'] = monto
                json_nuevo['creado_por'] = cobrador_id
                
                res_cli = supabase.table("clientes").insert(json_nuevo).execute()
                if not res_cli.data:
                    st.error("Error al crear el cliente de forma automática.")
                    return False
                cliente_final_id = res_cli.data[0]['id']
            
            else:
                codigo_cliente_final = asegurar_codigo_cliente(supabase, cliente_final_id)
                supabase.table("clientes").update({
                    "ultima_cantidad_prestada": monto,
                    "creado_por": cobrador_id 
                }).eq("id", cliente_final_id).execute()

            interes_generado = float(monto) * (float(tasa) / 100)
            total_pagar = float(monto) + interes_generado
            cuota = total_pagar / dias if modalidad == "Diario" else total_pagar / (dias / 7)
            
            fecha_hoy = datetime.now()
            fecha_vencimiento = fecha_hoy + timedelta(days=dias)
            
            codigo_generado = generar_codigo_prestamo(supabase, cliente_final_id, codigo_cliente_final)

            datos_prestamo = {
                "cliente_id": cliente_final_id,
                "cobrador_id": cobrador_id, 
                "monto_prestado": monto,
                "tasa_interes": tasa,
                "plazo_dias": dias,
                "monto_total_deuda": total_pagar,
                "saldo_pendiente": total_pagar,
                "estado": "activo",
                "fecha_inicio": fecha_hoy.date().isoformat(),
                "fecha_vencimiento": fecha_vencimiento.date().isoformat(),
                "modalidad": modalidad,
                "monto_cuota": cuota,
                "codigo_prestamo": codigo_generado
            }
            
            res_prest = supabase.table("prestamos").insert(datos_prestamo).execute()
            
            if res_prest.data:
                nuevo_saldo = saldo_chofer - monto
                supabase.table("usuarios").update({"saldo_actual": nuevo_saldo}).eq("id", cobrador_id).execute()

                tipo_notificacion = "notificacion_auto_nuevo" if tipo == "nuevo" else "notificacion_auto"
                datos_aviso_admin = {
                    "cobrador_id": cobrador_id,
                    "tipo_solicitud": tipo_notificacion,
                    "id_cliente_existente": cliente_final_id,
                    "datos_nuevo_cliente": json_nuevo if tipo == "nuevo" else None,
                    "monto_solicitado": monto,
                    "tasa_propuesta": tasa,
                    "plazo_dias": dias,
                    "modalidad": modalidad,
                    "estado": "pendiente",
                    "fecha_solicitud": datetime.now().isoformat()
                }
                try:
                    supabase.table("solicitudes").insert(datos_aviso_admin).execute()
                except Exception as e:
                    pass

                try:
                    etiqueta_tipo = "(NUEVO)" if tipo == "nuevo" else "(EXISTENTE)"
                    mensaje = (
                        f"⚡ *PRÉSTAMO AUTO-APROBADO (Ruta Verde)*\n"
                        f"👤 *Cliente:* {nombre_real_cliente} {etiqueta_tipo}\n"
                        f"💰 *Monto:* C$ {monto:,.2f}\n"
                        f"🚛 *Chofer:* {nombre_chofer}\n"
                        f"🔑 *Código:* {codigo_generado}\n"
                        f"💳 *Saldo restante chofer:* C$ {nuevo_saldo:,.2f}\n\n" 
                        f"✅ _Préstamo creado automáticamente._"
                    )
                    enviar_alerta_telegram(mensaje, "")
                except Exception as e:
                    print("Error Telegram auto-aprobación:", e)
                    
                return {"auto_aprobado": True, "nombre_cliente": nombre_real_cliente, "monto": monto, "tipo": "NUEVO" if tipo == "nuevo" else "EXISTENTE"}
            return False

        # =======================================================
        # 🟠 RUTA NORMAL (VA A SOLICITUDES PARA EL ADMIN)
        # =======================================================
        else:
            datos_insertar = {
                "cobrador_id": cobrador_id,
                "tipo_solicitud": tipo,
                "id_cliente_existente": id_existente,
                "datos_nuevo_cliente": json_nuevo,
                "monto_solicitado": monto,
                "tasa_propuesta": tasa,
                "estado": "pendiente",
                "fecha_solicitud": datetime.now().isoformat(),
                "plazo_dias": dias,
                "modalidad": modalidad
            }
            
            response = supabase.table("solicitudes").insert(datos_insertar).execute()
            
            if response.data:
                try:
                    etiqueta_tipo = "(NUEVO)" if tipo == "nuevo" else "(EXISTENTE)"
                    alerta_duplicado = "\n⚠️ *ALERTA:* Driver reportó posible duplicado validado.\n" if duplicado_ignorado else ""

                    mensaje = (
                        f"🚨 *NUEVA SOLICITUD DE CRÉDITO*\n"
                        f"{alerta_duplicado}\n"
                        f"👤 *Cliente:* {nombre_real_cliente} {etiqueta_tipo}\n"
                        f"💰 *Monto:* C$ {monto:,.2f}\n"
                        f"🚛 *Chofer:* {nombre_chofer}\n"
                        f"📅 *Plazo:* {dias} días ({modalidad})\n"
                        f"📈 *Tasa:* {tasa}%\n\n"
                        f"👇 _Ingresa a la App para aprobar_"
                    )
                    link_app = "https://crecemas.streamlit.app/" 
                    enviar_alerta_telegram(mensaje, link_app)
                except Exception as e:
                    print(f"⚠️ Alerta Telegram falló pero se guardó en DB: {e}")

                return {"auto_aprobado": False, "nombre_cliente": nombre_real_cliente, "monto": monto, "tipo": "NUEVO" if tipo == "nuevo" else "EXISTENTE"}
            return False
            
    except Exception as e:
        st.error(f"❌ Error SQL: {e}")
        return False

# ==========================================
# 4. INTERFAZ PRINCIPAL
# ==========================================

def mostrar_ventas():
    if 'solicitud_exito' in st.session_state:
        d = st.session_state['solicitud_exito']
        mostrar_popup_solicitud_exito(
            d['tipo'], 
            d['nombre_cliente'], 
            d['monto'], 
            d['auto_aprobado']
        )

    cargar_estilos_ventas()
    
    if 'alerta_duplicado_activa' not in st.session_state:
        st.session_state['alerta_duplicado_activa'] = False
        st.session_state['datos_duplicados_encontrados'] = []

    datos_recuperados = st.session_state.get('datos_a_corregir') or {}
    modo_correccion = True if datos_recuperados else False

    if modo_correccion:
        with st.container():
            st.info("✏️ **Modo Corrección:** Estás editando una solicitud rechazada anteriormente.")
            if st.button("❌ Cancelar Edición", type="secondary"):
                del st.session_state['datos_a_corregir']
                st.rerun()
            st.markdown("---")

    st.markdown("## Nueva Solicitud")
    st.markdown('<div class="mandatory-note">ℹ️ Los campos marcados con (*) son obligatorios</div>', unsafe_allow_html=True)
    
    idx_tipo = 1 if datos_recuperados.get('es_recurrente') else 0
    
    tipo_cliente_visual = st.radio(
        "¿A quién le vamos a prestar?",
        ["🆕 Nuevo Cliente", "👤 Cliente Existente"],
        index=idx_tipo,
        horizontal=True,
        key="tipo_cliente_radio"
    )
    
    tipo_sql = "nuevo" if "Nuevo" in tipo_cliente_visual else "existente"
    id_cliente_existente = None
    datos_json_nuevo = None
    
    with st.container(border=True):
        if tipo_sql == "existente":
            st.subheader("🔍 Buscar en Base de Datos")
            lista = obtener_clientes_existentes()
            opciones = {f"{c['nombre']} | 🆔 {c.get('cedula','S/D')}": c['id'] for c in lista}
            
            idx_combo = 0
            id_recuperado = datos_recuperados.get('cliente_id_recurrente')
            if id_recuperado and id_recuperado in opciones.values():
                for k, v in opciones.items():
                    if v == id_recuperado:
                        try: idx_combo = list(opciones.keys()).index(k)
                        except: pass
                        break

            seleccion = st.selectbox(
                "Selecciona o escribe para buscar un cliente *", 
                options=["Seleccionar..."] + list(opciones.keys()), 
                index=idx_combo + 1 if idx_combo > 0 else 0,
                help="Puedes escribir el nombre o la cédula para filtrar la lista rápidamente.",
                key="cliente_existente_selectbox"
            )
            
            if seleccion != "Seleccionar...":
                id_cliente_existente = opciones[seleccion]
                st.info(f"✅ Cliente seleccionado: {seleccion.split('|')[0]}")
                st.session_state['alerta_duplicado_activa'] = False 

        else:
            st.subheader("📝 Datos Personales")
            val_nom = datos_recuperados.get('nombre', '')
            val_ced = datos_recuperados.get('cedula', '')
            val_tel = datos_recuperados.get('telefono', '')
            val_dir = datos_recuperados.get('direccion', '')
            val_ref = datos_recuperados.get('referencias', '')
            val_contacto_emergencia = datos_recuperados.get('contacto_emergencia', '') 
            val_tel_emergencia = datos_recuperados.get('telefono_emergencia', '') 

            # Inicializamos variables en session_state ANTES de los inputs
            if "input_nombre" not in st.session_state: st.session_state.input_nombre = val_nom
            if "input_cedula" not in st.session_state: st.session_state.input_cedula = val_ced
            if "input_telefono" not in st.session_state: st.session_state.input_telefono = val_tel
            if "input_direccion" not in st.session_state: st.session_state.input_direccion = val_dir
            if "input_contacto_emerg" not in st.session_state: st.session_state.input_contacto_emerg = val_contacto_emergencia
            if "input_tel_emerg" not in st.session_state: st.session_state.input_tel_emerg = val_tel_emergencia
            if "input_referencias" not in st.session_state: st.session_state.input_referencias = val_ref

            col_a, col_b = st.columns(2)
            with col_a:
                nombre_input = st.text_input("Nombre Completo *", placeholder="Ej: Juan Pérez", key="input_nombre")
                nombre = nombre_input.strip().upper() if nombre_input else ""
                cedula = st.text_input("Cédula *", placeholder="Ej: 001-000000-0000A", key="input_cedula").strip()
                
            with col_b:
                tel = st.text_input("Teléfono *", placeholder="Ej: 8888-8888", key="input_telefono").strip()
                dire = st.text_input("Dirección Domiciliar *", placeholder="Dirección exacta...", key="input_direccion")
            
            st.markdown("**Contacto de Emergencia**")
            col_c, col_d = st.columns(2)
            with col_c:
                contacto_emergencia = st.text_input("Nombre de Emergencia", placeholder="Ej: María López (Madre)", key="input_contacto_emerg")
            with col_d:
                telefono_emergencia = st.text_input("Teléfono de Emergencia", placeholder="Ej: 8888-9999", key="input_tel_emerg")

            st.write("")
            refs = st.text_area("Referencias Personales", height=80, placeholder="Opcional: Nombre de tienda, vecino, etc.", key="input_referencias")
            
            st.markdown("**Evidencia Fotográfica**")
            foto_doc = st.file_uploader("Subir foto de documento o negocio", type=['png', 'jpg', 'jpeg'], key="input_foto")
            
            datos_json_nuevo = {
                "nombre": nombre, "cedula": cedula, "telefono": tel,
                "direccion": dire, "referencias": refs,
                "contacto_emergencia": contacto_emergencia, 
                "telefono_emergencia": telefono_emergencia, 
                "tiene_foto": True if foto_doc else False 
            }

    st.write("") 
    st.subheader("💸 Condiciones del Crédito")
    
    raw_monto = float(datos_recuperados.get('monto', 1000.0))
    raw_tasa = int(datos_recuperados.get('tasa', 20))
    rec_dias = int(datos_recuperados.get('plazo', 30))
    rec_mod = datos_recuperados.get('modalidad', 'Diario')

    val_inicial_monto = max(100.0, raw_monto) 
    val_inicial_tasa = max(15, min(raw_tasa, 30))
    val_inicial_dias = max(5, min(rec_dias, 60))

    # Inicializamos números en session_state ANTES de los inputs
    if "input_monto" not in st.session_state: st.session_state.input_monto = val_inicial_monto
    if "input_tasa" not in st.session_state: st.session_state.input_tasa = val_inicial_tasa
    if "input_plazo" not in st.session_state: st.session_state.input_plazo = val_inicial_dias

    with st.container(border=True):
        col_monto, col_tasa = st.columns([0.6, 0.4])
        with col_monto:
            monto = st.number_input("Monto a Prestar (C$) *", min_value=100.0, step=100.0, key="input_monto")
        with col_tasa:
            tasa = st.slider("Tasa de Interés (%)", min_value=15, max_value=30, key="input_tasa")

        c_dias, c_freq = st.columns(2)
        with c_dias:
            dias = st.number_input("Plazo (Días)", min_value=5, max_value=60, step=1, key="input_plazo")
        
        with c_freq:
            lista_mod = ["Diario"]
            idx_mod = lista_mod.index(rec_mod) if rec_mod in lista_mod else 0
            modalidad = st.selectbox("Modalidad de Cobro", lista_mod, index=idx_mod, key="input_modalidad")

        interes_generado = monto * (tasa / 100)
        total_pagar = monto + interes_generado
        
        if modalidad == "Diario":
            cuota = total_pagar / dias
        else:
            semanas = dias / 7
            cuota = total_pagar / semanas if semanas > 0 else total_pagar

        st.markdown("---")
        st.markdown("#### 📊 Proyección de Pago")
        r1, r2, r3 = st.columns(3)
        r1.metric("Interés Total", f"C$ {interes_generado:,.2f}")
        r2.metric("Total a Pagar", f"C$ {total_pagar:,.2f}")
        r3.metric(f"Cuota {modalidad}", f"C$ {cuota:,.2f}")

    st.write("")

    if st.session_state['alerta_duplicado_activa'] and tipo_sql == "nuevo":
        with st.container(border=True):
            st.error("⚠️ **ALERTA: CLIENTES SIMILARES ENCONTRADOS**")
            st.markdown("El sistema encontró coincidencias en la base de datos:")
            
            if st.session_state['datos_duplicados_encontrados']:
                df_match = pd.DataFrame(st.session_state['datos_duplicados_encontrados'])
                st.dataframe(df_match[['nombre', 'cedula', 'telefono']], hide_index=True, use_container_width=True)
            
            st.markdown("¿Deseas registrarlo de todas formas?")
            col_d1, col_d2 = st.columns(2)
            if col_d1.button("🔙 Cancelar y Corregir", use_container_width=True):
                st.session_state['alerta_duplicado_activa'] = False
                st.rerun()
                
            if col_d2.button("⚠️ SÍ, CREAR DE TODAS FORMAS", type="primary", use_container_width=True):
                exito_datos = guardar_solicitud_sql(
                    tipo_sql, id_cliente_existente, datos_json_nuevo, 
                    monto, tasa, dias, modalidad, duplicado_ignorado=True
                )
                if exito_datos:
                    st.session_state['alerta_duplicado_activa'] = False
                    if 'datos_a_corregir' in st.session_state: del st.session_state['datos_a_corregir']
                    st.session_state['solicitud_exito'] = exito_datos
                    st.rerun()

    else:
        boton_texto = "🚀 Registrar Solicitud"
        if modo_correccion: boton_texto = "♻️ Actualizar Solicitud"

        if st.button(boton_texto, type="primary", use_container_width=True):
            error_msg = []
            
            if tipo_sql == "nuevo":
                if not datos_json_nuevo['nombre']: error_msg.append("El Nombre es obligatorio.")
                if not datos_json_nuevo['cedula']: error_msg.append("La Cédula es obligatoria.")
                if not datos_json_nuevo['telefono']: error_msg.append("El Teléfono es obligatorio.")
                if not datos_json_nuevo['direccion']: error_msg.append("La Dirección es obligatoria.")
                if not datos_json_nuevo['contacto_emergencia']: error_msg.append("El Nombre de Emergencia es obligatorio.")
                if not datos_json_nuevo['telefono_emergencia']: error_msg.append("El Teléfono de Emergencia es obligatorio.")

                if error_msg:
                    for e in error_msg: st.error(f"⚠️ {e}")
                    return 

                coincidencias = buscar_coincidencias(
                    datos_json_nuevo['nombre'], 
                    datos_json_nuevo['cedula'], 
                    datos_json_nuevo['telefono']
                )
                
                if coincidencias:
                    st.session_state['alerta_duplicado_activa'] = True
                    st.session_state['datos_duplicados_encontrados'] = coincidencias
                    st.rerun()
                    return

            elif tipo_sql == "existente":
                if not id_cliente_existente:
                    st.error("⚠️ Debes seleccionar un cliente de la lista.")
                    return

            exito_datos = guardar_solicitud_sql(
                tipo_sql, id_cliente_existente, datos_json_nuevo, 
                monto, tasa, dias, modalidad
            )
            
            if exito_datos:
                if 'datos_a_corregir' in st.session_state: del st.session_state['datos_a_corregir']
                st.session_state['solicitud_exito'] = exito_datos
                st.rerun()