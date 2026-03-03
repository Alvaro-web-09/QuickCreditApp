import streamlit as st
import time
from db_connection import get_db_client

# IMPORTANTE: Asegúrate de que todos estos archivos existan en modules/driver_views
from modules.driver_views import mi_cartera, cobrar, prestamos, agenda_view, mis_solicitudes
from modules.driver_views.driver_caja import mostrar_caja_driver

def mostrar_ruta():
    # ==========================================
    # 0. INYECCIÓN DE ESTILO GLOBAL (Para que no cambie al navegar)
    # ==========================================
    st.markdown("""
        <style>
        /* 1. Botón COBRAR (type="primary") -> VERDE */
        div.stButton > button[kind="primary"] {
            background-color: #4CAF50 !important;
            border: none !important;
            color: white !important;
            font-weight: bold !important;
            box-shadow: 0px 2px 5px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #1B5E20 !important;
            transform: scale(1.02);
        }

        /* 2. Botón NO PAGO / CERRAR SESIÓN (type="secondary") -> ROJO */
        div.stButton > button[kind="secondary"] {
            color: #D32F2F !important;
            border: 2px solid #FFCDD2 !important;
            background-color: white !important;
            font-weight: 600 !important;
        }
        div.stButton > button[kind="secondary"]:hover {
            background-color: #FFEBEE !important;
            border-color: #D32F2F !important;
            color: #B71C1C !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Obtenemos el ID del usuario
    user_id = st.session_state.get('user_id')

    # ==========================================
    # 1. GESTIÓN DE ESTADO (MENÚ)
    # ==========================================
    opciones_menu = [
        "💼 Mi Ruta de hoy", 
        "🏦 Mi Bóveda (Caja)", 
        "📒 Agenda Clientes", 
        "💰 Cobrar", 
        "📝 Nueva Solicitud", 
        "📂 Mis Solicitudes"
    ]
    
    if 'menu_option' not in st.session_state or st.session_state['menu_option'] not in opciones_menu:
        st.session_state['menu_option'] = opciones_menu[0]

    try:
        index_actual = opciones_menu.index(st.session_state['menu_option'])
    except ValueError:
        index_actual = 0

    # ==========================================
    # 2. BARRA LATERAL (SIDEBAR)
    # ==========================================
    with st.sidebar:
        st.header("🚛 Panel Conductor")
        st.markdown(f"**Usuario:** {st.session_state.get('username', 'Driver')}")
        st.write("---")
        
        menu_seleccion = st.radio(
            "Navegación:",
            opciones_menu,
            index=index_actual,
             
        )
        
        if menu_seleccion != st.session_state.get('menu_option'):
            st.session_state['menu_option'] = menu_seleccion
            st.rerun()
        
        # El botón de cerrar sesión ya no es necesario aquí si lo tienes en app.py,
        # pero si lo dejas, ahora se verá rojo automáticamente por el CSS de arriba.

    # ==========================================
    # 3. CEREBRO: ¿QUÉ MUESTRO?
    # ==========================================
    opcion = st.session_state['menu_option']
    
    if opcion == "💼 Mi Ruta de hoy":
        mi_cartera.mostrar_dashboard()
    elif opcion == "🏦 Mi Bóveda (Caja)":
        mostrar_caja_driver(user_id)
    elif opcion == "📒 Agenda Clientes":
        agenda_view.mostrar_agenda()
    elif opcion == "💰 Cobrar":
        cobrar.mostrar_cobro()
    elif opcion == "📝 Nueva Solicitud":
        prestamos.mostrar_ventas()
    elif opcion == "📂 Mis Solicitudes":
        mis_solicitudes.mostrar_mis_solicitudes()

if __name__ == "__main__":
    if 'user_id' not in st.session_state:
        st.session_state['user_id'] = 'test-uuid'
        st.session_state['username'] = 'Test Driver'
    mostrar_ruta()