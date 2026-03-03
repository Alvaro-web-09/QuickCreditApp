import streamlit as st
from supabase import create_client
import ssl

# --- ☢️ HACK PARA REDES CORPORATIVAS ☢️ ---
# Esto le dice a Python: "No verifiques el certificado SSL, solo conéctate".
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Si el Python es muy viejo y no tiene esa opción, no hacemos nada
    pass
else:
    # Reemplazamos el contexto seguro por uno "sin verificación"
    ssl._create_default_https_context = _create_unverified_https_context
# ---------------------------------------------

@st.cache_resource
def get_db_client():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        
        return create_client(url, key)
        
    except Exception as e:
        st.error("❌ Error de configuración: Revisa tu archivo .streamlit/secrets.toml")
        st.stop()