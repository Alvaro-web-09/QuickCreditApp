import streamlit as st

# 1. IMPORTAMOS LOS MÓDULOS
from modules.admin_views import (
    dashboard, 
    solicitudes, 
    auditoria, 
    crm_clientes, 
    crm_vendedores, 
    estado_cuenta,
    balance_financiero,
    admin_caja,
    detalle_prestamos,
    cobros_extraordinarios,
    excel_master  # <--- NUEVA IMPORTACIÓN AQUÍ
)

def main():
    # ==========================================
    # 0. INYECCIÓN DE ESTILO GLOBAL (Mismo diseño que Driver)
    # ==========================================
    st.markdown("""
        <style>
        /* 1. Botón PRIMARIO (type="primary") -> VERDE */
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

        /* 2. Botón SECUNDARIO (type="secondary") -> ROJO */
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

    # --- MENÚ LATERAL DEL ADMIN ---
    with st.sidebar:
        st.title("🏢 Panel Admin")
        
        usuario = st.session_state.get('username', 'Admin Principal')
        st.write(f"Hola, **{usuario}**")
        st.markdown("---")
        
        # 2. AGREGAMOS LA OPCIÓN AL MENÚ
        menu = st.radio(
            "Navegación",
            [
                "📊 Dashboard Global", 
                "🖥️ Control Excel",      # <--- NUEVO BOTÓN AGREGADO AQUÍ
                "🏦 Fondos",                  
                "💸 Pagos Extraordinarios",   
                "📩 Solicitudes Nuevas", 
                "📂 Explorador de Préstamos", 
                "📈 Balance Financiero", 
                "📜 Estado de Cuenta",   
                "👥 Clientes",                
                "💼 Vendedores",              
                "💰 Pago Planilla"            
            ],
        )
        
        st.markdown("---")

    # --- ENRUTAMIENTO (ACTUALIZADO PARA COINCIDIR CON LOS NOMBRES) ---
    
    if menu == "📊 Dashboard Global":
        dashboard.mostrar_dashboard()

    elif menu == "🖥️ Control Excel":       # <--- NUEVA RUTA AGREGADA
        excel_master.mostrar_modulo_excel_completo()

    elif menu == "🏦 Fondos":              
        admin_caja.mostrar_gestion_caja()
        
    elif menu == "💸 Pagos Extraordinarios": 
        cobros_extraordinarios.mostrar_modulo_cobros_admin()
        
    elif menu == "📩 Solicitudes Nuevas":
        solicitudes.mostrar_solicitudes()

    elif menu == "📂 Explorador de Préstamos":
        detalle_prestamos.mostrar_detalle_prestamos()

    elif menu == "📈 Balance Financiero":
        balance_financiero.mostrar_balance_financiero()

    elif menu == "📜 Estado de Cuenta":
        estado_cuenta.mostrar_estado_cuenta()

    elif menu == "👥 Clientes":            
        crm_clientes.mostrar_crm_clientes()

    elif menu == "💼 Vendedores":          
        crm_vendedores.mostrar_crm_vendedores()
        
    elif menu == "💰 Pago Planilla":       
        auditoria.mostrar_auditoria()

if __name__ == "__main__":
    main()