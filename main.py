import os
from flask import Flask, request
import requests
import time
from collections import defaultdict

app = Flask(__name__)

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
VENTANA_TIEMPO = 1800 # Subimos a 30 minutos para mayor seguridad

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown", "disable_web_page_preview": False})
    except: pass

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        data = request.json
        if not data: return "OK", 200
        
        # Respuesta manual
        if "message" in data:
            enviar_telegram("📡 *Radar Reforzado:* Activo y rastreando.")
            return "OK", 200

        for tx in data:
            # 1. Identificar si alguno de nuestros operadores está en la transacción
            account_keys = [acc.get('pubkey') for acc in tx.get('accountData', [])]
            operador_encontrado = None
            for w_addr, w_nombre in WALLETS.items():
                if w_addr in account_keys or tx.get('feePayer') == w_addr:
                    operador_encontrado = w_nombre
                    break
            
            if operador_encontrado:
                # 2. Buscar qué token salió de la cuenta (Compra)
                token_ca = None
                if 'tokenTransfers' in tx:
                    for transfer in tx['tokenTransfers']:
                        # Si el operador es el que RECIBE el token, es una compra
                        if transfer.get('toUserAccount') in account_keys or transfer.get('toUserAccount') == tx.get('feePayer'):
                            token_ca = transfer.get('mint')
                            break
                
                if token_ca:
                    ahora = time.time()
                    tracker[token_ca].append({'wallet': operador_encontrado, 'time': ahora})
                    tracker[token_ca] = [t for t in tracker[token_ca] if ahora - t['time'] < VENTANA_TIEMPO]
                    
                    ops = list(set(t['wallet'] for t in tracker[token_ca]))
                    print(f"LECTURA: {operador_encontrado} operó con {token_ca}. Equipo en token: {ops}")

                    if len(ops) >= 2:
                        msg = (f"🚨 *CONFLUENCIA DETECTADA*\n\n"
                               f"💎 *Token:* `{token_ca}`\n"
                               f"👥 *Equipo:* {', '.join(ops)}\n"
                               f"🔗 [DexScreener](https://dexscreener.com/solana/{token_ca})")
                        enviar_telegram(msg)
        
        return "OK", 200
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
