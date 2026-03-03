import requests
import streamlit as st

# Carga manual (por si streamlit no lee los secretos aquí)
# OJO: REEMPLAZA ESTO CON TUS DATOS REALES SOLO PARA ESTA PRUEBA
TOKEN = "8318393313:AAEBwBLHOG_HAyI6PhCfhmgAB63Ytinsaww"
CHAT_ID = "8535378746"

def probar():
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "📢 Esta es una prueba de conexión directa."
    }
    
    print(f"📡 Intentando conectar a: {url}")
    print(f"👤 Enviando a ID: {CHAT_ID}")

    try:
        response = requests.post(url, json=payload)
        datos = response.json()
        
        if response.status_code == 200:
            print("\n✅ ¡ÉXITO! El mensaje debería haber llegado.")
        else:
            print("\n❌ ERROR DE TELEGRAM:")
            print(f"Código: {response.status_code}")
            print(f"Descripción: {datos.get('description')}")
            
    except Exception as e:
        print(f"\n❌ Error de conexión (Firewall/Internet): {e}")

if __name__ == "__main__":
    probar()