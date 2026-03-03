import requests
import streamlit as st

def enviar_alerta_telegram(mensaje, url_boton=None):
    """
    Envía mensaje a Telegram. 
    Si recibe 'url_boton', agrega un botón debajo del texto.
    """
    try:
        # 1. Cargar credenciales
        token = st.secrets["telegram"]["token"]
        chat_id = st.secrets["telegram"]["chat_id"]
        
        # 2. Configurar URL
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        # 3. Preparar datos básicos
        payload = {
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "Markdown" # Ojo con los caracteres especiales
        }

        # 4. AGREGAR BOTÓN (Si nos dieron un link)
        if url_boton:
            teclado = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 Ir a Aprobar", "url": url_boton}
                    ]
                ]
            }
            payload["reply_markup"] = teclado

        # 5. Enviar
        response = requests.post(url, json=payload)
        
        # Diagnóstico en terminal (para que veas si Telegram rechaza)
        if response.status_code != 200:
            print(f"❌ Error Telegram API: {response.text}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error Python Telegram: {e}")
        return False