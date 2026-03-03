import streamlit as st
from db_connection import get_db_client
from datetime import datetime

def mostrar_agenda():
    # ==========================================
    # 0. ESTILOS CSS FINTECH (V7.2 - FIX DE INDENTACIÓN)
    # ==========================================
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --primary: #4CAF50;
            --primary-dark: #388E3C;
            --bg-main: #F7F3E9;
            --text-dark: #1F2937;
            --text-grey: #6B7280;
        }

        .stApp { background-color: var(--bg-main); font-family: 'Inter', sans-serif; }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px !important;
            border: 1px solid rgba(0,0,0,0.05) !important;
            background-color: white !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
            padding: 20px !important;
            margin-bottom: 20px !important;
        }

        .card-header { display: flex; align-items: center; gap: 16px; margin-bottom: 10px; }
        
        .avatar-circle {
            width: 48px; height: 48px;
            background: linear-gradient(135deg, #4CAF50 0%, #4CAF50 100%);
            color: white; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 18px;
            box-shadow: 0 3px 6px rgba(76, 175, 80, 0.2);
            flex-shrink: 0;
        }
        
        .info-main { flex-grow: 1; overflow: hidden; }
        .client-name { font-size: 17px; font-weight: 700; color: var(--text-dark); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .client-sub { font-size: 13px; color: var(--text-grey); margin-top: 2px; }

        .status-tag { padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; white-space: nowrap; }
        .tag-debt { background: #FEF2F2; color: #DC2626; border: 1px solid #FEE2E2; }
        .tag-clean { background: #ECFDF5; color: #059669; border: 1px solid #D1FAE5; }
        .tag-inactive { background: #F3F4F6; color: #6B7280; }

        div[data-testid="stExpander"] { 
            border: none !important; 
            box-shadow: none !important; 
            background: transparent !important;
            padding-bottom: 10px !important;
        }
        .streamlit-expanderHeader { 
            padding-left: 0 !important; 
            color: var(--primary) !important; 
            font-weight: 600;
            font-size: 14px;
            background-color: transparent !important;
        }
        div[data-testid="stExpanderDetails"] {
            border-top: 1px solid #F3F4F6;
            padding-top: 16px !important;
        }

        .detail-grid { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 12px;
            margin-bottom: 16px; 
        }
        .detail-full-width { grid-column: span 2; }
        .detail-item { display: flex; flex-direction: column; }
        .detail-label { font-size: 11px; text-transform: uppercase; color: #9CA3AF; font-weight: 600; margin-bottom: 2px; }
        .detail-value { font-size: 14px; color: var(--text-dark); font-weight: 500; }
        .detail-highlight { color: var(--primary); font-weight: 700; font-size: 15px; }

        .header-box { padding: 10px 0 30px 0; }
        .header-title { font-size: 28px; font-weight: 800; color: var(--text-dark); letter-spacing: -0.5px; }
        .header-sub { color: var(--text-grey); font-size: 15px; }
        </style>
    """, unsafe_allow_html=True)

    # 1. TÍTULO
    st.markdown("""
<div class="header-box">
<div class="header-title">📒 Cartera de Clientes</div>
<div class="header-sub">Gestión integral y expedientes detallados</div>
</div>
""", unsafe_allow_html=True)
    
    # 2. DATA
    supabase = get_db_client()
    user_id = st.session_state.get('user_id')
    
    if not user_id:
        st.error("⚠️ Sesión no iniciada.")
        return

    try:
        query_clientes = supabase.table("clientes").select("*").eq("creado_por", user_id)
        clientes = (query_clientes.execute()).data or []

        query_prestamos = supabase.table("prestamos").select("cliente_id, saldo_pendiente, monto_cuota")\
            .eq("cobrador_id", user_id).neq("estado", "pagado")
        prestamos_data = (query_prestamos.execute()).data or []
        
        mapa_deuda = {p['cliente_id']: {'saldo': p['saldo_pendiente'], 'cuota': p['monto_cuota']} for p in prestamos_data}

    except Exception as e:
        st.error(f"Error: {e}")
        return

    if not clientes:
        st.info("📭 Sin clientes.")
        return

    # 3. FILTROS
    c_search, c_filter = st.columns([0.65, 0.35])
    with c_search:
        busqueda = st.text_input("", placeholder="🔍 Buscar cliente...", label_visibility="collapsed")
    with c_filter:
         with st.expander("Filtros", expanded=False):
            filtro_deuda = st.radio("Mostrar:", ["Todos", "Con Deuda", "Sin Deuda"], index=0)

    st.write("") 

    # 4. LOGICA
    clientes_filtrados = []
    termino = busqueda.lower() if busqueda else ""

    for c in clientes:
        c_id = c['id']
        tiene_deuda = c_id in mapa_deuda
        if termino:
            raw_text = f"{c.get('nombre','')} {c.get('cedula','')} {c.get('direccion','')} {c.get('referencias','')}".lower()
            if termino not in raw_text: continue 
        if filtro_deuda == "Con Deuda" and not tiene_deuda: continue
        if filtro_deuda == "Sin Deuda" and tiene_deuda: continue
        clientes_filtrados.append(c)

    st.caption(f"Mostrando {len(clientes_filtrados)} clientes")

    # 5. RENDERIZADO
    for c in clientes_filtrados:
        c_id = c['id']
        nombre = c.get('nombre', 'Sin Nombre')
        cedula = c.get('cedula') or "No registrada"
        telefono = c.get('telefono')
        direccion = c.get('direccion') or "Managua"
        direccion_det = c.get('direccion_detalle') or "No especificado"
        referencias = c.get('referencias') or "---"
        estado_cartera = c.get('estado_cartera', 'activo').capitalize()
        es_fav = c.get('es_favorito', False)
        
        # --- NUEVAS VARIABLES DE EMERGENCIA ---
        contacto_emerg = c.get('contacto_emergencia') or "No especificado"
        telefono_emerg = c.get('telefono_emergencia') or "---"
        # --------------------------------------
        
        fecha_reg_fmt = "Reciente"
        if c.get('fecha_registro'):
            try: fecha_reg_fmt = c.get('fecha_registro').split("T")[0] 
            except: pass

        ultima_prestada = c.get('ultima_cantidad_prestada') or 0
        ultima_prestada_fmt = f"C$ {ultima_prestada:,.0f}" if ultima_prestada > 0 else "N/A"

        datos_prestamo = mapa_deuda.get(c_id, None)
        if datos_prestamo:
            deuda_total = datos_prestamo['saldo']
            badge_html = f"<div class='status-tag tag-debt'>Deuda: C$ {deuda_total:,.0f}</div>"
        else:
            badge_html = "<div class='status-tag tag-clean'>Solvente</div>"

        if estado_cartera.lower() == 'inactivo':
             badge_html = "<div class='status-tag tag-inactive'>Inactivo</div>"

        ini = (nombre.split()[0][0] + (nombre.split()[1][0] if len(nombre.split())>1 else "")).upper()
        fav_icon = "<span style='color:#FFC107; margin-left:4px;'>★</span>" if es_fav else ""

        # --- TARJETA ---
        with st.container(border=True):
            
            # A. HEADER HTML (SIN INDENTACIÓN)
            st.markdown(f"""
<div class="card-header">
<div class="avatar-circle">{ini}</div>
<div class="info-main">
<div class="client-name">{nombre} {fav_icon}</div>
<div class="client-sub">{cedula}</div>
</div>
{badge_html}
</div>
""", unsafe_allow_html=True)
            
            # B. EXPANDER (HTML SIN INDENTACIÓN)
            with st.expander("📂 Ver Expediente Completo", expanded=False):
                st.markdown(f"""
<div class="detail-grid">
<div class="detail-item"><div class="detail-label">Estado</div><div class="detail-value">{estado_cartera}</div></div>
<div class="detail-item"><div class="detail-label">Registro</div><div class="detail-value">{fecha_reg_fmt}</div></div>
<div class="detail-item detail-full-width">
<div class="detail-label">📍 Dirección</div>
<div class="detail-value">{direccion}</div>
</div>
<div class="detail-item detail-full-width">
<div class="detail-label">🏠 Detalle</div>
<div class="detail-value" style="font-style: italic; color: #555;">{direccion_det}</div>
</div>
<div class="detail-item detail-full-width">
<div class="detail-label">📝 Referencias</div>
<div class="detail-value">{referencias}</div>
</div>
<div class="detail-item"><div class="detail-label">💰 Último Préstamo</div><div class="detail-value detail-highlight">{ultima_prestada_fmt}</div></div>
<div class="detail-item"><div class="detail-label">📞 Teléfono</div><div class="detail-value">{telefono if telefono else "--"}</div></div>

<div class="detail-item detail-full-width" style="margin-top: 8px; padding-top: 8px; border-top: 1px dashed #E5E7EB;">
<div class="detail-label" style="color: #EF4444;">🚨 Contacto de Emergencia</div>
<div class="detail-value"><b>{contacto_emerg}</b> - 📞 {telefono_emerg}</div>
</div>
</div>
""", unsafe_allow_html=True)
            
            # C. BOTÓN DE ACCIÓN
            if telefono:
                tel_clean = ''.join(filter(str.isdigit, str(telefono)))
                if len(tel_clean) == 8: tel_clean = "505" + tel_clean
                
                st.link_button(
                    "💬 Enviar WhatsApp", 
                    f"https://wa.me/{tel_clean}", 
                    use_container_width=True
                )