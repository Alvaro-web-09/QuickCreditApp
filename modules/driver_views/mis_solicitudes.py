import streamlit as st
from datetime import datetime
from db_connection import get_db_client
import base64
import time

# ==========================================
# 0. ESTILOS VISUALES (DASHBOARD ALINEADO)
# ==========================================
def cargar_estilos_modernos():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
        .stApp { font-family: 'Inter', sans-serif; }

        /* --- ESTILO DE LOS KPI (DASHBOARD) --- */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 10px;
            padding: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            text-align: center;
            
            /* AJUSTE CLAVE DE ALINEACIÓN */
            min-height: 140px; 
            display: flex;
            flex-direction: column;
            justify-content: center; 
            align-items: center;
        }
        
        div[data-testid="stMetricLabel"] {
            display: flex;
            justify-content: center;
            width: 100%;
        }
        
        div[data-testid="stMetricLabel"] p {
            font-size: 14px;
            font-weight: 600;
            color: #666;
            margin-bottom: 0px;
        }

        div[data-testid="stMetricValue"] {
            font-size: 32px;
            font-weight: 700;
            color: #333;
        }

        div[data-testid="stMetricDelta"] {
            font-size: 13px;
            background-color: #f0f2f6; 
            padding: 2px 8px;
            border-radius: 6px;
            margin-top: 8px;
            color: #555 !important;
        }
        
        div[data-testid="stMetricDelta"] svg {
            display: none;
        }

        /* --- ESTILO DE LOS EXPANDERS (LISTA) --- */
        div[data-testid="stExpander"] {
            background-color: transparent;
            border: none;
            margin-bottom: 8px;
        }
        
        .streamlit-expanderHeader {
            background-color: #FFFFFF !important;
            border: 1px solid #E0E0E0;
            border-radius: 10px !important;
            padding: 15px !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.03);
            font-size: 16px;
            color: #333;
            transition: all 0.2s;
        }
        
        .streamlit-expanderHeader:hover {
            border-color: #4CAF50;
            box-shadow: 0 4px 8px rgba(76, 175, 80, 0.1);
        }

        div[data-testid="stExpanderDetails"] {
            background-color: #F9F9F9;
            border-radius: 0 0 10px 10px;
            border: 1px solid #E0E0E0;
            border-top: none;
            margin-top: -5px;
            padding: 20px;
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. CONFIGURACIÓN Y SONIDOS
# ==========================================

# 👇 NUEVO ESTADO AGREGADO PARA LA RUTA VERDE 👇
ESTADOS_CONFIG = {
    "pendiente": {"color": "orange", "icono": "🟠", "texto": "En Revisión"},
    "aprobada":  {"color": "green", "icono": "🟢", "texto": "Aprobado"},
    "rechazada": {"color": "red", "icono": "🔴", "texto": "Rechazada"},
    "auto_aprobado": {"color": "blue", "icono": "⚡", "texto": "Auto-Aprobado (Ruta Verde)"}
}

def reproducir_sonido(tipo):
    sound_url = ""
    if tipo == "success":
        sound_url = "https://www.myinstants.com/media/sounds/ka-ching.mp3"
    elif tipo == "error":
        sound_url = "https://www.myinstants.com/media/sounds/windows-error-sound.mp3"
    elif tipo == "notification":
        sound_url = "https://www.myinstants.com/media/sounds/discord-notification.mp3"
    
    if sound_url:
        st.markdown(f"""
            <audio autoplay style="display:none;">
                <source src="{sound_url}" type="audio/mpeg">
            </audio>
        """, unsafe_allow_html=True)

# ==========================================
# 2. FUNCIÓN PRINCIPAL
# ==========================================

def mostrar_mis_solicitudes():
    cargar_estilos_modernos() 

    if st.session_state.get('mensaje_correccion_activo'):
        reproducir_sonido("notification")
        st.success("✅ **Solicitud Cargada:** Dirígete a la pestaña 'Nueva Solicitud' para modificarla y enviarla de nuevo.")
        st.toast("Datos cargados. Ve a Nueva Solicitud.", icon="📝")
        st.session_state['mensaje_correccion_activo'] = False
    
    st.subheader("📋 Historial de Solicitudes")
    
    if 'solicitudes_ocultas' not in st.session_state:
        st.session_state['solicitudes_ocultas'] = set()
    if 'datos_a_corregir' not in st.session_state:
        st.session_state['datos_a_corregir'] = None
    if 'memoria_estados' not in st.session_state:
        st.session_state['memoria_estados'] = {}

    user_id = st.session_state.get('user_id')
    if not user_id:
        st.error("No hay sesión activa.")
        return

    # --- CARGA DE DATOS ---
    supabase = get_db_client()
    try:
        response = supabase.table("solicitudes")\
            .select("*, clientes(nombre)")\
            .eq("cobrador_id", user_id)\
            .order("fecha_solicitud", desc=True)\
            .limit(50)\
            .execute()
        datos = response.data or []
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return

    # 👇 CLASIFICACIÓN DE ESTADO VISUAL (A PRUEBA DE BALAS) 👇
    for s in datos:
        estado_db = str(s.get('estado', '')).strip().lower()
        tipo_sol = str(s.get('tipo_solicitud', '')).strip().lower()
        
        # 1. Si la BD ya lo marca como alguna variante de auto aprobado
        if estado_db in ['auto_aprobada', 'auto_aprobado', 'auto-aprobado']:
            s['estado_visual'] = 'auto_aprobado'
            
        # 2. O si está pendiente pero es una notificación automática (la magia del rayito)
        elif estado_db == 'pendiente' and tipo_sol.startswith('notificacion_auto'):
            s['estado_visual'] = 'auto_aprobado'
            
        # 3. Si es cualquier otra cosa (pendiente, aprobada, rechazada)
        else:
            s['estado_visual'] = estado_db

    # --- SONIDOS Y REVIVIR SOLICITUDES ---
    sonido_a_reproducir = None
    for s in datos:
        s_id = s['id']
        estado_actual = s['estado_visual']
        
        if s_id in st.session_state['memoria_estados']:
            estado_anterior = st.session_state['memoria_estados'][s_id]
            
            # Si ahora está aprobada (pero antes no lo estaba, ya sea pendiente o rechazada)
            if estado_anterior != 'aprobada' and estado_actual == 'aprobada':
                sonido_a_reproducir = "success"
                
                # ¡MAGIA AQUÍ! Si el driver la había ocultado cuando estaba rechazada, la sacamos de ocultas para que la vuelva a ver.
                if s_id in st.session_state['solicitudes_ocultas']:
                    st.session_state['solicitudes_ocultas'].remove(s_id)
                    
            # Si pasó de pendiente a rechazada
            elif estado_anterior == 'pendiente' and estado_actual == 'rechazada':
                sonido_a_reproducir = "error"
                
        st.session_state['memoria_estados'][s_id] = estado_actual

    if sonido_a_reproducir:
        reproducir_sonido(sonido_a_reproducir)
        if sonido_a_reproducir == "success":
            st.toast("¡Solicitud Aprobada!", icon="🤑")
        else:
            st.toast("Solicitud Rechazada", icon="🚫")

    # ==========================================
    # DASHBOARD (KPIs) ALINEADOS
    # ==========================================
    pendientes = [d for d in datos if d['estado_visual'] == 'pendiente']
    # Sumamos las auto_aprobadas al conteo de Aprobadas
    aprobadas = [d for d in datos if d['estado_visual'] in ['aprobada', 'auto_aprobado']]
    rechazadas = [d for d in datos if d['estado_visual'] == 'rechazada']
    
    monto_pendiente_total = sum(d['monto_solicitado'] for d in pendientes)

    k1, k2, k3 = st.columns(3)
    
    k1.metric("⏳ En Revisión", f"{len(pendientes)}", f"C$ {monto_pendiente_total:,.0f}", delta_color="off")
    k2.metric("✅ Aprobadas / ⚡ Auto", f"{len(aprobadas)}")
    k3.metric("🚫 Rechazadas", f"{len(rechazadas)}")
    
    st.markdown("---")
    # ==========================================

    if not datos:
        st.info("📭 Aún no has realizado solicitudes.")
        return

    # --- FILTROS ---
    datos_activos = [s for s in datos if s['id'] not in st.session_state['solicitudes_ocultas']]

    col_filter, col_refresh = st.columns([0.8, 0.2])
    with col_filter:
        filtro_estado = st.radio(
            "Filtro",
            ["Todas", "Pendientes", "Aprobadas", "Rechazadas"],
            horizontal=True,
            label_visibility="collapsed"
        )
    with col_refresh:
        if st.button("🔄", help="Actualizar lista"):
            st.rerun()

    lista_mostrar = []
    if filtro_estado == "Pendientes":
        lista_mostrar = [s for s in datos_activos if s['estado_visual'] == 'pendiente']
    elif filtro_estado == "Aprobadas":
        lista_mostrar = [s for s in datos_activos if s['estado_visual'] in ['aprobada', 'auto_aprobado']]
    elif filtro_estado == "Rechazadas":
        lista_mostrar = [s for s in datos_activos if s['estado_visual'] == 'rechazada']
    else:
        lista_mostrar = datos_activos

    if not lista_mostrar:
        st.caption("No hay solicitudes en esta categoría.")
        return

    # --- LISTA ---
    for s in lista_mostrar:
        estado_v = s['estado_visual']
        conf = ESTADOS_CONFIG.get(estado_v, {"color": "grey", "icono": "❓", "texto": "Desconocido"})
        
        data_cliente = s.get('clientes') or {}
        data_nuevo = s.get('datos_nuevo_cliente') or {}
        nombre = data_cliente.get('nombre') or data_nuevo.get('nombre') or "Sin Nombre"
        
        fecha_corta = "Hoy"
        if s.get('fecha_solicitud'):
            try:
                dt = datetime.fromisoformat(s.get('fecha_solicitud').replace('Z', ''))
                diff = datetime.now() - dt
                if diff.days == 0: fecha_corta = dt.strftime("%I:%M %p")
                elif diff.days == 1: fecha_corta = "Ayer"
                else: fecha_corta = dt.strftime("%d/%m")
            except: pass

        titulo_expander = f"{conf['icono']}  **{nombre}** —   C$ {s['monto_solicitado']:,.0f}  _({fecha_corta})_"
        
        with st.expander(titulo_expander, expanded=False):
            st.markdown(f"**Estado:** :{conf['color']}[{conf['texto']}]")
            st.caption(f"Modalidad: {s['modalidad']}")
            
            monto = s.get('monto_solicitado') or 0  
            tasa = s.get('tasa_propuesta') or 20    
            total = monto + (monto * (tasa/100))
            
            col_metrics = st.columns(3)
            col_metrics[0].metric("Plazo", f"{s['plazo_dias']} días")
            col_metrics[1].metric("Interés", f"{tasa}%")
            col_metrics[2].metric("Total", f"C$ {total:,.0f}")
            
            st.divider()

            if estado_v == 'rechazada':
                 st.error(f"Motivo: {s.get('motivo_rechazo', 'Sin motivo')}")
                 c_btn1, c_btn2 = st.columns(2)
                 
                 if c_btn1.button("♻️ Corregir", key=f"fix_{s['id']}", use_container_width=True):
                     st.session_state['datos_a_corregir'] = {
                         'monto': s['monto_solicitado'],
                         'plazo': s['plazo_dias'],
                         'modalidad': s.get('modalidad', 'Diario'),
                         'tasa': s.get('tasa_propuesta', 20),
                         'nombre': nombre,
                         'cedula': data_nuevo.get('cedula', ''),
                         'direccion': data_nuevo.get('direccion', ''),
                         'telefono': data_nuevo.get('telefono', ''),
                         'referencias': data_nuevo.get('referencias', ''),
                         'es_recurrente': False if s.get('tipo_solicitud') == 'nuevo' else True,
                         'cliente_id_recurrente': s.get('id_cliente_existente')
                     }
                     st.session_state['solicitudes_ocultas'].add(s['id'])
                     st.session_state['mensaje_correccion_activo'] = True
                     st.rerun()

                 if c_btn2.button("🗑️ Borrar", key=f"del_{s['id']}", use_container_width=True):
                     st.session_state['solicitudes_ocultas'].add(s['id'])
                     st.rerun()

            elif estado_v in ['aprobada', 'auto_aprobado']:
                 if st.button("📦 Archivar", key=f"arc_{s['id']}", use_container_width=True):
                     st.session_state['solicitudes_ocultas'].add(s['id'])
                     st.rerun()
            
            elif estado_v == 'pendiente':
                 st.info("ℹ️ Esperando respuesta de administración.")