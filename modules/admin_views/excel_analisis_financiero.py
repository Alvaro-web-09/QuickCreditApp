import streamlit as st
import pandas as pd
from db_connection import get_db_client

def mostrar_analisis_financiero():
    st.header("📈 Análisis Financiero")
    st.write("Métricas de rendimiento y estado global de la cartera.")

    # --- LEYENDA DE FÓRMULAS PARA EL CLIENTE ---
    with st.expander("📝 Leyenda de Fórmulas y Referencias en BD (Haz clic para expandir)"):
        st.markdown("""
        Esta tabla explica cómo se calcula cada indicador basándose estrictamente en la base de datos:

        | Indicador | Lógica / Fórmula | Referencia exacta en Supabase |
        | :--- | :--- | :--- |
        | **Capital invertido** | Dinero semilla de la empresa. | *Input manual en pantalla* |
        | **Capital colocado** | Sumatoria de préstamos otorgados. | `prestamos.monto_prestado` |
        | **Capital recuperado** | Porción de capital de cada pago. | `pagos.monto` (desglosado) |
        | **Gastos Operativos** | Egresos registrados + Ajuste. | `movimientos_caja.monto` + *Input* |
        | **Capital disponible**| `Invertido - Colocado + Recuperado - Gastos` | *Calculado* |
        | **Saldo pendiente** | Deudas activas (Principal y Total). | `prestamos.monto_prestado` - capital pagado |
        | **Cartera Operativa** | Igual al *Capital disponible*. | *Calculado* |
        | **Cartera Actual** | `Cartera Operativa + Saldo pendiente total` | *Calculado* |
        | **Intereses generados** | Ganancia total proyectada. | `prestamos.monto_total_deuda` - `monto_prestado` |
        | **Intereses cobrados** | Porción de interés recibida. | `pagos.monto` (desglosado) |
        | **Ganancia neta** | `Intereses cobrados - Gastos Operativos` | *Calculado* |
        | **Margen neto total** | `Ganancia neta / Capital invertido` | *Calculado* |
        | **Capital promedio** | `(Capital Colocado + Saldo pendiente principal) / 2` | *Calculado* |
        | **Yield de cartera** | `Intereses generados / Capital promedio` | *Calculado* |
        | **Rotación de capital** | `Capital colocado / Capital invertido` | *Calculado* |
        | **Rotación de cartera** | `Capital recuperado / Capital promedio` | *Calculado* |
        | **Ingreso diario** | `Intereses generados / 30` | *Calculado* |
        | **ROI** | `Intereses generados / Capital invertido` | *Calculado* |
        | **ROI real** | `Ganancia neta / Capital invertido` | *Calculado* |
        """)

    supabase = get_db_client()

    # --- INPUTS INICIALES ---
    col1, col2 = st.columns(2)
    with col1:
        capital_invertido = st.number_input("💰 Capital Invertido (Dinero Semilla)", value=480000.0, step=5000.0)
    with col2:
        gastos_manuales = st.number_input("📉 Ajuste Manual de Gastos (+)", value=40000.0, step=1000.0)

    st.divider()

    try:
        # 1. Obtener Préstamos (Columnas exactas del esquema)
        res_prestamos = supabase.table("prestamos").select("id, monto_prestado, monto_total_deuda, saldo_pendiente, estado").execute()
        df_prestamos = pd.DataFrame(res_prestamos.data) if res_prestamos.data else pd.DataFrame()

        # 2. Obtener Pagos (Columnas exactas del esquema)
        res_pagos = supabase.table("pagos").select("prestamo_id, monto").execute()
        df_pagos = pd.DataFrame(res_pagos.data) if res_pagos.data else pd.DataFrame()

        # 3. Obtener Gastos Reales de Movimientos de Caja
        res_movimientos = supabase.table("movimientos_caja").select("monto, tipo").execute()
        df_mov = pd.DataFrame(res_movimientos.data) if res_movimientos.data else pd.DataFrame()
        
        gastos_bd = 0.0
        if not df_mov.empty:
            df_mov['monto'] = pd.to_numeric(df_mov['monto'], errors='coerce').fillna(0)
            df_mov['tipo'] = df_mov['tipo'].astype(str).str.lower()
            # Asumimos que los egresos pueden estar registrados con alguna de estas palabras
            gastos_bd = df_mov[df_mov['tipo'].isin(['egreso', 'gasto', 'salida'])]['monto'].sum()

        if df_prestamos.empty:
            st.warning("No hay suficientes datos en la tabla 'prestamos' para realizar el análisis.")
            return

        # Limpiar numéricos garantizando compatibilidad con "numeric" de Supabase
        for col in ['monto_prestado', 'monto_total_deuda', 'saldo_pendiente']:
            df_prestamos[col] = pd.to_numeric(df_prestamos[col], errors='coerce').fillna(0)

        # Proporciones de interés y capital
        df_prestamos['interes_total'] = df_prestamos['monto_total_deuda'] - df_prestamos['monto_prestado']
        
        df_prestamos['proporcion_interes'] = df_prestamos.apply(
            lambda row: row['interes_total'] / row['monto_total_deuda'] if row['monto_total_deuda'] > 0 else 0, 
            axis=1
        )
        df_prestamos['proporcion_capital'] = 1 - df_prestamos['proporcion_interes']

        # --- CÁLCULO DE PAGOS ---
        capital_recuperado = 0.0
        intereses_cobrados_reales = 0.0

        if not df_pagos.empty:
            df_pagos['monto'] = pd.to_numeric(df_pagos['monto'], errors='coerce').fillna(0)
            
            df_pagos_detallados = pd.merge(
                df_pagos, 
                df_prestamos[['id', 'proporcion_capital', 'proporcion_interes']], 
                left_on='prestamo_id', 
                right_on='id', 
                how='left'
            ).fillna(0)

            df_pagos_detallados['capital_pagado'] = df_pagos_detallados['monto'] * df_pagos_detallados['proporcion_capital']
            df_pagos_detallados['interes_pagado'] = df_pagos_detallados['monto'] * df_pagos_detallados['proporcion_interes']

            capital_recuperado = df_pagos_detallados['capital_pagado'].sum()
            intereses_cobrados_reales = df_pagos_detallados['interes_pagado'].sum()

            capital_pagado_por_prestamo = df_pagos_detallados.groupby('prestamo_id')['capital_pagado'].sum().reset_index()
            df_prestamos = pd.merge(df_prestamos, capital_pagado_por_prestamo, left_on='id', right_on='prestamo_id', how='left').fillna(0)
        else:
            df_prestamos['capital_pagado'] = 0.0

        # --- MÉTRICAS FINALES ---
        capital_colocado = df_prestamos['monto_prestado'].sum()
        gastos_operativos = gastos_bd + gastos_manuales 
        capital_disponible = capital_invertido - capital_colocado + capital_recuperado - gastos_operativos
        
        df_prestamos['principal_pendiente'] = df_prestamos['monto_prestado'] - df_prestamos['capital_pagado']
        
        # Filtramos estado != 'pagado' basado en la columna text de Supabase
        saldo_pendiente_principal = df_prestamos[df_prestamos['estado'].str.lower() != 'pagado']['principal_pendiente'].sum()
        saldo_pendiente_total = df_prestamos[df_prestamos['estado'].str.lower() != 'pagado']['saldo_pendiente'].sum()

        cartera_operativa = capital_disponible
        cartera_actual = cartera_operativa + saldo_pendiente_total
        intereses_generados = df_prestamos['interes_total'].sum()
        
        ganancia_neta = intereses_cobrados_reales - gastos_operativos
        margen_neto_total = (ganancia_neta / capital_invertido) if capital_invertido > 0 else 0
        
        capital_promedio = (capital_colocado + saldo_pendiente_principal) / 2 
        
        yield_cartera = (intereses_generados / capital_promedio) if capital_promedio > 0 else 0
        rotacion_capital = (capital_colocado / capital_invertido) if capital_invertido > 0 else 0
        rotacion_cartera = (capital_recuperado / capital_promedio) if capital_promedio > 0 else 0
        
        ingreso_diario_cartera = intereses_generados / 30 
        
        roi = (intereses_generados / capital_invertido) if capital_invertido > 0 else 0
        roi_real = (ganancia_neta / capital_invertido) if capital_invertido > 0 else 0

        # --- PREPARACIÓN DE TABLA VISUAL ---
        def fmt_c(val): return f"C$ {val:,.2f}"
        def fmt_p(val): return f"{val * 100:,.2f}%"

        datos_indicadores = [
            {"Indicador": "Capital invertido", "Valor": fmt_c(capital_invertido), "Valor Secundario": ""},
            {"Indicador": "Capital colocado", "Valor": fmt_c(capital_colocado), "Valor Secundario": ""},
            {"Indicador": "Capital recuperado", "Valor": fmt_c(capital_recuperado), "Valor Secundario": ""},
            {"Indicador": "Gastos Operativos", "Valor": fmt_c(gastos_operativos), "Valor Secundario": ""},
            {"Indicador": "Capital disponible para prestar", "Valor": fmt_c(capital_disponible), "Valor Secundario": ""},
            {"Indicador": "Saldo pendiente de cartera/Cartera viva", "Valor": fmt_c(saldo_pendiente_principal), "Valor Secundario": fmt_c(saldo_pendiente_total)},
            {"Indicador": "Cartera Operativa", "Valor": fmt_c(cartera_operativa), "Valor Secundario": ""},
            {"Indicador": "Cartera Actual", "Valor": fmt_c(cartera_actual), "Valor Secundario": ""},
            {"Indicador": "Intereses generados", "Valor": fmt_c(intereses_generados), "Valor Secundario": ""},
            {"Indicador": "Intereses cobrados reales", "Valor": fmt_c(intereses_cobrados_reales), "Valor Secundario": ""},
            {"Indicador": "Ganancia neta", "Valor": fmt_c(ganancia_neta), "Valor Secundario": ""},
            {"Indicador": "Margen neto total", "Valor": fmt_p(margen_neto_total), "Valor Secundario": ""},
            {"Indicador": "Capital promedio", "Valor": fmt_c(capital_promedio), "Valor Secundario": ""},
            {"Indicador": "Yield de cartera", "Valor": fmt_p(yield_cartera), "Valor Secundario": ""},
            {"Indicador": "---", "Valor": "---", "Valor Secundario": "---"}, 
            {"Indicador": "Rotación de capital", "Valor": fmt_p(rotacion_capital), "Valor Secundario": ""},
            {"Indicador": "Rotación de cartera", "Valor": fmt_p(rotacion_cartera), "Valor Secundario": ""},
            {"Indicador": "Ingreso diario cartera", "Valor": fmt_c(ingreso_diario_cartera), "Valor Secundario": ""},
            {"Indicador": "ROI", "Valor": fmt_p(roi), "Valor Secundario": ""},
            {"Indicador": "ROI real", "Valor": fmt_p(roi_real), "Valor Secundario": ""}
        ]

        df_analisis = pd.DataFrame(datos_indicadores)

        def highlight_row(row):
            if row['Indicador'] == 'Intereses cobrados reales':
                return ['background-color: #dcedc8; color: black'] * len(row) 
            elif row['Indicador'] == '---':
                return ['background-color: #f0f2f6; color: transparent'] * len(row)
            return [''] * len(row)

        st.dataframe(
            df_analisis.style.apply(highlight_row, axis=1),
            use_container_width=True,
            hide_index=True,
            height=750
        )

    except Exception as e:
        st.error(f"Error al generar el Análisis Financiero: {str(e)}")