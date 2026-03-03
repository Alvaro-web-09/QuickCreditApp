import requests

# TUS DATOS (Ya corregidos)
TOKEN = "8318393313:AAEBwBLHOG_HAyI6PhCfhmgAB63Ytinsaww"
CHAT_ID = "8535378746" # <--- Aquí está la duda

def test_final():
    print("------------------------------------------------")
    print("📡 PROBANDO CONEXIÓN A TELEGRAM...")
    print(f"🔑 Token usado: ...{TOKEN[-10:]}")
    print(f"👤 Enviando a ID: {CHAT_ID}")
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "🔥 PRUEBA FINAL: Si lees esto, ¡ya funciona!"
    }
    
    try:
        response = requests.post(url, json=payload)
        respuesta_json = response.json()
        
        print(f"📨 Estado HTTP: {response.status_code}")
        
        if response.status_code == 200:
            print("\n✅ ¡ÉXITO TOTAL! El mensaje debe estar en tu celular.")
        else:
            print("\n❌ FALLÓ. Telegram respondió esto:")
            print(f"⚠️ Error: {respuesta_json.get('description')}")
            
            # AYUDA AUTOMÁTICA
            desc = respuesta_json.get('description', '')
            if "Chat not found" in desc:
                print("\n💡 SOLUCIÓN: El ID es incorrecto. Ese número no es tu chat.")
                print("   👉 Busca @userinfobot en Telegram y dale Start para ver tu ID real.")
            elif "bot was blocked" in desc or "user is deactivated" in desc:
                print("\n💡 SOLUCIÓN: No has iniciado el bot.")
                print("   👉 Busca tu bot en Telegram y dale al botón INICIAR (/start).")
                
    except Exception as e:
        print(f"\n❌ Error de conexión: {e}")

if __name__ == "__main__":
    test_final()