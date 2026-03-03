import ssl
import streamlit as st
import os
from datetime import datetime
import pytz

# --- IMPORTACIONES NUEVAS PARA TELEGRAM Y DB ---
from utils.telegram_sender import enviar_alerta_telegram
from db_connection import get_db_client

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="CreceMás | Servicios Financieros",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PARCHE DE SEGURIDAD (SSL) ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- 3. IMPORTACIÓN DE MÓDULOS ---
from modules import login, admin, driver

# --- 4. GESTIÓN DE ESTADO (SESSION STATE) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'role' not in st.session_state:
    st.session_state['role'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None

# --- 5. ESTILOS CSS FINTECH ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    :root {
        --primary-color: #4CAF50;
        --text-color: #0F3D3E;
        --bg-color: #F7F3E9;
        --card-bg: #FFFFFF;
        --sidebar-bg: #E6F4EA;
    }
    .stApp {
        background-color: var(--bg-color);
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {
        color: var(--text-color) !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    div[data-testid="stBorderContainer"] {
        background-color: var(--card-bg);
        border: none !important;
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(15, 61, 62, 0.08);
        padding: 40px !important;
    }
    .stTextInput input {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        color: var(--text-color);
        padding: 12px;
    }
    div[data-testid="stButton"] > button {
        background-color: var(--primary-color) !important;
        color: white !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        width: 100%;
    }
    .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 15px 0px;
        margin-bottom: 25px;
        border-bottom: 2px solid #E6F4EA;
    }
    .user-info {
        font-size: 0.9rem;
        color: #555;
        background-color: #E6F4EA;
        padding: 5px 15px;
        border-radius: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 6. CEREBRO DE NAVEGACIÓN (ROUTER) ---

if not st.session_state['logged_in']:
    st.write("")
    st.write("")
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            c_logo_1, c_logo_2, c_logo_3 = st.columns([1, 2, 1])
            with c_logo_2:
                if os.path.exists("logo.png"):
                    st.image("logo.png", use_container_width=True)
                else:
                    st.markdown("<h1 style='text-align: center;'>🌱</h1>", unsafe_allow_html=True)
            st.write("") 
            login.mostrar_login()
else:
    # PANTALLA PRINCIPAL
    rol_actual = st.session_state.get('role')
    usuario_actual = st.session_state.get('username', 'Usuario')
    
    st.markdown(f"""
        <div class="dashboard-header">
            <div class="company-name">CreceMás <span style="font-size: 1rem; color: #4CAF50;">Financiera</span></div>
            <div class="user-info">👤 {usuario_actual.upper()} | {rol_actual.capitalize()}</div>
        </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.write("")
        st.write("")
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

    # --- CARGA DE MÓDULOS CON LÓGICA DE HORARIO ---
    if rol_actual == 'admin':
        admin.main()
        
    elif rol_actual == 'driver': 
        tz = pytz.timezone('America/Guatemala')
        hora_actual = datetime.now(tz).hour
        
        # 1. VERIFICAR PERMISO ESPECIAL EN BASE DE DATOS
        supabase = get_db_client()
        user_id = st.session_state.get('user_id')
        tiene_permiso = False
        
        try:
            res = supabase.table("usuarios").select("permiso_fuera_horario").eq("id", user_id).execute()
            if res.data:
                tiene_permiso = res.data[0].get("permiso_fuera_horario", False)
        except Exception as e:
            pass # Si falla la consulta, asumimos que no tiene permiso
            
        # 2. VALIDAR SI ENTRA POR HORA NORMAL O POR PERMISO
        if (8 <= hora_actual < 16) or tiene_permiso:
            driver.mostrar_ruta()
        else:
            # 3. PANTALLA DE BLOQUEO Y SOLICITUD DE ACCESO
            st.warning("⚠️ ACCESO RESTRINGIDO")
            st.info(f"El sistema para cobradores solo está disponible de **8:00 AM a 4:00 PM**.\nHora actual: {datetime.now(tz).strftime('%I:%M %p')}")
            
            st.write("---")
            st.markdown("#### ¿Necesitas trabajar fuera de horario?")
            
            if st.button("Solicitar acceso especial al Administrador"):
                nombre_chofer = st.session_state.get('username', 'Un Chofer')
                user_id = st.session_state.get('user_id') # Aseguramos tener el ID
                ahora_str = datetime.now(tz).isoformat()
                
                # 1. Crear el mensaje para Telegram
                mensaje = (
                    f"🚨 *SOLICITUD DE ACCESO FUERA DE HORARIO*\n\n"
                    f"🚛 *Chofer:* {nombre_chofer}\n"
                    f"⏰ *Hora de intento:* {datetime.now(tz).strftime('%I:%M %p')}\n\n"
                    f"👇 _Ingresa a la App web, ve a la sección de Solicitudes y aprueba el permiso._"
                )
                
                link_app = "https://crecemas.streamlit.app/" 
                
                try:
                    # 2. Insertar en la tabla solicitudes de Supabase
                    datos_solicitud = {
                        "cobrador_id": user_id,
                        "tipo_solicitud": "permiso_horario",  # Esto es lo que busca el admin
                        "estado": "pendiente",
                        "fecha_solicitud": ahora_str,
                        "motivo_rechazo": "Solicitud de acceso fuera de horario",
                        # Campos obligatorios en tu tabla que podemos mandar en 0 o vacíos
                        "monto_solicitado": 0,
                        "tasa_propuesta": 0,
                        "plazo_dias": 0
                    }
                    supabase.table("solicitudes").insert(datos_solicitud).execute()

                    # 3. Enviar el Telegram
                    enviar_alerta_telegram(mensaje, link_app)
                    
                    st.success("✅ **Solicitud enviada.** \n\nEscríbele a tu administrador. Una vez que apruebe el acceso en el panel, **recarga esta página**.")
                except Exception as e:
                    st.error(f"❌ Hubo un error al procesar la solicitud: {e}")