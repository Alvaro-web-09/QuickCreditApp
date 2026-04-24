import streamlit as st
import pandas as pd
from db_connection import get_db_client

def mostrar_directorio_excel():
    st.header("👥 Directorio de Clientes")
    st.info("Esta información se sincroniza en tiempo real con Supabase.")
    
    supabase = get_db_client()

    try:
        # Consulta a Supabase (Quitamos el .order() de aquí porque lo haremos de forma más inteligente en Pandas)
        query = supabase.table("clientes").select(
            "codigo_cliente, nombre, cedula, telefono, direccion, estado_cartera"
        ).execute()
        
        datos = query.data

        if datos:
            df = pd.DataFrame(datos)
            
            # Renombrar columnas para la vista
            columnas_bonitas = {
                "codigo_cliente": "Código Cliente",
                "nombre": "Nombre del Cliente",
                "cedula": "Cédula / ID",
                "telefono": "Teléfono",
                "direccion": "Dirección Completa",
                "estado_cartera": "Estado"
            }
            df = df.rename(columns=columnas_bonitas)

            # ==========================================
            # 🚀 MEJORA 1: ORDENAMIENTO LÓGICO (CM1, CM2... CM10)
            # ==========================================
            # Extraemos los números del texto (ej: de "CM10" sacamos "10") y ordenamos matemáticamente
            df['_orden_num'] = df['Código Cliente'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
            df = df.sort_values('_orden_num').drop(columns=['_orden_num']).reset_index(drop=True)

            # ==========================================
            # 🧠 MEJORA 2: FILTROS HIPER INTELIGENTES
            # ==========================================
            st.markdown("### 🔎 Panel de Filtros Avanzados")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                busqueda = st.text_input("🔍 Búsqueda global (Nombre, Cédula...)", "")
            
            with col2:
                # Filtro dinámico basado en los estados que realmente existan en la base de datos
                estados_unicos = df["Estado"].dropna().unique().tolist()
                filtro_estado = st.multiselect("🏷️ Filtrar por Estado", options=estados_unicos, default=[])
                
            with col3:
                busqueda_direccion = st.text_input("📍 Buscar por Barrio o Dirección...", "")

            # --- APLICAMOS LOS FILTROS AL DATAFRAME ---
            if busqueda:
                df = df[df.apply(lambda row: busqueda.lower() in row.astype(str).str.lower().values, axis=1)]
                
            if filtro_estado:
                df = df[df["Estado"].isin(filtro_estado)]
                
            if busqueda_direccion:
                df = df[df["Dirección Completa"].str.contains(busqueda_direccion, case=False, na=False)]

            # ==========================================
            # 📊 MOSTRAR TABLA
            # ==========================================
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=500 
            )

            st.caption(f"Total de registros encontrados: {len(df)}")
            st.divider()
            
            # Descarga Inteligente (Descarga solo lo filtrado)
            col1, col2 = st.columns([1, 3])
            with col1:
                csv = df.to_csv(index=False).encode('utf-8-sig') 
                st.download_button(
                    label="📥 Descargar Vista Actual (.csv)",
                    data=csv,
                    file_name="Directorio_Clientes_Filtrado.csv",
                    mime="text/csv",
                    type="primary"
                )
            with col2:
                st.write("💡 *Consejo: Usa los filtros de arriba para limpiar la tabla. El botón de Excel solo descargará los datos que estés viendo en pantalla.*")
        else:
            st.warning("No se encontraron clientes en la base de datos.")

    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")