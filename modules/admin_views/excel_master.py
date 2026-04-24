import streamlit as st

# Importamos todas nuestras pestañas
from modules.admin_views import directorio_excel
from modules.admin_views import excel_prestamos
from modules.admin_views import excel_pagos
from modules.admin_views import excel_pagos_diarios
from modules.admin_views import excel_diario 
from modules.admin_views import excel_analisis_financiero # <--- Importación de la pestaña 6

def mostrar_modulo_excel_completo():
    st.title("🖥️ Sistema de Control (Vista Excel)")
    
    # Agregamos tab6 y su nombre a la lista
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "👥 Directorio Clientes", 
        "💰 Registro Préstamos", 
        "📊 Control Pagos", 
        "📅 Pagos Diarios",
        "🗓️ Diario de Caja",
        "📈 Análisis Financiero"  # <--- Nombre de la pestaña 6
    ])
    
    with tab1:
        directorio_excel.mostrar_directorio_excel()
    with tab2:
        excel_prestamos.mostrar_directorio_prestamos()
    with tab3:
        excel_pagos.mostrar_control_pagos()
    with tab4:
        excel_pagos_diarios.mostrar_pagos_diarios()
    with tab5:
        excel_diario.mostrar_diario_caja() 
    with tab6:
        excel_analisis_financiero.mostrar_analisis_financiero() # <--- Llamada a la función