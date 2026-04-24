import streamlit as st
import pandas as pd
from db_connection import get_db_client

def mostrar_diario_caja():
    st.header("🗓️ Control de Dinero por Driver")
    
    # --- BLOQUE DE NOTAS Y FÓRMULAS ---
    with st.expander("📝 Notas de Fórmulas y Referencias (Control de Dinero)"):
        st.markdown("""
        | Columna | Lógica / Fórmula | Referencia en BD |
        | :--- | :--- | :--- |
        | **Driver** | Nombre del Cobrador asignado. | `usuarios(nombre_completo)` |
        | **Valor Entregado** | Saldo inicial del día (Arrastra el *Valor en bolsa* del día anterior). | Calculado |
        | **Valor Colocado** | Suma de préstamos entregados en la fecha. | `prestamos(monto_prestado)` |
        | **Valor Recuperado** | Suma de abonos recibidos en la fecha. | `pagos(monto)` |
        | **Valor esperado** | Ingreso manual de meta o proyección. | Editable en pantalla |
        | **Gastos operativos** | Egresos del día registrados manualmente. | Editable en pantalla |
        | **Valor en bolsa** | `= Valor Entregado - Valor Colocado + Valor Recuperado - Gastos` | Calculado |
        """)

    supabase = get_db_client()

    try:
        # 1. Obtener lista de cobradores (usuarios) para el filtro
        res_usuarios = supabase.table("usuarios").select("id, nombre_completo").execute()
        df_usuarios = pd.DataFrame(res_usuarios.data) if res_usuarios.data else pd.DataFrame()

        if df_usuarios.empty:
            st.warning("No hay usuarios registrados en el sistema para asignar como Driver.")
            return

        # --- FILTRO POR DRIVER ---
        st.write("---")
        driver_dict = dict(zip(df_usuarios['id'], df_usuarios['nombre_completo']))
        driver_seleccionado_id = st.selectbox(
            "👤 Selecciona el Driver (Cobrador):", 
            options=list(driver_dict.keys()), 
            format_func=lambda x: driver_dict[x]
        )
        driver_nombre = driver_dict[driver_seleccionado_id]
        st.write("---")

        # 2. Traer datos de Préstamos filtrados por el cobrador
        res_prestamos = supabase.table("prestamos").select("fecha_inicio, monto_prestado").eq("cobrador_id", driver_seleccionado_id).execute()
        df_prestamos = pd.DataFrame(res_prestamos.data) if res_prestamos.data else pd.DataFrame()
        
        # 3. Traer datos de Pagos filtrados por el cobrador
        res_pagos = supabase.table("pagos").select("fecha_pago, monto").eq("cobrador_id", driver_seleccionado_id).execute()
        df_pagos = pd.DataFrame(res_pagos.data) if res_pagos.data else pd.DataFrame()

        if not df_prestamos.empty or not df_pagos.empty:
            
            # --- Agrupar Préstamos por Fecha ---
            if not df_prestamos.empty:
                df_prestamos['fecha'] = pd.to_datetime(df_prestamos['fecha_inicio'])
                df_prestamos['monto_prestado'] = pd.to_numeric(df_prestamos['monto_prestado'], errors='coerce').fillna(0)
                colocado = df_prestamos.groupby('fecha')['monto_prestado'].sum().reset_index()
                colocado.rename(columns={'monto_prestado': 'Valor Colocado'}, inplace=True)
            else:
                colocado = pd.DataFrame(columns=['fecha', 'Valor Colocado'])

            # --- Agrupar Pagos por Fecha ---
            if not df_pagos.empty:
                df_pagos['fecha'] = pd.to_datetime(df_pagos['fecha_pago'])
                df_pagos['monto'] = pd.to_numeric(df_pagos['monto'], errors='coerce').fillna(0)
                recuperado = df_pagos.groupby('fecha')['monto'].sum().reset_index()
                recuperado.rename(columns={'monto': 'Valor Recuperado'}, inplace=True)
            else:
                recuperado = pd.DataFrame(columns=['fecha', 'Valor Recuperado'])

            # --- Unir ambas tablas por fecha ---
            df_diario = pd.merge(colocado, recuperado, on='fecha', how='outer').fillna(0)
            df_diario = df_diario.sort_values('fecha').reset_index(drop=True)

            # --- Añadir las columnas faltantes ---
            df_diario['Driver'] = driver_nombre
            df_diario['Valor esperado'] = 0.0    
            
            # Inicializamos Gastos Operativos guardando el estado específico por Driver
            state_key = f"gastos_op_{driver_seleccionado_id}"
            if state_key not in st.session_state:
                st.session_state[state_key] = [0.0] * len(df_diario)
            elif len(st.session_state[state_key]) < len(df_diario):
                faltantes = len(df_diario) - len(st.session_state[state_key])
                st.session_state[state_key].extend([0.0] * faltantes)
                
            df_diario['Gastos operativos'] = st.session_state[state_key][:len(df_diario)]
            df_diario['Fecha'] = df_diario['fecha'].dt.strftime('%d-%m-%Y')

            # --- CÁLCULO SECUENCIAL (Amortización) ---
            col1, col2 = st.columns([1, 3])
            capital_inicial = col1.number_input(f"💰 Capital Inicial de {driver_nombre} (Día 1)", value=480000.0, step=1000.0)

            valor_entregado_list = []
            valor_en_bolsa_list = []
            saldo_actual = capital_inicial
            
            for index, row in df_diario.iterrows():
                v_entregado = saldo_actual 
                v_bolsa = v_entregado - row['Valor Colocado'] + row['Valor Recuperado'] - row['Gastos operativos']
                
                valor_entregado_list.append(v_entregado)
                valor_en_bolsa_list.append(v_bolsa)
                saldo_actual = v_bolsa

            df_diario['Valor Entregado'] = valor_entregado_list
            df_diario['Valor en bolsa'] = valor_en_bolsa_list

            # --- ORDENAR COLUMNAS EXACTAMENTE COMO EN EXCEL ---
            columnas_finales = [
                'Driver', 'Valor Entregado', 'Valor Colocado', 'Valor esperado', 
                'Valor Recuperado', 'Valor en bolsa', 'Gastos operativos', 'Fecha'
            ]
            df_mostrar = df_diario[columnas_finales].copy()

            # --- MOSTRAR TABLA EDITABLE ---
            st.write(f"### 📊 Movimientos de {driver_nombre}")
            
            df_editado = st.data_editor(
                df_mostrar,
                column_config={
                    "Valor Entregado": st.column_config.NumberColumn(format="C$ %.2f", disabled=True),
                    "Valor Colocado": st.column_config.NumberColumn(format="C$ %.2f", disabled=True),
                    "Valor esperado": st.column_config.NumberColumn(format="C$ %.2f"),
                    "Valor Recuperado": st.column_config.NumberColumn(format="C$ %.2f", disabled=True),
                    "Valor en bolsa": st.column_config.NumberColumn(format="C$ %.2f", disabled=True),
                    "Gastos operativos": st.column_config.NumberColumn(format="C$ %.2f"), # ¡Editable!
                    "Fecha": st.column_config.TextColumn(disabled=True),
                    "Driver": st.column_config.TextColumn(disabled=True)
                },
                hide_index=True,
                use_container_width=True,
                height=500
            )

            # Detectar cambios en los gastos operativos y recalcular en vivo
            if not df_editado['Gastos operativos'].equals(df_mostrar['Gastos operativos']):
                st.session_state[state_key] = df_editado['Gastos operativos'].tolist()
                st.rerun()

            # Botón de descarga
            st.divider()
            csv = df_editado.to_csv(index=False).encode('utf-8-sig') 
            st.download_button(f"📥 Descargar Control de {driver_nombre} (.csv)", csv, f"Control_Diario_{driver_nombre.replace(' ', '_')}.csv", "text/csv")

        else:
            st.info(f"No hay movimientos registrados (ni préstamos ni pagos) para el driver: {driver_nombre}.")

    except Exception as e:
        st.error(f"Error al generar el control de dinero: {str(e)}")