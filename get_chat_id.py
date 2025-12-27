"""
Script para obtener tu Telegram Chat ID
Enviale cualquier mensaje a tu bot y luego ejecutá este script
"""
import requests
import os

# Leer token del .env
with open('backend/.env', 'r') as f:
    for line in f:
        if line.startswith('TELEGRAM_BOT_TOKEN='):
            BOT_TOKEN = line.split('=')[1].strip()
            break

print(f"🤖 Usando bot token: {BOT_TOKEN[:20]}...")

# Obtener updates del bot
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    
    if data['ok'] and data['result']:
        print("\n✅ Mensajes encontrados!\n")
        
        # Mostrar los últimos chats
        chat_ids = set()
        for update in data['result']:
            if 'message' in update:
                chat = update['message']['chat']
                chat_id = chat['id']
                username = chat.get('username', 'N/A')
                first_name = chat.get('first_name', 'N/A')
                
                chat_ids.add(chat_id)
                print(f"📱 Chat ID: {chat_id}")
                print(f"   Nombre: {first_name}")
                print(f"   Username: @{username}")
                print()
        
        if chat_ids:
            print(f"\n🎯 TU CHAT ID ES: {list(chat_ids)[0]}")
            print("\nCopiá ese número y pegalo en la app (🔔 Alerts → Telegram Chat ID)")
    else:
        print("⚠️ No hay mensajes todavía.")
        print("\n📲 IMPORTANTE:")
        print("1. Abrí Telegram")
        print("2. Buscá tu bot")
        print("3. Enviale CUALQUIER mensaje (ej: 'hola')")
        print("4. Volvé a ejecutar este script")
else:
    print(f"❌ Error: {response.status_code}")
    print("Verificá que el token esté bien configurado en backend/.env")
