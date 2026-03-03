import streamlit as st
import pandas as pd
import time
from db_connection import get_db_client
from datetime import datetime
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
# 1. GENERADOR DE PDF DEL CLIENTE (COLORES DE MARCA CORREGIDOS)
# ---------------------------------------------------------
def generar_reporte_cliente_pdf(cliente, prestamos, resumen_kpi, nombre_vendedor):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    # --- PALETA DE COLORES DE MARCA ---
    COLOR_NEGRO = colors.HexColor("#000000")   # Títulos y Encabezados Fuertes
    COLOR_VERDE = colors.HexColor("#4CAF50")   # Acentos y Dinero positivo
    COLOR_ROJO  = colors.HexColor("#C62828")   # Deudas / Riesgo
    COLOR_GRIS_CLARO = colors.HexColor("#EEEEEE") # Fondos suaves

    # --- ESTILOS DE TEXTO ---
    style_titulo = ParagraphStyle(
        name='TitleCorp', 
        parent=styles['Heading1'], 
        alignment=TA_CENTER, 
        fontSize=18, 
        textColor=COLOR_NEGRO, 
        spaceAfter=12
    )
    style_subtitulo = ParagraphStyle(
        name='SubTitle', 
        parent=styles['Heading2'], 
        fontSize=12, 
        textColor=COLOR_VERDE, 
        spaceAfter=6
    )
    style_normal = ParagraphStyle(name='NormalCorp', parent=styles['Normal'], fontSize=10, textColor=colors.black)

    # --- LOGO ---
    logo_file = "logo.png" 
    if not os.path.exists(logo_file):
        for ext in [".jpg", ".jpeg"]:
            if os.path.exists("logo"+ext):
                logo_file = "logo"+ext
                break
    
    if os.path.exists(logo_file):
        im = Image(logo_file, width=3.0*cm, height=3.0*cm, kind='proportional')
        story.append(im)
    
    story.append(Spacer(1, 10))

    # --- CONTENIDO ---
    story.append(Paragraph("EXPEDIENTE MAESTRO DE CLIENTE", style_titulo))
    story.append(Spacer(1, 15))

    # Sección 1: Datos Personales
    story.append(Paragraph("INFORMACIÓN PERSONAL", style_subtitulo))
    
    # NUEVO: Obtenemos el código del cliente
    codigo_cliente = cliente.get('codigo_cliente', 'Sin Asignar')
    nombre = cliente.get('nombre', 'N/A')
    cedula = cliente.get('cedula', 'N/A')
    telefono = cliente.get('telefono', 'N/A')
    direccion = cliente.get('direccion', 'No especificada')
    contacto_emergencia = cliente.get('contacto_emergencia', 'No especificado')
    telefono_emergencia = cliente.get('telefono_emergencia', 'N/A')

    data_info = [
        ["Código de Cliente:", codigo_cliente],
        ["Nombre Completo:", nombre],
        ["Cédula de Identidad:", cedula],
        ["Teléfono / Celular:", telefono],
        ["Dirección:", Paragraph(direccion, style_normal)],
        ["Contacto Emergencia:", contacto_emergencia],
        ["Tel. Emergencia:", telefono_emergencia],
        ["Vendedor Asignado:", nombre_vendedor]
    ]
    
    t_info = Table(data_info, colWidths=[140, 310])
    t_info.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,0), (-1,-1), COLOR_NEGRO),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), COLOR_GRIS_CLARO),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 20))

    # Sección 2: KPIs Financieros
    story.append(Paragraph("ESTADO DE CUENTA Y RIESGO", style_subtitulo))
    riesgo = resumen_kpi.get('riesgo_txt', 'N/A')
    saldo = resumen_kpi.get('saldo', 0.0)
    
    data_kpi = [["CLASIFICACIÓN", "DEUDA TOTAL ACTIVA"], [riesgo, f"C$ {saldo:,.2f}"]]
    t_kpi = Table(data_kpi, colWidths=[225, 225])
    
    estilo_kpi = [
        ('BACKGROUND', (0,0), (-1,0), COLOR_NEGRO),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('SIZE', (0,1), (-1,1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]
    
    if saldo > 0: 
        estilo_kpi.append(('TEXTCOLOR', (1,1), (1,1), COLOR_ROJO))
    else: 
        estilo_kpi.append(('TEXTCOLOR', (1,1), (1,1), COLOR_VERDE))
        
    t_kpi.setStyle(TableStyle(estilo_kpi))
    story.append(t_kpi)
    story.append(Spacer(1, 20))

    # Sección 3: Tabla Histórica
    story.append(Paragraph("HISTORIAL DE CRÉDITOS", style_subtitulo))
    if prestamos:
        # NUEVO: Agregamos CÓDIGO a los encabezados
        headers = ["CÓDIGO", "FECHA", "MONTO", "SALDO", "ESTADO", "PLAZO"]
        data_hist = [headers]
        
        for p in prestamos:
            row = [
                p.get('codigo_prestamo', '-'), # NUEVA COLUMNA
                p.get('fecha_inicio', '-'), 
                f"C$ {float(p.get('monto_prestado',0)):,.2f}", 
                f"C$ {float(p.get('saldo_pendiente',0)):,.2f}", 
                str(p.get('estado','')).upper(), 
                f"{p.get('plazo_dias',0)} días"
            ]
            data_hist.append(row)
            
        # Reajustamos los anchos de columna para que quepa el código
        t_hist = Table(data_hist, colWidths=[65, 70, 85, 85, 65, 80])
        t_hist.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_NEGRO),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (2,0), (3,-1), 'RIGHT'),
            ('ALIGN', (0,0), (1,-1), 'CENTER'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, COLOR_GRIS_CLARO]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,0), (-1,-1), 8), # Letra un poco más pequeña para que quepa bien
        ]))
        story.append(t_hist)
    else:
        story.append(Paragraph("Sin historial de créditos registrado.", style_normal))

    # Pie de página
    story.append(Spacer(1, 40))
    story.append(Paragraph(f"Documento generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ParagraphStyle(name='Footer', fontSize=8, textColor=colors.grey, alignment=TA_CENTER)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------
def clasificar_cliente(p_c):
    if not p_c: 
        return "NUEVO", "Nuevo Ingreso"
    
    mora = any(str(p['estado']).lower() == 'mora' for p in p_c)
    activos = [p for p in p_c if str(p['estado']).lower() == 'activo']
    pagados = [p for p in p_c if str(p['estado']).lower() == 'pagado' or str(p['estado']).lower() == 'finalizado']
    
    if mora: return "RIESGO", "Riesgo de Mora"
    if len(pagados) >= 3: return "VIP", "Cliente Preferente"
    if len(activos) > 0: return "REGULAR", "Cliente Activo"
    return "ESTABLE", "Cliente al Corriente"

# ---------------------------------------------------------
# VISTA PRINCIPAL (CRM)
# ---------------------------------------------------------
def mostrar_crm_clientes():
    st.markdown("## Panel de Gestión de Clientes")
    st.markdown("---")
    
    supabase = get_db_client()

    # --- CARGA DE DATOS ---
    with st.spinner("Cargando directorio de clientes..."):
        try:
            clientes = supabase.table("clientes").select("*").order("nombre").execute().data or []
            prestamos = supabase.table("prestamos").select("*").execute().data or []
            users_db = supabase.table("usuarios").select("id, nombre_completo, rol").execute().data or []
            
            # Mapas
            dict_drivers = {str(u['id']): u['nombre_completo'] for u in users_db}
            solo_drivers = [u for u in users_db if u['rol'] == 'driver' or u['rol'] == 'cobrador']
            dict_solo_drivers = {str(d['id']): d['nombre_completo'] for d in solo_drivers}
            
        except Exception as e:
            st.error(f"Error de conexión: {e}")
            return

    # --- 1. FILTROS (Contenedor Desplegable) ---
    with st.expander("⚙️ Filtros y Búsqueda", expanded=False):
        col_search, col_vend, col_status = st.columns([2, 1.5, 1])
        
        with col_search: 
            # NUEVO: Permitimos buscar por código
            busqueda = st.text_input("Buscar Cliente", placeholder="Código, Nombre o Cédula")
        
        with col_vend:
            nombres_vendedores = list(set(dict_drivers.values()))
            if "Admin / Sistema" not in nombres_vendedores: nombres_vendedores.append("Admin / Sistema")
            vend_sel = st.multiselect("Filtrar por Vendedor", options=nombres_vendedores, default=nombres_vendedores)
        
        with col_status:
            filtro_p = st.selectbox("Estado Financiero", ["Todos", "Solo con Saldo", "Sin Deuda"])

    # --- PROCESAMIENTO ---
    data_master = []
    termino_busqueda = busqueda.lower() if busqueda else None

    for c in clientes:
        p_c = [p for p in prestamos if str(p['cliente_id']) == str(c['id'])]
        saldo = sum(float(p['saldo_pendiente']) for p in p_c if str(p['estado']).lower() == 'activo')
        creado_por_id = str(c.get('creado_por')) if c.get('creado_por') else None
        nombre_v = dict_drivers.get(creado_por_id, "Admin / Sistema")
        r_id, r_txt = clasificar_cliente(p_c)
        codigo_c = c.get('codigo_cliente', '--') # Obtenemos el código

        # Filtros
        coincide_texto = False
        if termino_busqueda:
            # NUEVO: Añadimos el código del cliente al string de búsqueda
            texto_cliente = (str(codigo_c) + " " + str(c['nombre']) + " " + str(c.get('cedula',''))).lower()
            if termino_busqueda in texto_cliente: coincide_texto = True
        
        coincide_vendedor = nombre_v in vend_sel

        if termino_busqueda and not coincide_texto: continue
        if not termino_busqueda and not coincide_vendedor: continue
        if filtro_p == "Solo con Saldo" and saldo <= 0: continue
        if filtro_p == "Sin Deuda" and saldo > 0: continue

        data_master.append({
            "Código": codigo_c, # NUEVA COLUMNA
            "Nombre": c['nombre'], 
            "Cédula": c.get('cedula', 'N/A'),
            "Vendedor": nombre_v, 
            "Saldo": saldo, 
            "Clasificación": r_txt,
            "ID": c['id'] # Oculto en la tabla, se usa para lógica
        })

    # Tabla Principal
    if data_master:
        st.dataframe(
            pd.DataFrame(data_master), use_container_width=True, hide_index=True,
            # NUEVO: Incluimos el Código al inicio del orden de columnas
            column_order=("Código", "Nombre", "Cédula", "Vendedor", "Saldo", "Clasificación"),
            column_config={"Saldo": st.column_config.NumberColumn(format="C$ %.2f")}
        )
    else:
        st.info("No se encontraron registros.")

    st.divider()

    # --- 2. GESTIÓN INDIVIDUAL ---
    st.markdown("### Gestión de Expediente Individual")
    
    # NUEVO: El desplegable ahora muestra el código para ubicar rápido al cliente
    opciones_select = {d['ID']: f"{d['Código']} | {d['Nombre']} | {d['Cédula']}" for d in data_master}
    id_sel = st.selectbox("Seleccionar Cliente:", options=[None] + list(opciones_select.keys()), format_func=lambda x: opciones_select.get(x, "Seleccione..."))

    if id_sel:
        c_sel = next(c for c in clientes if c['id'] == id_sel)
        p_sel = [p for p in prestamos if str(p['cliente_id']) == str(id_sel)]
        r_id, r_txt = clasificar_cliente(p_sel)
        saldo_s = sum(float(p['saldo_pendiente']) for p in p_sel if str(p['estado']).lower() == 'activo')
        id_v = str(c_sel.get('creado_por')) if c_sel.get('creado_por') else None
        nom_v_sel = dict_drivers.get(id_v, "Admin / Sistema")

        col_pdf, col_id = st.columns([1, 3])
        with col_pdf:
            pdf_bytes = generar_reporte_cliente_pdf(c_sel, p_sel, {"riesgo_txt": r_txt, "saldo": saldo_s}, nom_v_sel)
            st.download_button("Descargar Expediente PDF", data=pdf_bytes, file_name=f"Expediente_{c_sel.get('codigo_cliente', 'SinCodigo')}_{c_sel['nombre']}.pdf", mime="application/pdf", type="primary", use_container_width=True)
        with col_id:
            st.caption(f"ID Base de Datos: {c_sel['id']} | Registro: {c_sel.get('created_at', 'N/A')[:10]}")

        t1, t2, t3, t4 = st.tabs(["Información Financiera", "Editar Datos", "Reasignación", "Notas"])
        
        with t1:
            m1, m2, m3 = st.columns(3)
            m1.metric("Estatus", r_txt)
            m2.metric("Deuda Total", f"C$ {saldo_s:,.2f}")
            m3.metric("Créditos", len(p_sel))
            
            st.markdown("#### Detalle de Préstamos")
            if p_sel:
                df_p = pd.DataFrame(p_sel)
                # NUEVO: Añadimos 'codigo_prestamo' a las columnas que se muestran
                cols_p = [c for c in ['codigo_prestamo', 'fecha_inicio', 'monto_prestado', 'saldo_pendiente', 'estado', 'plazo_dias'] if c in df_p.columns]
                st.dataframe(df_p[cols_p], use_container_width=True, hide_index=True, column_config={
                    "codigo_prestamo": "Código", # Renombramos la columna visualmente
                    "monto_prestado": st.column_config.NumberColumn("Monto", format="C$ %.2f"),
                    "saldo_pendiente": st.column_config.NumberColumn("Saldo", format="C$ %.2f")
                })
            else:
                st.info("Sin historial.")

        with t2:
            st.markdown("#### Editar Datos del Cliente")
            with st.form("form_edit"):
                c1, c2 = st.columns(2)
                # Columna 1
                n_nom = c1.text_input("Nombre Completo", c_sel['nombre'])
                n_ced = c1.text_input("Cédula", c_sel.get('cedula', ''))
                n_tel = c1.text_input("Teléfono Personal", c_sel.get('telefono', ''))
                
                # Columna 2
                n_dir = c2.text_input("Dirección", c_sel.get('direccion', ''))
                n_contacto_emerg = c2.text_input("Contacto de Emergencia (Nombre)", c_sel.get('contacto_emergencia', ''))
                n_tel_emerg = c2.text_input("Teléfono de Emergencia", c_sel.get('telefono_emergencia', ''))
                
                if st.form_submit_button("Guardar Cambios", type="primary"):
                    supabase.table("clientes").update({
                        "nombre": n_nom, 
                        "cedula": n_ced, 
                        "direccion": n_dir, 
                        "telefono": n_tel,
                        "contacto_emergencia": n_contacto_emerg,
                        "telefono_emergencia": n_tel_emerg
                    }).eq("id", id_sel).execute()
                    st.rerun()

        with t3:
            st.warning(f"Vendedor Actual: {nom_v_sel}")
            nv = st.selectbox("Nuevo Responsable", list(dict_solo_drivers.values()), index=None)
            if nv and st.button("Reasignar"):
                nid = next(k for k, v in dict_solo_drivers.items() if v == nv)
                supabase.table("clientes").update({"creado_por": nid}).eq("id", id_sel).execute()
                st.rerun()

        with t4:
            st.markdown("#### Historial de Notas")
            
            # 1. Mostrar historial actual (con contenedor de scroll para que no se haga infinito)
            notas_actuales = c_sel.get('notas_admin', '') or ""
            
            with st.container(height=300, border=True): 
                if notas_actuales.strip():
                    st.markdown(notas_actuales)
                else:
                    st.info("No hay notas registradas para este cliente aún.")
            
            st.divider()
            
            # 2. Área para agregar una nueva nota
            nueva_nota = st.text_area("Escribir nueva nota", placeholder="Ej: El cliente prometió pagar mañana al mediodía...", height=100)
            
            if st.button("➕ Agregar Nota", type="primary"):
                if nueva_nota.strip():
                    # Generamos la fecha y hora actual
                    fecha_str = datetime.now().strftime("%d/%m/%Y %I:%M %p")
                    
                    # Formateamos cómo se verá visualmente esta nueva entrada
                    bloque_nueva_nota = f"**🗓️ {fecha_str} | 👤 {nom_v_sel}**\n> {nueva_nota.strip()}\n\n---\n\n"
                    
                    # Apilamos la nota nueva ARRIBA de las notas viejas
                    notas_actualizadas = bloque_nueva_nota + notas_actuales
                    
                    # Guardamos en la base de datos
                    supabase.table("clientes").update({"notas_admin": notas_actualizadas}).eq("id", id_sel).execute()
                    
                    st.toast("✅ Nota guardada con éxito")
                    time.sleep(1) # Pequeña pausa para que se vea el mensaje
                    st.rerun() # Recargamos para limpiar el input y mostrar la nota arriba
                else:
                    st.warning("Por favor, escribe algo antes de guardar.")