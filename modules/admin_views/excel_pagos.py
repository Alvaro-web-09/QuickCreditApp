import streamlit as st
import pandas as pd
from db_connection import get_db_client
import numpy as np

def mostrar_control_pagos():
    st.header("📊 Control de Pagos por Préstamos")
    
    # --- BLOQUE 1: NOTAS DE FÓRMULAS ---
    with st.expander("📝 Notas de Fórmulas"):
        st.markdown("""
        | Columna | Lógica / Fórmula |
        | :--- | :--- |
        | **No. de Cuota** | El plazo en días definido al crear el préstamo. |
        | **Cuotas pagadas** | `Total Pagado / Monto de Cuota Diaria` (Redondeado hacia abajo). |
        | **Prestamo + Interes** | Monto total de la deuda original. |
        | **Total pagado** | Suma de todos los pagos registrados para este préstamo. |
        | **Saldo restante** | `(Prestamo + Interes) - Total pagado` |
        """)

    supabase = get_db_client()

    try:
        # 1. Consultas a Supabase
        query_prestamos = supabase.table("prestamos").select(
            "id, codigo_prestamo, plazo_dias, monto_total_deuda, monto_cuota, estado, "
            "clientes(codigo_cliente, nombre)"
        ).execute()
        
        query_pagos = supabase.table("pagos").select("prestamo_id, monto").execute()

        if query_prestamos.data:
            df = pd.DataFrame(query_prestamos.data)
            
            # --- PROCESAMIENTO BÁSICO ---
            df['Código Cliente'] = df['clientes'].apply(lambda x: x['codigo_cliente'] if isinstance(x, dict) else '')
            df['Nombre del Cliente'] = df['clientes'].apply(lambda x: x['nombre'] if isinstance(x, dict) else '')
            
            # Convertir a números
            cols_num = ['plazo_dias', 'monto_total_deuda', 'monto_cuota']
            for col in cols_num:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # --- CÁLCULO DE PAGOS ---
            if query_pagos.data:
                df_pagos = pd.DataFrame(query_pagos.data)
                df_pagos['monto'] = pd.to_numeric(df_pagos['monto'], errors='coerce').fillna(0)
                # Agrupamos los pagos por préstamo
                pagos_sum = df_pagos.groupby('prestamo_id')['monto'].sum().reset_index()
                pagos_sum.rename(columns={'prestamo_id': 'id', 'monto': 'Total pagado'}, inplace=True)
                
                df = pd.merge(df, pagos_sum, on='id', how='left')
                df['Total pagado'] = df['Total pagado'].fillna(0)
            else:
                df['Total pagado'] = 0.0

            # --- CÁLCULOS FINALES PARA LA TABLA ---
            # Cuotas pagadas (Total Pagado / Cuota Diaria)
            df['Cuotas pagadas'] = np.floor(
                np.where(df['monto_cuota'] > 0, df['Total pagado'] / df['monto_cuota'], 0)
            ).astype(int)

            df['Saldo restante'] = df['monto_total_deuda'] - df['Total pagado']
            
            # Para evitar saldos negativos por errores de redondeo o sobrepagos pequeños
            df['Saldo restante'] = df['Saldo restante'].apply(lambda x: 0 if x < 0.01 else x)

            # ==========================================
            # 🚀 ORDENAMIENTO LÓGICO Y NATURAL
            # ==========================================
            # Extraemos el número del código de préstamo (ej. de "CM10-01" extrae "10")
            df['_orden_num'] = df['codigo_prestamo'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
            
            # Ordenamos: Primero los ACTIVOS arriba, y luego por orden numérico real
            df = df.sort_values(by=['estado', '_orden_num'], ascending=[True, True])
            
            # Eliminamos la columna temporal y reiniciamos el índice
            df = df.drop(columns=['_orden_num']).reset_index(drop=True)

            # Selección y renombramiento de columnas
            columnas = [
                'codigo_prestamo', 'Código Cliente', 'Nombre del Cliente', 'plazo_dias', 
                'Cuotas pagadas', 'monto_total_deuda', 'Total pagado', 'Saldo restante', 'estado'
            ]
            
            df_mostrar = df[columnas].copy()
            df_mostrar.rename(columns={
                'codigo_prestamo': 'Código Préstamo',
                'plazo_dias': 'No. de Cuota',
                'monto_total_deuda': 'Prestamo+interes',
                'estado': 'Estado'
            }, inplace=True)

            # --- PANEL DE FILTROS ---
            st.write("---")
            c1, c2 = st.columns(2)
            with c1:
                busqueda = st.text_input("🔍 Buscar por Código o Nombre de Cliente", "")
            with c2:
                estados = df_mostrar["Estado"].unique().tolist()
                filtro_est = st.multiselect("🏷️ Filtrar por Estado", estados, default=["activo"] if "activo" in estados else None)

            # Aplicar filtros
            if busqueda:
                df_mostrar = df_mostrar[df_mostrar.apply(lambda r: busqueda.lower() in r.astype(str).str.lower().values, axis=1)]
            if filtro_est:
                df_mostrar = df_mostrar[df_mostrar["Estado"].isin(filtro_est)]

            # --- ESTILOS Y COLORES ---
            def aplicar_colores(row):
                estilos = [''] * len(row)
                idx_estado = row.index.get_loc('Estado')
                val = str(row['Estado']).upper()
                
                # Pintar la columna estado
                if val == 'PAGADO':
                    estilos[idx_estado] = 'color: #155724; font-weight: bold;'
                else:
                    estilos[idx_estado] = 'color: #856404; font-weight: bold;' # Color ámbar/dorado para ACTIVO
                return estilos

            # Aplicar formato de moneda a las columnas financieras
            df_final = df_mostrar.style.apply(aplicar_colores, axis=1).format({
                'Prestamo+interes': 'C$ {:,.2f}',
                'Total pagado': 'C$ {:,.2f}',
                'Saldo restante': 'C$ {:,.2f}'
            })

            # Mostrar tabla interactiva
            st.dataframe(df_final, use_container_width=True, hide_index=True, height=600)

            # --- BOTÓN DESCARGA ---
            st.divider()
            csv = df_mostrar.to_csv(index=False).encode('utf-8-sig') 
            st.download_button("📥 Descargar Control de Pagos (.csv)", csv, "Control_de_Pagos.csv", "text/csv")

        else:
            st.warning("No hay datos de préstamos para mostrar.")

    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")