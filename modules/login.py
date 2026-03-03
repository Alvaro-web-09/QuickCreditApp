import streamlit as st
import time
from db_connection import get_db_client 

def mostrar_login():
    # Ya estamos dentro de la columna central de app.py
    # Solo dibujamos la "Tarjeta" del formulario
    
    with st.container(border=True):
        st.markdown("### Iniciar Sesión")
        st.caption("Ingresa tus credenciales para acceder.")
        
        # --- NUEVO: Usamos un formulario para habilitar el "Enter" ---
        with st.form("login_form", clear_on_submit=False):
            
            # Input de usuario
            username = st.text_input("Usuario", placeholder="Ej: chofer1")
            password = st.text_input("Contraseña", type="password", placeholder="••••••")
            
            st.write("") # Espacio visual
            
            # --- NUEVO: st.form_submit_button reacciona al "Enter" automáticamente ---
            ingresar = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
            
        # La validación se evalúa cuando se presiona el botón o se da "Enter"
        if ingresar:
            if not username or not password:
                st.warning("⚠️ Por favor llena todos los campos.")
            else:
                try:
                    with st.spinner("Conectando..."):
                        supabase = get_db_client()
                        
                        # Consulta a base de datos
                        response = supabase.table("usuarios").select("*").eq("username", username).execute()
                    
                    if len(response.data) > 0:
                        user_data = response.data[0]
                        
                        # Verificación de contraseña (compatible con password o codigo_empleado)
                        pass_db = user_data.get('password') or user_data.get('codigo_empleado')
                        
                        if str(pass_db) == str(password):
                            # --- ÉXITO ---
                            nombre_mostrar = user_data.get('nombre_completo') or user_data.get('username')
                            st.success(f"¡Bienvenido, {nombre_mostrar}!")
                            
                            # Actualizamos la Sesión Global
                            st.session_state['logged_in'] = True
                            st.session_state['user_id'] = user_data['id']
                            st.session_state['username'] = user_data.get('username')
                            st.session_state['role'] = user_data['rol']
                            
                            time.sleep(1)
                            st.rerun() # Recarga la página para ir al menú principal
                        else:
                            st.error("❌ Contraseña incorrecta.")
                    else:
                        st.error("❌ El usuario no existe.")
                        
                except Exception as e:
                    st.error(f"Error técnico: {e}")

    # Pie de página discreto (fuera de la tarjeta pero pegadito)
    st.markdown(
        "<div style='text-align: center; color: #999; font-size: 12px; margin-top: 10px;'>🔒 Sistema Seguro SSL</div>", 
        unsafe_allow_html=True
    )