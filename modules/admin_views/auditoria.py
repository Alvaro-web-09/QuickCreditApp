import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from db_connection import get_db_client
import io
import os
import time
from zoneinfo import ZoneInfo

# --- LIBRERÍAS PARA PDF (REPORTLAB) ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.units import cm

# ==============================================================================
# 1. ESTILOS Y CONFIGURACIÓN
# ==============================================================================
def aplicar_estilos_corporativos():
    # CSS para una interfaz limpia tipo SaaS
    st.markdown("""
        <style>
            .block-container { padding-top: 2rem; }
            h1, h2, h3 { font-family: 'Helvetica', sans-serif; color: #2C3E50; }
            .stButton>button { width: 100%; border-radius: 6px; }
            div[data-testid="stMetricValue"] { font-size: 1.5rem; color: #2C3E50; }
        </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. GENERADOR DE PDF (LÓGICA ROBUSTA + DISEÑO ELEGANTE)
# ==============================================================================
def generar_voucher_pdf(datos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    # Paleta de colores Corporativa (Azul Oscuro / Gris)
    COLOR_PRINCIPAL = colors.HexColor("#2C3E50") # Azul acero oscuro
    COLOR_SECUNDARIO = colors.HexColor("#ECF0F1") # Gris muy claro
    
    # Estilos de texto
    estilo_titulo = ParagraphStyle(name='Title', parent=styles['Heading2'], alignment=TA_CENTER, textColor=COLOR_PRINCIPAL)
    
    # 1. Logo (con tu lógica de detección)
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
    story.append(Paragraph("COMPROBANTE DE PAGO", estilo_titulo))
    story.append(Spacer(1, 20))

    # 2. Información General
    data_info = [
        ["Beneficiario:", datos.get('chofer', 'N/A')],
        ["Periodo:", f"{datos.get('desde', '-')} al {datos.get('hasta', '-')}"],
        ["Concepto:", datos.get('semana_txt', 'N/A')],
        ["Fecha Emisión:", datetime.now(ZoneInfo("America/Managua")).strftime("%d/%m/%Y %H:%M")],
    ]
    t_info = Table(data_info, colWidths=[120, 320])
    t_info.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,0), (-1,-1), COLOR_PRINCIPAL),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 20))

    # 3. Desglose Económico
    if 'base' in datos:
        # Pago Nuevo (Detallado)
        data_pago = [
            ["DESCRIPCIÓN", "MONTO"],
            ["Salario Base", f"C$ {datos['base']:,.2f}"],
            [f"Comisión ({datos.get('pct_comision', 0)}%)", f"C$ {datos.get('monto_comision', 0):,.2f}"],
            ["Viáticos / Combustible", f"C$ {datos.get('combustible', 0):,.2f}"],
            ["TOTAL NETO", f"C$ {datos['total']:,.2f}"]
        ]
    else:
        # Reimpresión (Resumido)
        data_pago = [
            ["DESCRIPCIÓN", "MONTO"],
            [datos.get('descripcion_corta', 'Pago de Nómina'), ""],
            ["TOTAL REGISTRADO", f"C$ {datos['total']:,.2f}"],
        ]

    t_pago = Table(data_pago, colWidths=[320, 120])
    
    # Estilo de Tabla Minimalista
    t_pago.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,0), 1, COLOR_PRINCIPAL),      # Línea bajo header
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),         # Header en negrita
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),                     # Montos a la derecha
        ('TEXTCOLOR', (0,0), (-1,-1), COLOR_PRINCIPAL),
        ('topPadding', (0,0), (-1,-1), 8),
        # Fila Total (última fila)
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.grey),
        ('BACKGROUND', (0,-1), (-1,-1), COLOR_SECUNDARIO),     # Fondo sutil en total
    ]))
    story.append(t_pago)
    
    # 4. Firmas
    story.append(Spacer(1, 60))
    data_firmas = [
        ["__________________________", "__________________________"],
        ["Autorizado", "Recibido Conforme"]
    ]
    t_firmas = Table(data_firmas, colWidths=[220, 220])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.grey),
    ]))
    story.append(t_firmas)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==============================================================================
# 3. VISTA PRINCIPAL
# ==============================================================================
def mostrar_auditoria():
    aplicar_estilos_corporativos()
    st.header("Tesorería / Liquidación de Nómina")
    st.markdown("---")
    
    supabase = get_db_client()

    # --- FILTROS (Contenedor Desplegable Homogeneizado) ---
    with st.expander("⚙️ Configuración y Filtros", expanded=False):
        # Cargar Usuarios
        try:
            users = supabase.table("usuarios").select("id, username, nombre_completo").execute().data
            mapa_users = {u.get('nombre_completo', u['username']): u['id'] for u in users}
        except:
            st.error("Conexión perdida con base de datos")
            return

        c1, c2, c3 = st.columns([2, 1, 1])
        
        with c1:
            sel_chofer = st.selectbox("Colaborador", options=list(mapa_users.keys()))
            id_chofer = mapa_users[sel_chofer]
        
        hoy = date.today()
        inicio_def = hoy - timedelta(days=hoy.weekday() + 7)
        fin_def = inicio_def + timedelta(days=6)
        
        with c2:
            f_inicio = st.date_input("Inicio Periodo", value=inicio_def)
            
        with c3:
            f_fin = st.date_input("Fin Periodo", value=fin_def)
            num_semana = f_inicio.isocalendar()[1] if f_inicio else 0
            st.caption(f"Semana Fiscal: #{num_semana}")

    # --- PESTAÑAS (TABS) ---
    tab_nuevo, tab_historial = st.tabs(["Nueva Liquidación", "Historial de Pagos"])

    # --------------------------------------------------------
    # TAB 1: NUEVA LIQUIDACIÓN
    # --------------------------------------------------------
    with tab_nuevo:
        # Calcular Pendientes
        f_inicio_iso = f"{f_inicio}T00:00:00"
        f_fin_iso = f"{f_fin}T23:59:59"
        
        try:
            res = supabase.table("pagos").select("id, fecha_pago, monto, prestamos(clientes(nombre))")\
                .eq("cobrador_id", id_chofer).eq("comision_pagada", False)\
                .gte("fecha_pago", f_inicio_iso).lte("fecha_pago", f_fin_iso).execute()
            cobros = res.data or []
            total_recuperado = sum(c['monto'] for c in cobros)
        except:
            cobros = []; total_recuperado = 0

        # Layout Columnas
        col_resumen, col_calc = st.columns([1, 1])

        with col_resumen:
            st.subheader("Actividad Reciente")
            if cobros:
                df = pd.DataFrame([{
                    "Fecha": datetime.fromisoformat(c['fecha_pago']).strftime('%d/%m'),
                    "Cliente": c['prestamos']['clientes']['nombre'] if c['prestamos'] else 'N/A',
                    "Monto": c['monto']
                } for c in cobros])
                st.dataframe(df, use_container_width=True, height=220, hide_index=True)
                st.info(f"{len(cobros)} cobros pendientes de comisión.")
            else:
                st.warning("No hay actividad pendiente en este rango.")

        with col_calc:
            st.subheader("Liquidación")
            with st.container(border=True):
                val_base = st.number_input("Salario Base", value=2000.0, step=100.0)
                val_pct = st.number_input("% Comisión", value=5.0, step=0.5)
                val_gas = st.number_input("Viáticos / Combustible", value=500.0, step=50.0)
                
                comision = total_recuperado * (val_pct/100)
                total = val_base + comision + val_gas
                
                st.markdown("---")
                c1, c2 = st.columns(2)
                c1.metric("Comisión", f"C$ {comision:,.2f}")
                c2.metric("Total Neto", f"C$ {total:,.2f}")

            if st.button("Registrar Pago", type="primary", disabled=(total <= 0)):
                try:
                    # PASO 1: MOVIMIENTO DE CAJA
                    desc_mov = f"Pago Nómina S#{num_semana} - {sel_chofer}"
                    res_mov = supabase.table("movimientos_caja").insert({
                        "usuario_id": id_chofer,
                        "tipo": "pago_nomina",
                        "monto": -total,
                        "descripcion": desc_mov
                    }).execute()
                    
                    mov_id = res_mov.data[0]['id']

                    # PASO 2: REGISTRO DE NÓMINA (Ajustado a tus nombres de columna)
                    res_nom = supabase.table("nominas").insert({
                        "cobrador_id": id_chofer,
                        # Usamos los nombres exactos de tu tabla en Supabase:
                        "periodo_inicio": f_inicio.isoformat(), 
                        "periodo_fin": f_fin.isoformat(),
                        "salario_base": val_base,
                        "monto_comision": comision,
                        "viaticos_combustible": val_gas, # Verifica si este es el nombre en SQL
                        "total_pagado": total,           # En tu SQL se llama 'total_pagado'
                        "movimiento_id": mov_id          # Verifica si creaste esta columna
                    }).execute()
                    
                    nomina_id = res_nom.data[0]['id']

                    # PASO 3: VINCULAR PAGOS
                    ids_pagos = [c['id'] for c in cobros]
                    if ids_pagos:
                        supabase.table("pagos").update({
                            "comision_pagada": True, 
                            "nomina_id": nomina_id
                        }).in_("id", ids_pagos).execute()

                    # PASO 4: GENERAR PDF
                    pdf_data = {
                        "chofer": sel_chofer, "desde": f_inicio.strftime('%d/%m'), "hasta": f_fin.strftime('%d/%m'),
                        "semana_txt": f"Semana #{num_semana}", "base": val_base,
                        "pct_comision": val_pct, "monto_comision": comision,
                        "combustible": val_gas, "total": total
                    }
                    pdf_bytes = generar_voucher_pdf(pdf_data)
                    
                    st.session_state['pdf_temp'] = pdf_bytes
                    st.session_state['pdf_name'] = f"Nomina_{sel_chofer}_S{num_semana}.pdf"
                    st.rerun()

                except Exception as e:
                    st.error(f"Error al registrar: {e}")

        # Zona de Descarga Persistente
        if st.session_state.get('pdf_temp'):
            st.markdown("---")
            with st.container(border=True):
                c_dl1, c_dl2 = st.columns([3, 1])
                c_dl1.success("✅ Pago registrado con éxito.")
                c_dl2.download_button("Descargar PDF", st.session_state['pdf_temp'], 
                                    st.session_state['pdf_name'], "application/pdf", type="primary")
                if c_dl1.button("Nuevo Pago"):
                    del st.session_state['pdf_temp']
                    st.rerun()

    # --------------------------------------------------------
    # TAB 2: HISTORIAL
    # --------------------------------------------------------
    with tab_historial:
        st.subheader("Últimos Pagos")
        try:
            hist = supabase.table("movimientos_caja").select("*")\
                .eq("tipo", "pago_nomina").order("fecha", desc=True).limit(10).execute().data
            
            if hist:
                for h in hist:
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([1, 3, 1, 1])
                        fecha = datetime.fromisoformat(h['fecha']).strftime("%d/%m")
                        c1.text(fecha)
                        c2.text(h.get('descripcion', ''))
                        c3.markdown(f"**C$ {abs(h['monto']):,.2f}**")
                        
                        # Generación PDF Histórico
                        if c4.button("PDF", key=f"b_{h['id']}"):
                            pdf_h = generar_voucher_pdf({
                                "chofer": sel_chofer, # Nota: En prod idealmente usar nombre del ID guardado
                                "desde": "Histórico", "hasta": fecha,
                                "semana_txt": "Reimpresión Copia",
                                "total": abs(h['monto']),
                                "descripcion_corta": h.get('descripcion', '')
                            })
                            st.session_state[f"pdf_{h['id']}"] = pdf_h
                        
                        if f"pdf_{h['id']}" in st.session_state:
                             st.download_button("📥", st.session_state[f"pdf_{h['id']}"], 
                                                f"Voucher_{h['id']}.pdf", key=f"d_{h['id']}")
            else:
                st.caption("No hay historial disponible.")
        except Exception as e:
            st.error(f"Error historial: {e}")