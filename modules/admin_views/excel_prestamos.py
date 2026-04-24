import streamlit as st
import pandas as pd
from db_connection import get_db_client

def mostrar_directorio_prestamos():
    st.header("📂 Registro de Préstamos")
    
    # --- BLOQUE 1: NOTAS DE FÓRMULAS ---
    with st.expander("📝 Notas de Fórmulas"):
        st.markdown("""
        | Columna | Lógica / Fórmula |
        | :--- | :--- |
        | **Código Préstamo** | Identificador único del sistema (CM). |
        | **Interes generado** | `Monto del Préstamo * (Tasa Interés / 100)` |
        | **Préstamo + Intereses** | `Monto del Préstamo + Interés Generado` |
        | **Interes cobrado** | Pagos registrados aplicados al interés. |
        | **Interes pendiente** | `Interés Generado - Interés Cobrado` |
        """)

    supabase = get_db_client()

    try:
        # 1. Consulta a Supabase
        query_prestamos = supabase.table("prestamos").select(
            "id, codigo_prestamo, monto_prestado, tasa_interes, plazo_dias, "
            "fecha_inicio, fecha_vencimiento, monto_cuota, estado, "
            "clientes(codigo_cliente, nombre)"
        ).execute()
        
        query_pagos = supabase.table("pagos").select("prestamo_id, monto").execute()

        if query_prestamos.data:
            df = pd.DataFrame(query_prestamos.data)
            
            # --- PROCESAMIENTO ---
            df['Código Cliente'] = df['clientes'].apply(lambda x: x['codigo_cliente'] if isinstance(x, dict) else '')
            df['Nombre del Cliente'] = df['clientes'].apply(lambda x: x['nombre'] if isinstance(x, dict) else '')
            
            # Convertir a números
            cols_num = ['monto_prestado', 'tasa_interes', 'monto_cuota']
            for col in cols_num:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # ==========================================
            # 🚀 ORDENAMIENTO LÓGICO Y NATURAL
            # ==========================================
            df['fecha_inicio'] = pd.to_datetime(df['fecha_inicio'])
            
            # Extraemos el número del código de préstamo (ej. de "CM10-01" saca "10")
            df['_orden_num'] = df['codigo_prestamo'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
            
            # Ordenamos: Primero numéricamente por código, luego por fecha (los más recientes arriba)
            df = df.sort_values(by=['_orden_num', 'fecha_inicio'], ascending=[True, False])
            
            # Limpiamos la columna temporal
            df = df.drop(columns=['_orden_num']).reset_index(drop=True)

            # --- CÁLCULOS ---
            df['% Interes'] = df['tasa_interes'].astype(str) + "%"
            df['Interes generado'] = df['monto_prestado'] * (df['tasa_interes'] / 100)
            df['Total a Pagar'] = df['monto_prestado'] + df['Interes generado']
            
            # Sumar pagos
            if query_pagos.data:
                df_pagos = pd.DataFrame(query_pagos.data)
                df_pagos['monto'] = pd.to_numeric(df_pagos['monto'], errors='coerce').fillna(0)
                pagos_sum = df_pagos.groupby('prestamo_id')['monto'].sum().reset_index()
                pagos_sum.rename(columns={'prestamo_id': 'id', 'monto': 'Total Pagado'}, inplace=True)
                df = pd.merge(df, pagos_sum, on='id', how='left')
                df['Total Pagado'] = df['Total Pagado'].fillna(0)
            else:
                df['Total Pagado'] = 0.0

            df['Interes cobrado'] = df[['Total Pagado', 'Interes generado']].min(axis=1)
            df['Interes pendiente'] = df['Interes generado'] - df['Interes cobrado']
            
            # Fechas formato legible
            df['Fecha Préstamo'] = df['fecha_inicio'].dt.strftime('%d-%m-%Y')
            df['Fecha Vencimiento'] = pd.to_datetime(df['fecha_vencimiento']).dt.strftime('%d-%m-%Y')

            # Selección de columnas finales
            columnas = [
                'codigo_prestamo', 'Código Cliente', 'Nombre del Cliente', 'Fecha Préstamo', 
                'monto_prestado', '% Interes', 'Interes generado',
                'Total a Pagar', 'plazo_dias', 'monto_cuota', 'Interes cobrado', 'Interes pendiente', 'estado'
            ]
            
            df_mostrar = df[columnas].copy()
            df_mostrar.rename(columns={
                'codigo_prestamo': 'Código Préstamo',
                'monto_prestado': 'Monto Préstamo',
                'plazo_dias': 'Cuotas',
                'monto_cuota': 'Cuota Diaria',
                'estado': 'Estado'
            }, inplace=True)

            # --- PANEL DE FILTROS ---
            st.write("---")
            c1, c2 = st.columns(2)
            with c1:
                busqueda = st.text_input("🔍 Buscar por Código o Nombre", "")
            with c2:
                estados = df_mostrar["Estado"].unique().tolist()
                filtro_est = st.multiselect("🏷️ Filtrar por Estado", estados)

            if busqueda:
                df_mostrar = df_mostrar[df_mostrar.apply(lambda r: busqueda.lower() in r.astype(str).str.lower().values, axis=1)]
            if filtro_est:
                df_mostrar = df_mostrar[df_mostrar["Estado"].isin(filtro_est)]

            # --- ESTILOS ---
            def aplicar_colores(row):
                estilos = [''] * len(row)
                idx_estado = row.index.get_loc('Estado')
                val = str(row['Estado']).upper()
                if val == 'PAGADO':
                    estilos[idx_estado] = 'background-color: #d4edda; color: #155724; font-weight: bold; text-align: center;'
                else:
                    estilos[idx_estado] = 'background-color: #f8d7da; color: #721c24; font-weight: bold; text-align: center;'
                return estilos

            df_final = df_mostrar.style.apply(aplicar_colores, axis=1).format({
                'Monto Préstamo': 'C$ {:,.2f}',
                'Interes generado': 'C$ {:,.2f}',
                'Total a Pagar': 'C$ {:,.2f}',
                'Cuota Diaria': 'C$ {:,.2f}',
                'Interes cobrado': 'C$ {:,.2f}',
                'Interes pendiente': 'C$ {:,.2f}'
            })

            # Mostrar tabla
            st.dataframe(df_final, use_container_width=True, hide_index=True, height=550)

            # --- BOTÓN DESCARGA ---
            st.divider()
            csv = df_mostrar.to_csv(index=False).encode('utf-8-sig') 
            st.download_button("📥 Descargar Reporte (.csv)", csv, "Directorio_Prestamos.csv", "text/csv")

        else:
            st.warning("No hay datos disponibles.")

    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")