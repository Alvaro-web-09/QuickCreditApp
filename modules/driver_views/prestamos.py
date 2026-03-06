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
        query_string = ",no".join(or_conditions)
        r = supabase.table("clientes").select("*").or_(query_string).execute()
        return r.data 
    except Exception as e:
        print(f"Error buscando duplicados: {e}")
        return []

# 👇 FUNCIONES PARA LOS CÓDIGOS CM CORREGIDAS 👇
def obtener_siguiente_codigo_cliente(supabase):
    # Traemos todos y filtramos de forma segura en Python
    resp = supabase.table("clientes").select("codigo_cliente").execute()
    max_num = 0
    if resp.data:
        for c in resp.data:
            cod = c.get('codigo_cliente')
            # Solo procesamos si el código existe y empieza con CM
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
# 2. LÓGICA DE GUARDADO (Backend) CORREGIDA
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

        # =======================================================
        # 🟢 RUTA VERDE (AUTO-APROBACIÓN DIRECTA)
        # =======================================================
        if es_confianza:
            if saldo_chofer < monto:
                st.error(f"❌ No tienes saldo suficiente para auto-aprobar este préstamo. Saldo actual: C$ {saldo_chofer:,.2f}")
                return False
                
            cliente_final_id = id_existente
            nombre_cliente = f"Cliente Existente (ID: {id_existente})"
            codigo_cliente_final = None 

            # A. Lógica para Cliente Nuevo
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
                nombre_cliente = json_nuevo.get('nombre', 'Nuevo Cliente')
            
            # B. Lógica para Cliente Existente
            else:
                codigo_cliente_final = asegurar_codigo_cliente(supabase, cliente_final_id)
                supabase.table("clientes").update({
                    "ultima_cantidad_prestada": monto,
                    "creado_por": cobrador_id 
                }).eq("id", cliente_final_id).execute()

            # C. Cálculos financieros y fechas
            interes_generado = float(monto) * (float(tasa) / 100)
            total_pagar = float(monto) + interes_generado
            cuota = total_pagar / dias if modalidad == "Diario" else total_pagar / (dias / 7)
            
            fecha_hoy = datetime.now()
            fecha_vencimiento = fecha_hoy + timedelta(days=dias)
            
            # D. Generamos el código CM de préstamo
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
                # 🚨 CORRECCIÓN CRÍTICA: Descontar el saldo del chofer
                nuevo_saldo = saldo_chofer - monto
                supabase.table("usuarios").update({"saldo_actual": nuevo_saldo}).eq("id", cobrador_id).execute()

                # 👇 NOTIFICACIÓN SILENCIOSA AL ADMIN 👇
                tipo_notificacion = "notificacion_auto_nuevo" if tipo == "nuevo" else "notificacion_auto"
                
                datos_aviso_admin = {
                    "cobrador_id": cobrador_id,
                    "tipo_solicitud": tipo_notificacion,
                    "id_cliente_existente": cliente_final_id,
                    "datos_nuevo_cliente": json_nuevo if tipo == "nuevo" else None,
                    "monto_solicitado": monto,
                    "tasa_propuesta": tasa,      # 🚨 AHORA SÍ LLEVA LA TASA
                    "plazo_dias": dias,          # 🚨 AHORA SÍ LLEVA LOS DÍAS
                    "modalidad": modalidad,      # 🚨 AHORA SÍ LLEVA LA MODALIDAD
                    "estado": "pendiente",       # 🚨 VUELVE A "PENDIENTE" PARA QUE LE SALGA AL ADMIN
                    "fecha_solicitud": datetime.now().isoformat()
                }
                try:
                    supabase.table("solicitudes").insert(datos_aviso_admin).execute()
                except Exception as e:
                    pass

                try:
                    mensaje = (
                        f"⚡ *PRÉSTAMO AUTO-APROBADO (Ruta Verde)*\n"
                        f"👤 *Cliente:* {nombre_cliente}\n"
                        f"💰 *Monto:* C$ {monto:,.2f}\n"
                        f"🚛 *Chofer:* {nombre_chofer}\n"
                        f"🔑 *Código:* {codigo_generado}\n"
                        f"💳 *Saldo restante chofer:* C$ {nuevo_saldo:,.2f}\n\n" 
                        f"✅ _Préstamo creado automáticamente._"
                    )
                    enviar_alerta_telegram(mensaje, "")
                except Exception as e:
                    print("Error Telegram auto-aprobación:", e)
                    
                return True
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
                    if tipo == "nuevo" and json_nuevo:
                        nombre_cliente = json_nuevo.get('nombre', 'Nuevo Cliente')
                    else:
                        nombre_cliente = f"Cliente Existente (ID: {id_existente})"

                    alerta_duplicado = "\n⚠️ *ALERTA:* Driver reportó posible duplicado validado.\n" if duplicado_ignorado else ""

                    mensaje = (
                        f"🚨 *NUEVA SOLICITUD DE CRÉDITO*\n"
                        f"{alerta_duplicado}\n"
                        f"👤 *Cliente:* {nombre_cliente}\n"
                        f"💰 *Monto:* C$ {monto:,.2f}\n"
                        f"🚛 *Chofer:* {nombre_chofer}\n"
                        f"📅 *Plazo:* {dias} días ({modalidad})\n\n"
                        f"👇 _Ingresa a la App para aprobar_"
                    )
                    link_app = "https://crecemas.streamlit.app/" 
                    enviar_alerta_telegram(mensaje, link_app)
                except Exception as e:
                    print(f"⚠️ Alerta Telegram falló pero se guardó en DB: {e}")

                return True
            return False
            
    except Exception as e:
        st.error(f"❌ Error SQL: {e}")
        return False

