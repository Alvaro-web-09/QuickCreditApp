import streamlit as st

def configurar_pagina():
    """Configuración inicial obligatoria para todas las páginas."""
    st.set_page_config(
        page_title="CreceMás | Sistema Financiero",
        page_icon="🏦",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    # Inyectar CSS Global
    inyectar_css()

def inyectar_css():
    """CSS personalizado para transformar Streamlit en una Fintech App."""
    st.markdown("""
        <style>
        /* IMPORTAR FUENTE ROBOTO (Estándar financiero) */
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Roboto', sans-serif;
        }

        /* 1. HEADER LIMPIO */
        header {visibility: hidden;} /* Ocultar header default de Streamlit */
        
        .main-header {
            background-color: #F7F3E9;
            padding: 1rem 0;
            border-bottom: 2px solid #4CAF50;
            margin-bottom: 2rem;
        }
        
        .main-header h1 {
            color: #0F3D3E;
            font-weight: 700;
            font-size: 2rem;
            margin: 0;
        }
        
        .main-header p {
            color: #4CAF50;
            font-weight: 500;
            font-size: 1rem;
            margin: 0;
        }

        /* 2. TARJETAS (CARD UI) */
        .fintech-card {
            background-color: #FFFFFF; /* Fondo blanco para contraste limpio sobre crema */
            border: 1px solid #E6F4EA;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 12px rgba(15, 61, 62, 0.08); /* Sombra sutil azul petróleo */
            margin-bottom: 24px;
            transition: all 0.3s ease;
        }
        
        .fintech-card:hover {
            box-shadow: 0 6px 16px rgba(15, 61, 62, 0.12);
            transform: translateY(-2px);
        }

        /* 3. MÉTRICAS FINANCIERAS */
        .metric-container {
            text-align: center;
        }
        .metric-label {
            color: #6c757d;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }
        .metric-value {
            color: #0F3D3E;
            font-size: 1.8rem;
            font-weight: 700;
            margin: 0.5rem 0;
        }
        .metric-delta {
            font-size: 0.9rem;
            font-weight: 500;
        }
        .delta-pos { color: #4CAF50; }
        .delta-neg { color: #D32F2F; }

        /* 4. BOTONES PERSONALIZADOS */
        /* Primario (Verde) */
        div.stButton > button[kind="primary"] {
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #43A047;
            box-shadow: 0 4px 8px rgba(76, 175, 80, 0.4);
        }

        /* Secundario (Outline) */
        div.stButton > button[kind="secondary"] {
            background-color: transparent;
            color: #0F3D3E;
            border: 1px solid #0F3D3E;
            border-radius: 8px;
        }

        /* 5. TABLAS */
        [data-testid="stDataFrame"] {
            border: 1px solid #E6F4EA;
            border-radius: 8px;
            overflow: hidden;
        }
        
        /* 6. INPUTS */
        .stTextInput > div > div > input {
            background-color: #FFFFFF;
            border-radius: 8px;
            border: 1px solid #ced4da;
            color: #0F3D3E;
        }
        .stTextInput > div > div > input:focus {
            border-color: #4CAF50;
            box-shadow: 0 0 0 1px #4CAF50;
        }

        /* 7. ESTADOS (BADGES) */
        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .status-aprobada { background-color: #E6F4EA; color: #4CAF50; }
        .status-pendiente { background-color: #FFF3E0; color: #EF6C00; }
        .status-rechazada { background-color: #FFEBEE; color: #C62828; }
        
        </style>
    """, unsafe_allow_html=True)

def render_header(titulo, subtitulo=""):
    """Renderiza el encabezado corporativo estandarizado."""
    st.markdown(f"""
        <div class="main-header">
            <h1>CreceMás 🏦</h1>
            <p>{titulo} {' | ' + subtitulo if subtitulo else ''}</p>
        </div>
    """, unsafe_allow_html=True)

def card_inicio():
    """Abre un div para una tarjeta."""
    st.markdown('<div class="fintech-card">', unsafe_allow_html=True)

def card_fin():
    """Cierra el div de la tarjeta."""
    st.markdown('</div>', unsafe_allow_html=True)

def kpi_metric(label, value, delta=None, color="pos"):
    """Renderiza un KPI financiero personalizado."""
    delta_html = ""
    if delta:
        c = "delta-pos" if color == "pos" else "delta-neg"
        symbol = "↑" if color == "pos" else "↓"
        delta_html = f'<div class="metric-delta {c}">{symbol} {delta}</div>'
    
    st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {delta_html}
        </div>
    """, unsafe_allow_html=True)