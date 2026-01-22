import os
from flask import Flask, request
import requests
import time
from collections import defaultdict

app = Flask(__name__)

# --- CONFIGURACIÓN PERSONALIZADA ---
TOKEN = "8332101681:AAEbroUVbM_DkjhcuK-3onb095PpmFuCeyU"
CHAT_ID = "6120143616"

# Diccionario de nombres en clave (Logística)
WALLETS = {
    "4nE98eYJ4YySNFgz58NyyqwodxExEkbnnZYZmyPNPvu5": "OP_ALFA (Ballena)",
    "ESwdWuCTSRZnKRNXoyi1RP7ysuDkbDX3TQGWqxfjjKeN": "OP_PANDA (Sniper)",
    "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx": "OP_DELTA (Precisión)",
    "5d8tDay1ZDV4XVUBtTvFvQiLxDe8dz2ZCdsrkmTDcbm5": "OP_ZETA (Elite)",
    "5aLY85pyxiuX3fd4RgM3Yc1e3MAL6b7UgaZz6MS3JUfG": "OP_SIGMA (Inst.)"
}

tracker = defaultdict(list)
VENTANA_TIEMPO = 600  # 10 minutos (600 segundos)

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID, 
            "text": mensaje, 
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error de conexión: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return "Sin datos", 400

    for tx in data:
        # Detectar intercambio (Swap)
        if 'events' in tx and 'swap' in tx['events']:
            swap = tx['events']['swap']
            
            # Dirección del token y dirección de SOL
            token_ca = swap.get('tokenOutMint')
            sol_ca = "So11111111111111111111111111111111111111112"
            
            # Filtro: Solo compras (Entra SOL, sale Token)
            if swap.get('tokenInMint') == sol_ca:
                comprador_addr = tx.get('feePayer')
                nombre_wallet = WALLETS.get(comprador_addr, "OP_DESCONOCIDO")
                
                ahora = time.time()
                # Registrar movimiento
                tracker[token_ca].append({'wallet': nombre_wallet, 'time': ahora})
                
                # Limpiar historial antiguo del token
                tracker[token_ca] = [t for t in tracker[token_ca] if ahora - t['time'] < VENTANA_TIEMPO]
                
                # Obtener lista de operadores distintos en este token
                operadores_activos = list(set(t['wallet'] for t in tracker[token_ca]))