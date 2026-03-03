import streamlit as st
import pandas as pd
import plotly.express as px 
from datetime import datetime, timedelta
from db_connection import get_db_client
import io
import os

# --- LIBRERÍAS PARA PDF (REPORTLAB) ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.units import cm

# ---------------------------------------------------------
# 1. FUNCIÓN GENERADORA DE PDF (DISEÑO PROFESIONAL)
# ---------------------------------------------------------
def generar_reporte_financiero_pdf(f_inicio, f_fin, entradas_totales, prestado, nomina, otros_gastos, balance):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    # Paleta Corporativa
    COLOR_VERDE = colors.HexColor("#4CAF50") # Verde Bosque
    COLOR_AZUL = colors.HexColor("#4CAF50")  # Azul Institucional (Nota: Aquí tienes el mismo hex que el verde, podrías ajustarlo si deseas un azul real como "#1976D2")
    COLOR_ROJO = colors.HexColor("#C62828")  # Rojo Alerta
    COLOR_FONDO = colors.HexColor("#F5F5F5") # Gris muy suave

    style_titulo = ParagraphStyle(name='TitleCorp', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, textColor=COLOR_AZUL, spaceAfter=12)
    style_normal = ParagraphStyle(name='NormalCorp', parent=styles['Normal'], fontSize=10, textColor=colors.black, leading=14)

    # Logo (si existe)
    logo_file = "logo.png" 
    if not os.path.exists(logo_file):
        for ext in [".jpg", ".jpeg"]:
            if os.path.exists("logo"+ext):
                logo_file = "logo"+ext
                break
    if os.path.exists(logo_file):
        im = Image(logo_file, width=2.5*cm, height=2.5*cm, kind='proportional')
        story.append(im)
    story.append(Spacer(1, 10))

    # Encabezado
    story.append(Paragraph("INFORME DE BALANCE FINANCIERO", style_titulo))
    story.append(Spacer(1, 15))

    # Información del Periodo
    fecha_txt = f"Periodo: {f_inicio.strftime('%d/%m/%Y')} - {f_fin.strftime('%d/%m/%Y')}"
    emision_txt = f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    
    story.append(Paragraph(fecha_txt, style_normal))
    story.append(Paragraph(emision_txt, style_normal))
    story.append(Spacer(1, 10))
    
    # Línea divisoria
    story.append(Table([['']], colWidths=[480], style=[('LINEBELOW', (0,0), (-1,-1), 1, COLOR_AZUL)]))
    story.append(Spacer(1, 20))

    # Tabla de Datos
    txt_entradas = f"C$ {entradas_totales:,.2f}"
    txt_prestado = f"(C$ {prestado:,.2f})"
    txt_nomina = f"(C$ {nomina:,.2f})"
    txt_otros = f"(C$ {otros_gastos:,.2f})"
    txt_balance = f"C$ {balance:,.2f}"

    data_finanzas = [
        ["CONCEPTO", "IMPORTE"],
        ["(+) Ingresos Totales (Cobranza + Aportes)", txt_entradas],
        ["(-) Colocación de Créditos", txt_prestado],
        ["(-) Nómina y Comisiones", txt_nomina],
        ["(-) Gastos Operativos Varios", txt_otros],
        ["", ""],
        ["FLUJO DE CAJA NETO", txt_balance]
    ]

    t_finanzas = Table(data_finanzas, colWidths=[330, 150])
    
    estilo_tabla = [
        ('BACKGROUND', (0,0), (-1,0), COLOR_AZUL),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('PADDING', (0,0), (-1,-1), 12),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,-1), (-1,-1), COLOR_FONDO), # Fondo fila total
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('SIZE', (0,-1), (-1,-1), 11),
    ]

    if balance < 0:
        estilo_tabla.append(('TEXTCOLOR', (1,-1), (1,-1), COLOR_ROJO))
    else:
        estilo_tabla.append(('TEXTCOLOR', (1,-1), (1,-1), COLOR_VERDE))

    t_finanzas.setStyle(TableStyle(estilo_tabla))
    story.append(t_finanzas)
    
    # Pie de página / Nota
    story.append(Spacer(1, 30))
    nota = "Nota: Este reporte refleja el flujo de efectivo real (Caja) durante el periodo seleccionado. No incluye intereses devengados pendientes de cobro."
    story.append(Paragraph(nota, style_normal))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# 2. VISTA PRINCIPAL (LÓGICA + DISEÑO LIMPIO)
