import os
from flask import Flask, request
import requests
import time
from collections import defaultdict

app = Flask(__name__)

# --- CONFIGURACIÓN ---
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
# Aumentamos a 1200 segundos (20 minutos) para no perder confluencias lentas
VENTANA_TIEMPO = 1200 

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        data = request.json
        if not data: return "OK", 200

        # Respuesta a mensajes manuales
        if "message" in data:
            enviar_telegram("✅ *Sistema Activo*\nVentana: 20 min.\nCarteras: 5")
            return "OK", 200

        for tx in data:
            if 'events' in tx and 'swap' in tx['events']:
                swap = tx['events']['swap']
                token_ca = swap.get('tokenOutMint')
                
                # Filtro: Solo compras con SOL
                if swap.get('tokenInMint') == "So11111111111111111111111111111111111111112":
                    comprador = tx.get('feePayer')
                    nombre = WALLETS.get(comprador, "OP_DESCONOCIDO")
                    ahora = time.time()

                    # GUARDAR Y LIMPIAR
                    tracker[token_ca].append({'wallet': nombre, 'time': ahora})
                    tracker[token_ca] = [t for t in tracker[token_ca] if ahora - t['time'] < VENTANA_TIEMPO]
                    
                    ops = list(set(t['wallet'] for t in tracker[token_ca]))
                    
                    # LOG PARA REVISIÓN (Aparecerá en Render)
                    print(f"DEBUG: {nombre} compró {token_ca}. Operadores actuales en token: {ops}")

                    if len(ops) >= 2:
                        msg = (f"📦 *REPORTE DE LOGÍSTICA: CONFLUENCIA*\n\n"
                               f"📂 *Token:* `{token_ca}`\n"
                               f"👷 *Equipo:* {', '.join(ops)}\n"
                               f"🔗 [DexScreener](https://dexscreener.com/solana/{token_ca})")
                        enviar_telegram(msg)
        return "OK", 200
    return "Servidor Activo", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
