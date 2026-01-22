import os
from flask import Flask, request
import requests
import time
from collections import defaultdict

app = Flask(__name__)

# --- CONFIGURACIÓN PERSONALIZADA ---
TOKEN = "8332101681:AAEbroUVbM_DkjhcuK-3onb095PpmFuCeyU"
CHAT_ID = "6120143616"

WALLETS = {
    "4nE98eYJ4YySNFgz58NyyqwodxExEkbnnZYZmyPNPvu5": "OP_ALFA (Ballena)",
    "ESwdWuCTSRZnKRNXoyi1RP7ysuDkbDX3TQGWqxfjjKeN": "OP_PANDA (Sniper)",
    "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx": "OP_DELTA (Precisión)",
    "5d8tDay1ZDV4XVUBtTvFvQiLxDe8dz2ZCdsrkmTDcbm5": "OP_ZETA (Elite)",
    "5aLY85pyxiuX3fd4RgM3Yc1e3MAL6b7UgaZz6MS3JUfG": "OP_SIGMA (Inst.)"
}

tracker = defaultdict(list)
VENTANA_TIEMPO = 600

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error: {e}")

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    # --- PARTE NUEVA: RESPUESTA A TUS MENSAJES ---
    if request.method == 'POST':
        data = request.json
        if not data:
            return "OK", 200

        # Si el mensaje viene de Telegram (cuando tú le escribes)
        if "message" in data:
            user_text = data["message"].get("text", "")
            enviar_telegram(f"✅ *Sistema de Logística Operativo*\n\nEstoy vigilando {len(WALLETS)} carteras. Te avisaré cuando haya duplicados.")
            return "OK", 200

        # Si el mensaje viene de Helius (datos de la blockchain)
        for tx in data:
            if 'events' in tx and 'swap' in tx['events']:
                swap = tx['events']['swap']
                token_ca = swap.get('tokenOutMint')
                if swap.get('tokenInMint') == "So11111111111111111111111111111111111111112":
                    comprador_addr = tx.get('feePayer')
                    nombre_wallet = WALLETS.get(comprador_addr, "OP_DESCONOCIDO")
                    ahora = time.time()
                    tracker[token_ca].append({'wallet': nombre_wallet, 'time': ahora})
                    tracker[token_ca] = [t for t in tracker[token_ca] if ahora - t['time'] < VENTANA_TIEMPO]
                    operadores_activos = list(set(t['wallet'] for t in tracker[token_ca]))
                    
                    if len(operadores_activos) >= 2:
                        msg = (f"📦 *REPORTE DE LOGÍSTICA: PEDIDO DUPLICADO*\n\n"
                               f"📂 *ID Lote:* `{token_ca}`\n"
                               f"👷 *Personal:* {', '.join(operadores_activos)}\n"
                               f"🔗 [Abrir Albarán](https://dexscreener.com/solana/{token_ca})")
                        enviar_telegram(msg)
        return "OK", 200
    return "Servidor Activo", 200

@app.route('/')
def health_check():
    return "Servidor Logística Activo", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