# ==========================================
# 3. INTERFAZ PRINCIPAL
# ==========================================

def mostrar_ventas():
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
        horizontal=True
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
                help="Puedes escribir el nombre o la cédula para filtrar la lista rápidamente."
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

            col_a, col_b = st.columns(2)
            with col_a:
                nombre_input = st.text_input("Nombre Completo *", value=val_nom, placeholder="Ej: Juan Pérez")
                nombre = nombre_input.strip().upper() if nombre_input else ""
                cedula = st.text_input("Cédula *", value=val_ced, placeholder="Ej: 001-000000-0000A").strip()
                
            with col_b:
                tel = st.text_input("Teléfono *", value=val_tel, placeholder="Ej: 8888-8888").strip()
                dire = st.text_input("Dirección Domiciliar *", value=val_dir, placeholder="Dirección exacta...")
            
            st.markdown("**Contacto de Emergencia**")
            col_c, col_d = st.columns(2)
            with col_c:
                contacto_emergencia = st.text_input("Nombre de Emergencia", value=val_contacto_emergencia, placeholder="Ej: María López (Madre)")
            with col_d:
                telefono_emergencia = st.text_input("Teléfono de Emergencia", value=val_tel_emergencia, placeholder="Ej: 8888-9999")

            st.write("")
            refs = st.text_area("Referencias Personales", value=val_ref, height=80, placeholder="Opcional: Nombre de tienda, vecino, etc.")
            
            st.markdown("**Evidencia Fotográfica**")
            foto_doc = st.file_uploader("Subir foto de documento o negocio", type=['png', 'jpg', 'jpeg'])
            
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
    val_inicial_tasa = max(15, min(raw_tasa, 20))

    with st.container(border=True):
        col_monto, col_tasa = st.columns([0.6, 0.4])
        with col_monto:
            monto = st.number_input("Monto a Prestar (C$) *", min_value=100.0, step=100.0, value=val_inicial_monto)
        with col_tasa:
            tasa = st.slider("Tasa de Interés (%)", min_value=15, max_value=20, value=val_inicial_tasa)

        c_dias, c_freq = st.columns(2)
        with c_dias:
            lista_dias = [28, 29, 30, 31]
            idx_dias = lista_dias.index(rec_dias) if rec_dias in lista_dias else 1
            dias = st.selectbox("Plazo (Días)", lista_dias, index=idx_dias)
        
        with c_freq:
            lista_mod = ["Diario", "Semanal"]
            idx_mod = lista_mod.index(rec_mod) if rec_mod in lista_mod else 0
            modalidad = st.selectbox("Modalidad de Cobro", lista_mod, index=idx_mod)

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
                exito = guardar_solicitud_sql(
                    tipo_sql, id_cliente_existente, datos_json_nuevo, 
                    monto, tasa, dias, modalidad, duplicado_ignorado=True
                )
                if exito:
                    st.session_state['alerta_duplicado_activa'] = False
                    if 'datos_a_corregir' in st.session_state: del st.session_state['datos_a_corregir']
                    st.balloons()
                    st.success("✅ Solicitud forzada creada correctamente.")
                    time.sleep(2)
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

            exito = guardar_solicitud_sql(
                tipo_sql, id_cliente_existente, datos_json_nuevo, 
                monto, tasa, dias, modalidad
            )
            
            if exito:
                if 'datos_a_corregir' in st.session_state: del st.session_state['datos_a_corregir']
                st.balloons()
                st.success("✅ Solicitud enviada correctamente.")
                time.sleep(2) 
                st.rerun()