import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from db_connection import get_db_client
import io
import os
from datetime import datetime

# --- LIBRERÍAS PARA PDF (REPORTLAB) ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.units import cm

# ---------------------------------------------------------
# 1. FUNCIÓN GENERADORA DE PDF (ESTILO BANCARIO / FORMAL)
# ---------------------------------------------------------
def generar_pdf_estado_cuenta(cliente_info, prestamo_info, cobrador_asignado, df_movimientos, resumen_totales):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    # Colores Corporativos (Sobrios)
    COLOR_PRIMARIO = colors.HexColor("#1B5E20")  # Verde Oscuro Corporativo
    COLOR_SECUNDARIO = colors.HexColor("#455A64") # Gris Azulado
    COLOR_FILA_PAR = colors.HexColor("#F5F5F5")   # Gris muy claro para filas
    COLOR_TEXTO = colors.black

    # Estilos de Texto
    style_titulo = ParagraphStyle(name='H1_Corp', parent=styles['Heading1'], alignment=TA_RIGHT, fontSize=18, textColor=COLOR_PRIMARIO, spaceAfter=2)
    style_sub = ParagraphStyle(name='Sub_Corp', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=9, textColor=COLOR_SECUNDARIO)
    style_th = ParagraphStyle(name='TH_Corp', parent=styles['Normal'], fontSize=9, textColor=colors.white, alignment=TA_CENTER)
    style_td = ParagraphStyle(name='TD_Corp', parent=styles['Normal'], fontSize=9, textColor=COLOR_TEXTO)
    style_td_num = ParagraphStyle(name='TD_Num', parent=styles['Normal'], fontSize=9, textColor=COLOR_TEXTO, alignment=TA_RIGHT)

    # 1. ENCABEZADO
    # Logo
    logo_file = "logo.png"
    if not os.path.exists(logo_file):
        for ext in [".jpg", ".jpeg"]:
            if os.path.exists("logo"+ext):
                logo_file = "logo"+ext
                break
    
    img_logo = Image(logo_file, width=3.5*cm, height=3.5*cm, kind='proportional') if os.path.exists(logo_file) else Paragraph("", styles['Normal'])
    
    # Textos Encabezado
    codigo_prestamo_pdf = prestamo_info.get('codigo_prestamo', prestamo_info['id'].split('-')[0].upper())
    
    datos_empresa = [
        Paragraph("ESTADO DE CUENTA", style_titulo),
        Paragraph(f"Fecha de Emisión: {datetime.now().strftime('%d/%m/%Y')}", style_sub),
        Paragraph(f"Ref. Crédito: {codigo_prestamo_pdf}", style_sub)
    ]

    t_header = Table([[img_logo, datos_empresa]], colWidths=[200, 330])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))
    
    # Línea separadora
    story.append(Table([['']], colWidths=[530], style=[('LINEBELOW', (0,0), (-1,-1), 1.5, COLOR_PRIMARIO)]))
    story.append(Spacer(1, 15))

    # 2. INFORMACIÓN DEL CLIENTE Y CRÉDITO
    codigo_cli_pdf = cliente_info.get('codigo_cliente', 'S/C')
    txt_cliente = f"""
    <b>CLIENTE:</b><br/>
    {codigo_cli_pdf} - {cliente_info['nombre']}<br/>
    ID/Cédula: {cliente_info['cedula']}
    """
    
    txt_credito = f"""
    <b>DETALLES DEL CRÉDITO:</b><br/>
    Fecha Inicio: {prestamo_info['fecha_inicio']}<br/>
    Oficial Asignado: {cobrador_asignado}<br/>
    Estado Actual: {prestamo_info['estado'].upper()}
    """
    
    t_info = Table([
        [Paragraph(txt_cliente, style_td), Paragraph(txt_credito, style_td)]
    ], colWidths=[265, 265])
    
    t_info.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 20))

    # 3. TABLA DE MOVIMIENTOS
    headers = [
        Paragraph('FECHA', style_th), 
        Paragraph('CONCEPTO', style_th), 
        Paragraph('RESPONSABLE', style_th), 
        Paragraph('MONTO', style_th)
    ]
    
    data_rows = [headers]
    
    for _, row in df_movimientos.iterrows():
        monto_fmt = f"C$ {row['Monto']:,.2f}" if row['Monto'] > 0 else "-"
        if row['Tipo'] == "Visita Sin Cobro":
            monto_fmt = "0.00"
            
        data_rows.append([
            Paragraph(str(row['Fecha']), style_td),
            Paragraph(row['Tipo'], style_td),
            Paragraph(str(row['Cobrador']), style_td),
            Paragraph(monto_fmt, style_td_num)
        ])

    t_movs = Table(data_rows, colWidths=[70, 180, 160, 120])
    
    estilo_tabla_movs = [
        ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARIO), 
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (3,1), (3,-1), 'RIGHT'), 
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, COLOR_FILA_PAR]) 
    ]
    t_movs.setStyle(TableStyle(estilo_tabla_movs))
    story.append(t_movs)
    story.append(Spacer(1, 20))

    # 4. TOTALES 
    data_totales = [
        ["Capital Prestado:", f"C$ {prestamo_info['monto_prestado']:,.2f}"],
        ["Intereses:", f"C$ {resumen_totales.get('interes', 0):,.2f}"],
        ["Total a Pagar:", f"C$ {resumen_totales.get('total_deuda', 0):,.2f}"],
        ["Total Abonado:", f"C$ {resumen_totales['pagado']:,.2f}"],
        ["Saldo Pendiente:", f"C$ {resumen_totales['saldo']:,.2f}"]
    ]
    
    t_totales = Table(data_totales, colWidths=[120, 120])
    t_totales.setStyle(TableStyle([
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica-Bold'),
        ('LINEABOVE', (0,-1), (-1,-1), 1, COLOR_PRIMARIO), 
        ('TEXTCOLOR', (0,-1), (-1,-1), COLOR_PRIMARIO),
    ]))
    
    t_layout = Table([['', t_totales]], colWidths=[290, 240])
    story.append(t_layout)

    story.append(Spacer(1, 40))
    nota = "Nota: Documento generado electrónicamente. Para aclaraciones, contacte a administración."
    story.append(Paragraph(nota, ParagraphStyle(name='Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# 2. VISTA PRINCIPAL (STREAMLIT CLEAN)
# ---------------------------------------------------------
def mostrar_estado_cuenta():
    c_head, c_date = st.columns([3, 1])
    with c_head:
        st.markdown("## Historial de Crédito")
    with c_date:
        st.caption(f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
    
    st.markdown("---")

    supabase = get_db_client()

    try:
        # 1. Mapa Usuarios 
        mapa_usuarios = {}
        users = supabase.table("usuarios").select("id, nombre_completo, username").execute().data
        for u in users:
            name = u['nombre_completo'] if u['nombre_completo'] else u['username']
            mapa_usuarios[u['id']] = name
            
        # 2. Lista Clientes
        clientes = supabase.table("clientes").select("id, nombre, cedula, codigo_cliente").order('nombre').execute().data
        if not clientes:
            st.info("No se encontraron clientes registrados.")
            return

        opciones_cliente = {f"[{c.get('codigo_cliente', 'S/C')}] {c['nombre']}": c['id'] for c in clientes} 
        
        # --- UI SELECCIÓN CON EXPANSOR ---
        with st.expander("🔍 Filtros de Búsqueda (Clic para ocultar/mostrar)", expanded=True):
            st.markdown("#### 1. Buscar Cliente")
            seleccion_nombre = st.selectbox(
                "Seleccione un cliente", 
                options=list(opciones_cliente.keys()), 
                index=None,
                label_visibility="collapsed",
                placeholder="Escribe para buscar..."
            )

            if not seleccion_nombre:
                st.info("👈 Seleccione un cliente arriba para ver su expediente.")
                return

            cliente_id = opciones_cliente[seleccion_nombre]
            datos_cliente = next((c for c in clientes if c['id'] == cliente_id), None)

            # 3. Historial Préstamos
            prestamos = supabase.table("prestamos")\
                .select("*")\
                .eq("cliente_id", cliente_id)\
                .order("fecha_inicio", desc=True)\
                .execute().data

            if not prestamos:
                st.warning("El cliente seleccionado no tiene historial de préstamos.")
                return

            st.markdown("#### 2. Elegir Crédito")
            mapa_prestamos = {}
            for p in prestamos:
                icono = "🟢" if p['estado'] == 'activo' else "🏁" if p['estado'] == 'pagado' else "🔴"
                cod_p = p.get('codigo_prestamo', 'S/C')
                lbl = f"{icono} {cod_p} | {p['fecha_inicio']} | C$ {p['monto_prestado']:,.0f}"
                mapa_prestamos[lbl] = p
            
            lbl_prestamo = st.selectbox(
                "Seleccione préstamo", 
                options=list(mapa_prestamos.keys()),
                label_visibility="collapsed"
            )
            
            prestamo_sel = mapa_prestamos[lbl_prestamo]
            prestamo_id = prestamo_sel['id']

            # 4. Buscar Oficial Asignado
            nombre_cobrador = "No Asignado"
            solicitud = supabase.table("solicitudes")\
                .select("cobrador_id")\
                .eq("id_cliente_existente", cliente_id)\
                .eq("estado", "aprobada")\
                .order("fecha_solicitud", desc=True)\
                .limit(1)\
                .execute().data
                
            if solicitud:
                cob_id = solicitud[0].get('cobrador_id')
                nombre_cobrador = mapa_usuarios.get(cob_id, "Desconocido")

    except Exception as e:
        st.error(f"Error recuperando datos: {e}")
        return

    # --- PROCESAMIENTO DE MOVIMIENTOS ---
    pagos = supabase.table("pagos").select("*").eq("prestamo_id", prestamo_id).execute().data
    visitas = supabase.table("bitacora_visitas")\
        .select("fecha, estado_visita, cobrador_id")\
        .eq("cliente_id", cliente_id)\
        .gte("fecha", prestamo_sel['fecha_inicio'])\
        .execute().data

    # Cálculos Financieros
    total_pagado = sum([p['monto'] for p in pagos])
    
    # 1. Obtenemos el Saldo Pendiente real (deuda restante)
    saldo_actual = prestamo_sel.get('saldo_pendiente', prestamo_sel['monto_prestado'] - total_pagado)

    # 2. Desglose del Préstamo
    capital_prestado = prestamo_sel['monto_prestado']
    
    # La deuda original completa (Total a Pagar) es lo que ya pagó + lo que aún debe
    total_deuda = total_pagado + saldo_actual 
    
    # El interés es la diferencia entre la deuda total y el dinero entregado
    intereses_totales = max(0, total_deuda - capital_prestado)

    # Progreso basado en la Deuda Total
    porcentaje_pagado = 0.0
    if total_deuda > 0:
        porcentaje_pagado = min(total_pagado / total_deuda, 1.0)

    # --- NUEVO: ALERTA DE MORA / ESTADO ---
    if prestamo_sel['estado'] == 'pagado':
        st.success("🎉 Este crédito ya ha sido cancelado en su totalidad.")
    else:
        if pagos:
            fechas_pagos = [pd.to_datetime(p['fecha_pago']) for p in pagos]
            ultima_fecha = max(fechas_pagos)
            dias_sin_pago = (datetime.now() - ultima_fecha).days
            if dias_sin_pago > 7:
                st.error(f"⚠️ **Alerta:** El cliente lleva **{dias_sin_pago} días** sin registrar un abono.")
            elif dias_sin_pago > 3:
                st.warning(f"⏳ **Atención:** El último pago fue hace **{dias_sin_pago} días**.")
            else:
                st.info(f"✅ **Al día:** Último pago registrado hace **{dias_sin_pago} días**.")
        else:
            st.info("No se han registrado pagos para este crédito aún.")

    # --- UI: TARJETAS KPI (DESGLOSE COMPLETO) ---
    with st.container(border=True):
        # Usamos 6 columnas para contar toda la historia financiera
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        
        with k1:
            st.metric("Capital Prestado", f"C$ {capital_prestado:,.0f}", help="Dinero entregado al cliente")
        with k2:
            st.metric("Intereses", f"C$ {intereses_totales:,.0f}", help="Ganancia por el préstamo")
        with k3:
            st.metric("Total a Pagar", f"C$ {total_deuda:,.0f}", help="Capital + Intereses")
        with k4:
            st.metric("Total Abonado", f"C$ {total_pagado:,.0f}", delta="Recuperado")
        with k5:
            st.metric("Saldo Pendiente", f"C$ {saldo_actual:,.0f}", delta="Por cobrar", delta_color="inverse")
        with k6:
            st.metric("Estado", prestamo_sel['estado'].upper())
        
        # Barra de progreso
        st.progress(porcentaje_pagado, text=f"Progreso del Crédito: {int(porcentaje_pagado * 100)}%")

    st.write("")

    # --- PREPARACIÓN DE DATOS PARA GRÁFICOS ---
    data_mix = []
    
    for p in pagos:
        c_name = mapa_usuarios.get(p.get('cobrador_id'), "Oficina")
        # Jala la fecha sin importar cómo se llame exactamente en la tabla
        fecha_real = p.get('fecha_pago') or p.get('fecha_hora') or p.get('created_at')
        
        data_mix.append({
            "Fecha": fecha_real,
            "Tipo": "Abono",
            "Monto": float(p.get('monto', 0)),
            "Cobrador": c_name,
            "Categoria": "Ingreso"
        })
        
    # --- PROCESAR VISITAS (CORREGIDO) ---
    for v in visitas:
        # Solo agregamos al historial si la visita fue explícitamente un "No Pago"
        if v.get('estado_visita') == 'No Pago':
            c_name = mapa_usuarios.get(v.get('cobrador_id'), "Cobrador")
            data_mix.append({
                "Fecha": v.get('fecha'),
                "Tipo": "Visita Sin Cobro",
                "Monto": 0.0,
                "Cobrador": c_name,
                "Categoria": "Incidencia"
            })

    if data_mix:
        
        # --- SOLUCIÓN: CREAR EL DATAFRAME AQUÍ ---
        df = pd.DataFrame(data_mix)
        df['Fecha_dt'] = pd.to_datetime(df['Fecha'], errors='coerce')

        # --- NUEVO: FILTRO DE FECHAS ---
        c_filt, _ = st.columns([1, 2])
        with c_filt:
            filtro_tiempo = st.selectbox("📅 Rango de historial:", ["Todo el historial", "Últimos 30 días", "Últimos 7 días"])
        
        # Aplicar filtro al DataFrame
        if filtro_tiempo == "Últimos 30 días":
            limite = pd.Timestamp(datetime.now()) - pd.Timedelta(days=30)
            df = df[df['Fecha_dt'] >= limite]
        elif filtro_tiempo == "Últimos 7 días":
            limite = pd.Timestamp(datetime.now()) - pd.Timedelta(days=7)
            df = df[df['Fecha_dt'] >= limite]

        if df.empty:
            st.warning("No hay movimientos registrados en el rango de tiempo seleccionado.")
        else:
            col_izq, col_der = st.columns([2, 1])

            with col_izq:
                st.markdown("#### Comportamiento de Pago")
                
                fig = go.Figure()
                
                df_abonos = df[df['Categoria'] == 'Ingreso']
                if not df_abonos.empty:
                    fig.add_trace(go.Bar(
                        x=df_abonos['Fecha_dt'], 
                        y=df_abonos['Monto'],
                        name='Abono Recibido',
                        marker_color='#4CAF50'
                    ))
                
                df_incidentes = df[df['Categoria'] == 'Incidencia']
                if not df_incidentes.empty:
                    y_val = df_abonos['Monto'].mean() if not df_abonos.empty else 100
                    fig.add_trace(go.Scatter(
                        x=df_incidentes['Fecha_dt'], 
                        y=[y_val]*len(df_incidentes),
                        mode='markers',
                        name='Visita Sin Pago',
                        marker=dict(color='#D32F2F', symbol='x', size=10)
                    ))

                fig.update_layout(
                    template="plotly_white",
                    height=350,
                    margin=dict(l=20, r=20, t=20, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_der:
                # --- NUEVO: GRÁFICO DE DONA ---
                st.markdown("#### Resumen de Saldo")
                fig_donut = go.Figure(data=[go.Pie(
                    labels=['Pagado', 'Pendiente'],
                    values=[total_pagado, max(0, saldo_actual)], # max(0) evita errores si se pagó de más
                    hole=.6,
                    marker_colors=['#4CAF50', '#E0E0E0'],
                    textinfo='none' # Mantenemos limpio el gráfico
                )])
                fig_donut.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=150,
                    showlegend=True,
                    annotations=[dict(text=f"{int(porcentaje_pagado*100)}%", x=0.5, y=0.5, font_size=20, showarrow=False)]
                )
                st.plotly_chart(fig_donut, use_container_width=True)

                # Tabla debajo de la dona
                st.markdown("#### Movimientos")
                df_display = df[['Fecha', 'Tipo', 'Monto']].copy()
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    height=180, # Altura ajustada para que quepa bien con la dona
                    hide_index=True,
                    column_config={
                        "Monto": st.column_config.NumberColumn(format="C$ %.2f")
                    }
                )

        # --- BOTÓN DESCARGA ---
        st.write("---")
        c_descarga, _ = st.columns([1, 2])
        with c_descarga:
            pdf_bytes = generar_pdf_estado_cuenta(
                {
                    'nombre': datos_cliente['nombre'], 
                    'cedula': datos_cliente['cedula'], 
                    'codigo_cliente': datos_cliente.get('codigo_cliente', 'S/C')
                },
                prestamo_sel,
                nombre_cobrador,
                df[['Fecha', 'Tipo', 'Cobrador', 'Monto']] if not df.empty else pd.DataFrame(columns=['Fecha', 'Tipo', 'Cobrador', 'Monto']),
                # 👇 AQUÍ ES DONDE AGREGAMOS LOS NUEVOS DATOS 👇
                {'pagado': total_pagado, 'saldo': saldo_actual, 'interes': intereses_totales, 'total_deuda': total_deuda}
            )
            
            cod_file = prestamo_sel.get('codigo_prestamo', prestamo_sel['fecha_inicio'])
            filename = f"EdoCta_{datos_cliente.get('codigo_cliente', 'SC')}_{cod_file}.pdf"
            
            st.download_button(
                label="📄 Descargar Estado de Cuenta PDF",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )

    else:
        st.info("No hay movimientos registrados para este préstamo aún.")