# ---------------------------------------------------------
def mostrar_balance_financiero():
    # Título limpio
    col_t, col_d = st.columns([3,1])
    with col_t:
        st.markdown("## Balance General y Flujo de Caja")
    with col_d:
        st.caption(f"Actualizado: {datetime.now().strftime('%d/%m/%Y')}")
    
    st.markdown("---")
    
    supabase = get_db_client()

    # 1. FILTROS DE FECHA (Contenedor Desplegable)
    with st.expander("⚙️ Filtros de Fecha del Balance", expanded=False):
        c1, c2, c3 = st.columns([1, 1, 2])
        hoy = datetime.now().date()
        inicio_semana = hoy - timedelta(days=hoy.weekday()) 
        fin_semana = inicio_semana + timedelta(days=6)      

        with c1:
            f_inicio = st.date_input("Fecha Inicio", value=inicio_semana)
        with c2:
            f_fin = st.date_input("Fecha Fin", value=fin_semana)
        
        # Validación
        if f_inicio > f_fin:
            st.error("Error: La fecha de inicio no puede ser posterior a la fecha final.")
            return

    # FORMATO ISO PARA CONSULTA EXACTA
    f_inicio_iso = f"{f_inicio}T00:00:00"
    f_fin_iso = f"{f_fin}T23:59:59"

    # 2. CONSULTAS A BASE DE DATOS
    try:
        with st.spinner("Consolidando información financiera..."):
            # A. Cobros (Entradas)
            q_cobros = supabase.table("pagos")\
                .select("monto")\
                .gte("fecha_pago", f_inicio)\
                .lte("fecha_pago", f_fin)\
                .execute()
            
            # B. Préstamos (Salidas de Capital)
            q_prestamos = supabase.table("prestamos")\
                .select("monto_prestado")\
                .gte("fecha_inicio", f_inicio)\
                .lte("fecha_inicio", f_fin)\
                .in_("estado", ["activo", "pagado", "mora"])\
                .execute()
                
            # C. Caja (Gastos Operativos e Ingresos Varios)
            q_caja = supabase.table("movimientos_caja")\
                .select("monto, tipo, descripcion")\
                .gte("fecha", f_inicio_iso)\
                .lte("fecha", f_fin_iso)\
                .neq("tipo", "entrega_capital")\
                .execute()
            
            datos_caja = q_caja.data

    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return

    # 3. CÁLCULOS
    total_cobrado_clientes = sum([float(p['monto']) for p in q_cobros.data])
    total_prestado = sum([float(p['monto_prestado']) for p in q_prestamos.data])
    
    total_nomina = 0.0
    total_otros_gastos = 0.0
    total_otros_ingresos = 0.0 
    
    for mov in datos_caja:
        tipo = mov.get('tipo')
        monto = float(mov['monto'])
        monto_abs = abs(monto)

        if tipo == 'pago_nomina':
            total_nomina += monto_abs
        elif tipo == 'ingreso':
            total_otros_ingresos += monto_abs
        elif tipo in ['egreso', 'otros']:
            total_otros_gastos += monto_abs

    # Totales Finales
    total_entradas = total_cobrado_clientes + total_otros_ingresos
    total_salidas = total_prestado + total_nomina + total_otros_gastos
    balance_neto = total_entradas - total_salidas

    # 4. BOTÓN DE DESCARGA PDF
    st.write("")
    col_kpi_title, col_btn = st.columns([3, 1])
    with col_kpi_title:
        st.markdown("### Resumen Ejecutivo")
    
    with col_btn:
        pdf_buffer = generar_reporte_financiero_pdf(
            f_inicio, f_fin, 
            total_entradas, 
            total_prestado, 
            total_nomina, 
            total_otros_gastos, 
            balance_neto
        )
        
        nombre_archivo = f"Balance_{f_inicio}_al_{f_fin}.pdf"
        
        st.download_button(
            label="Descargar Reporte PDF",
            data=pdf_buffer,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )

    # 5. TARJETAS KPI (DISEÑO LIMPIO)
    with st.container(border=True):
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric(
                "Entradas Totales", 
                f"C$ {total_entradas:,.0f}", 
                delta=None,
                help="Suma de cobros realizados a clientes + ingresos extra registrados en caja."
            )
        with kpi2:
            st.metric(
                "Capital Colocado", 
                f"C$ {total_prestado:,.0f}", 
                delta="- Salida", 
                delta_color="inverse",
                help="Dinero entregado en nuevos préstamos durante este periodo."
            )
        with kpi3:
            st.metric(
                "Gastos Operativos", 
                f"C$ {(total_nomina + total_otros_gastos):,.0f}", 
                delta="- Salida", 
                delta_color="inverse",
                help="Suma de pago de nómina, servicios y otros egresos administrativos."
            )
        with kpi4:
            label_balance = "Superávit" if balance_neto > 0 else "Déficit"
            color_delta = "normal" if balance_neto > 0 else "inverse"
            st.metric(
                "Flujo Neto (Caja)", 
                f"C$ {balance_neto:,.0f}", 
                delta=label_balance, 
                delta_color=color_delta,
                help="Resultado final: Entradas - (Préstamos + Gastos). Indica la liquidez generada."
            )

    st.write("")

    # 6. GRÁFICOS ANALÍTICOS
    c_chart1, c_chart2 = st.columns(2)

    with c_chart1:
        st.markdown("#### Composición de Egresos")
        if total_salidas > 0:
            datos_salidas = {
                "Concepto": ["Préstamos (Inversión)", "Nómina", "Otros Gastos"],
                "Monto": [total_prestado, total_nomina, total_otros_gastos]
            }
            df_salidas = pd.DataFrame(datos_salidas)
            # Filtramos valores en 0 para limpiar el gráfico
            df_salidas = df_salidas[df_salidas["Monto"] > 0]
            
            # Colores sobrios (Pasteles profesionales)
            colores_pie = ["#90CAF9", "#A5D6A7", "#EF9A9A"] 
            
            fig = px.pie(
                df_salidas, 
                values='Monto', 
                names='Concepto', 
                hole=0.5, 
                color_discrete_sequence=colores_pie
            )
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Distribución porcentual del dinero que salió de la empresa.")
        else:
            st.info("No se registraron salidas de dinero en el periodo seleccionado.")

    with c_chart2:
        st.markdown("#### Comparativa de Flujo")
        datos_barras = {
            "Categoría": ["Entradas", "Salidas"],
            "Monto": [total_entradas, total_salidas],
            "Tipo": ["Ingreso", "Egreso"] # Para asignar color
        }
        df_barras = pd.DataFrame(datos_barras)
        
        # Colores semánticos estándar: Verde (Ingreso), Rojo Suave (Egreso)
        mapa_colores = {"Ingreso": "#66BB6A", "Egreso": "#EF5350"}
        
        fig2 = px.bar(
            df_barras, 
            x="Categoría", 
            y="Monto", 
            color="Tipo", 
            color_discrete_map=mapa_colores, 
            text_auto='.2s'
        )
        fig2.update_layout(
            showlegend=False, 
            margin=dict(t=20, b=20, l=20, r=20),
            yaxis_title="Monto (C$)"
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("Visualización directa de la relación Ingresos vs. Gastos Totales.")