import streamlit as st
import pandas as pd
from db_connection import get_db_client
import numpy as np

def mostrar_pagos_diarios():
    st.header("📅 Registro de Pagos Diarios")
    
    # --- BLOQUE 1: NOTAS DE FÓRMULAS ---
    with st.expander("📝 Notas de Fórmulas (Distribución de Capital e Interés)"):
        st.markdown("""
        | Columna | Lógica / Fórmula |
        | :--- | :--- |
        | **Monto pagado** | El abono total registrado en el sistema. |
        | **Interes del pago** | Proporcional al préstamo. `Monto pagado * (Interés generado / Deuda Total)` |
        | **Capital del pago** | `Monto pagado - Interes del pago` |
        """)

    supabase = get_db_client()

    try:
        # 1. Consultas a Supabase
        # Traemos los pagos
        query_pagos = supabase.table("pagos").select(
            "id, prestamo_id, monto, fecha_pago, fecha_hora"
        ).execute()
        
        # Traemos los préstamos (para saber la tasa y sacar la proporción)
        query_prestamos = supabase.table("prestamos").select(
            "id, codigo_prestamo, monto_prestado, tasa_interes, "
            "clientes(codigo_cliente, nombre)"
        ).execute()

        if query_pagos.data and query_prestamos.data:
            df_pagos = pd.DataFrame(query_pagos.data)
            df_prestamos = pd.DataFrame(query_prestamos.data)

            # --- PROCESAMIENTO DE PRÉSTAMOS ---
            df_prestamos['Código Cliente'] = df_prestamos['clientes'].apply(lambda x: x['codigo_cliente'] if isinstance(x, dict) else '')
            df_prestamos['Nombre'] = df_prestamos['clientes'].apply(lambda x: x['nombre'] if isinstance(x, dict) else '')
            
            # Convertir a números
            df_prestamos['monto_prestado'] = pd.to_numeric(df_prestamos['monto_prestado'], errors='coerce').fillna(0)
            df_prestamos['tasa_interes'] = pd.to_numeric(df_prestamos['tasa_interes'], errors='coerce').fillna(0)
            
            # Renombramos 'id' a 'prestamo_id' para poder cruzar las tablas
            df_prestamos = df_prestamos.rename(columns={'id': 'prestamo_id'})

            # --- CRUCE DE TABLAS (JOIN) ---
            # Unimos cada pago con la información de su respectivo préstamo
            df = pd.merge(df_pagos, df_prestamos, on='prestamo_id', how='inner')

            # --- CÁLCULOS MATEMÁTICOS DE PROPORCIÓN ---
            df['monto'] = pd.to_numeric(df['monto'], errors='coerce').fillna(0)
            
            # 1. Calculamos el Interés Generado Total del Préstamo
            df['Interes Generado Total'] = df['monto_prestado'] * (df['tasa_interes'] / 100)
            
            # 2. Calculamos la Deuda Total
            df['Deuda Total'] = df['monto_prestado'] + df['Interes Generado Total']
            
            # 3. Calculamos la proporción (Ratio) que le toca al interés
            df['Ratio Interes'] = np.where(df['Deuda Total'] > 0, df['Interes Generado Total'] / df['Deuda Total'], 0)
            
            # 4. Aplicamos el Ratio al pago del día
            df['Interes del pago'] = df['monto'] * df['Ratio Interes']
            df['Capital del pago'] = df['monto'] - df['Interes del pago']

            # --- FECHAS Y ORDENAMIENTO ---
            # Usamos fecha_pago si existe, si no, sacamos la fecha de fecha_hora
            df['fecha_uso'] = pd.to_datetime(df['fecha_pago'].fillna(pd.to_datetime(df['fecha_hora']).dt.date), errors='coerce')
            
            # Ordenamos del pago más reciente al más antiguo
            df = df.sort_values('fecha_uso', ascending=False).reset_index(drop=True)
            df['Fecha'] = df['fecha_uso'].dt.strftime('%d/%m/%Y')

            # Selección de columnas finales
            columnas = [
                'Fecha', 'codigo_prestamo', 'Código Cliente', 'Nombre', 
                'monto', 'Interes del pago', 'Capital del pago'
            ]
            
            df_mostrar = df[columnas].copy()
            df_mostrar.rename(columns={
                'codigo_prestamo': 'Código Préstamo',
                'monto': 'Monto pagado'
            }, inplace=True)

            # --- PANEL DE FILTROS ---
            st.write("---")
            c1, c2 = st.columns(2)
            with c1:
                busqueda = st.text_input("🔍 Buscar por Nombre, CM de Cliente o CM de Préstamo", "")
            with c2:
                # Filtro rápido por fechas
                fechas_unicas = df_mostrar["Fecha"].unique().tolist()
                filtro_fecha = st.multiselect("📅 Filtrar por Fecha específica", fechas_unicas)

            if busqueda:
                df_mostrar = df_mostrar[df_mostrar.apply(lambda r: busqueda.lower() in r.astype(str).str.lower().values, axis=1)]
            if filtro_fecha:
                df_mostrar = df_mostrar[df_mostrar["Fecha"].isin(filtro_fecha)]

            # --- TOTALES EN PANTALLA ---
            # Sumamos lo que quedó filtrado para darle un resumen al cliente
            total_recaudado = df_mostrar['Monto pagado'].sum()
            total_interes = df_mostrar['Interes del pago'].sum()
            total_capital = df_mostrar['Capital del pago'].sum()
            
            col_tot1, col_tot2, col_tot3 = st.columns(3)
            col_tot1.metric("💰 Total Recaudado (Vista)", f"C$ {total_recaudado:,.2f}")
            col_tot2.metric("📈 Interés Recuperado", f"C$ {total_interes:,.2f}")
            col_tot3.metric("🏦 Capital Recuperado", f"C$ {total_capital:,.2f}")
            st.write("---")

            # --- ESTILOS ---
            # Aplicamos colores ligeros para diferenciar el capital del interés visualmente
            df_final = df_mostrar.style.format({
                'Monto pagado': 'C$ {:,.2f}',
                'Interes del pago': 'C$ {:,.2f}',
                'Capital del pago': 'C$ {:,.2f}'
            }).set_properties(subset=['Interes del pago'], **{'color': '#856404'}) \
              .set_properties(subset=['Capital del pago'], **{'color': '#155724'})

            # Mostrar tabla
            st.dataframe(df_final, use_container_width=True, hide_index=True, height=550)

            # --- BOTÓN DESCARGA ---
            st.divider()
            csv = df_mostrar.to_csv(index=False).encode('utf-8-sig') 
            st.download_button("📥 Descargar Pagos Diarios (.csv)", csv, "Pagos_Diarios.csv", "text/csv")

        else:
            st.warning("No hay pagos registrados aún en la base de datos.")

    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")