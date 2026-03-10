import streamlit as st
import pandas as pd
from datetime import datetime
from db_connection import get_db_client
import time

def mostrar_gestion_caja():
    # Encabezado Corporativo
    st.markdown("## Gestión de Tesorería y Bóveda")
    st.markdown("Control de flujo de efectivo y asignación de saldos a responsables.")
    
    supabase = get_db_client()

    # 1. Obtener lista de choferes (Lógica original intacta)
    try:
        q_users = supabase.table("usuarios").select("id, username, nombre_completo, saldo_actual").execute()
        drivers = q_users.data
    except Exception as e:
        st.error(f"Error de conexión al cargar usuarios: {e}")
        return

    if not drivers:
        st.warning("No se encontraron usuarios registrados en el sistema.")
        return

    mapa_drivers = {f"{d.get('nombre_completo', d['username'])}": d for d in drivers}
    
    # --- BLOQUE 1: SELECCIÓN Y ESTADO ACTUAL ---
    with st.container(border=True):
        col_sel, col_info = st.columns([2, 1])
        
        with col_sel:
            seleccion = st.selectbox("Seleccionar Responsable", options=list(mapa_drivers.keys()))
            driver_actual = mapa_drivers[seleccion]
            driver_id = driver_actual['id']
            
            # --- SOLUCIÓN AQUÍ ---
            # Extraemos el valor crudo primero. Si es None, usamos 0.0 por defecto.
            saldo_crudo = driver_actual.get('saldo_actual')
            saldo_actual = float(saldo_crudo if saldo_crudo is not None else 0.0)

        with col_info:
            st.metric(
                "Saldo en Custodia", 
                f"C$ {saldo_actual:,.2f}",
                help="Dinero efectivo que el conductor tiene actualmente disponible según sistema."
            )

    # --- BLOQUE 2: OPERACIONES DE CAJA ---
    st.write("")
    with st.container(border=True):
        st.subheader("Registro de Movimientos")
        
        # Radio button con textos formales. La lógica busca la palabra "Entregar", así que la mantenemos en el texto.
        tipo_operacion = st.radio(
            "Tipo de Operación:", 
            ["Asignación de Capital (Entregar)", "Recepción de Efectivo (Recibir/Cierre)"], 
            horizontal=True
        )
        
        col1, col2 = st.columns(2)
        with col1:
            monto = st.number_input("Monto de la Transacción (C$)", min_value=0.0, step=100.0, format="%.2f")
        with col2:
            nota = st.text_input("Concepto / Referencia", placeholder="Ej: Fondo inicial operativo")

        st.caption("Nota: Las entregas suman al saldo del conductor; las recepciones lo restan.")

        if st.button("Procesar Transacción", type="primary", use_container_width=True):
            if monto <= 0:
                st.error("Error de validación: El monto debe ser mayor a 0.")
                return
                
            try:
                # LÓGICA ORIGINAL PRESERVADA
                # Usamos 'Entregar' como palabra clave para mantener la lógica original del if
                if "Entregar" in tipo_operacion:
                    tipo_bd = "entrega_capital"
                    monto_registro = monto
                else:
                    tipo_bd = "cierre_caja"
                    monto_registro = -monto
                    if (saldo_actual - monto) < 0:
                        st.error("Operación rechazada: No es posible retirar más fondos de los disponibles en custodia.")
                        return
                
                # Inserción en BD
                supabase.table("movimientos_caja").insert({
                    "usuario_id": driver_id,
                    "tipo": tipo_bd,
                    "monto": monto_registro,
                    "descripcion": f"{nota} (Procesado por Admin)",
                    "fecha": datetime.now().isoformat()
                }).execute()
                
                st.success("Transacción registrada correctamente en el sistema.")
                
                # --- CRÍTICO PARA ACTUALIZACIÓN VISUAL ---
                time.sleep(1.2) 
                st.cache_data.clear() 
                st.rerun() 
                
            except Exception as e:
                st.error(f"Error técnico al procesar: {e}")

    # --- BLOQUE 3: AJUSTES ADMINISTRATIVOS (ZONA DE RIESGO) ---
    st.write("")
    with st.expander("Panel de Ajustes Administrativos (Uso Restringido)"):
        st.warning("Atención: Esta herramienta sobrescribe el saldo manualmente. Úsela solo para correcciones de auditoría.")
        
        col_adj_1, col_adj_2 = st.columns([2,1])
        with col_adj_1:
            ajuste_tipo = st.selectbox("Acción Correctiva", ["Restablecer a CERO (Reset)", "Definir Saldo Manualmente"])
        
        monto_ajuste = 0.0
        with col_adj_2:
            if "Manual" in ajuste_tipo: # Ajustado para coincidir con el texto del selectbox nuevo
                monto_ajuste = st.number_input("Nuevo Saldo Exacto", min_value=0.0, key="manual_val")

        if st.button("Aplicar Ajuste Forzado", use_container_width=True):
            try:
                # LÓGICA ORIGINAL
                supabase.table("usuarios").update({"saldo_actual": monto_ajuste}).eq("id", driver_id).execute()
                
                # Registro de auditoría
                supabase.table("movimientos_caja").insert({
                    "usuario_id": driver_id,
                    "tipo": "otros",
                    "monto": 0, 
                    "descripcion": f"AJUSTE MANUAL ADMIN: {saldo_actual} -> {monto_ajuste}",
                    "fecha": datetime.now().isoformat()
                }).execute()
                
                st.success("Ajuste de saldo aplicado correctamente.")
                time.sleep(1)
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error técnico: {e}")

    # --- BLOQUE 4: HISTORIAL DE MOVIMIENTOS ---
    st.markdown("---")
    st.subheader("Auditoría de Movimientos Recientes")
    
    try:
        # Consulta original
        q_hist = supabase.table("movimientos_caja").select("*").eq("usuario_id", driver_id).order("fecha", desc=True).limit(10).execute()
        
        if q_hist.data:
            # Transformación visual: De texto simple a DataFrame estructurado
            df_hist = pd.DataFrame(q_hist.data)
            
            # Limpieza y formateo para visualización
            df_display = df_hist[['fecha', 'tipo', 'monto', 'descripcion']].copy()
            
            # Formateo de nombres de columnas
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "fecha": st.column_config.DatetimeColumn("Fecha / Hora", format="DD/MM/YYYY HH:mm"),
                    "tipo": "Tipo Operación",
                    "monto": st.column_config.NumberColumn("Monto (C$)", format="C$ %.2f"),
                    "descripcion": "Detalle / Referencia"
                }
            )
        else:
            st.info("No hay movimientos registrados para este usuario.")
            
    except Exception as e:
        st.error(f"No se pudo cargar el historial: {e}")