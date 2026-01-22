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
VENTANA_TIEMPO = 1800 # 30 minutos

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
    except: 
        pass

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        data = request.json
        if not data: return "OK", 200
        
        # Respuesta manual para confirmar que vive
        if isinstance(data, dict) and "message" in data:
            enviar_telegram("📡 *Radar Nivel 3 Activo.*\nFiltrando SOL/USDC. Analizando tokens nuevos.")
            return "OK", 200

        # Helius envía una lista de transacciones
        for tx in data:
            # 1. ¿Quién es el responsable?
            comprador = tx.get('feePayer')
            if comprador not in WALLETS:
                continue 
                
            nombre = WALLETS[comprador]
            
            # 2. Buscar transferencias de tokens HACIA el usuario (Compras)
            if 'tokenTransfers' in tx:
                for tf in tx['tokenTransfers']:
                    # Si el token va hacia nuestra wallet, es una adquisición
                    if tf.get('toUserAccount') == comprador:
                        token_ca = tf.get('mint')
                        
                        # --- FILTRO DE MONEDAS BASE (Para evitar spam de SOL) ---
                        # Ignoramos: SOL, Wrapped SOL, USDC y USDT
                        monedas_base = [
                            "So11111111111111111111111111111111111111112", 
                            "11111111111111111111111111111111",
                            "EPjFW36vn7J989kz5j1B1wvQ7bbjkneX9W8hzU31be52",
                            "Es9vMFrzaDCSTMdUiJcxKsM45fvBYgxQSJJqmohcvnJ"
                        ]
                        
                        if token_ca in monedas_base:
                            continue
                            
                        ahora = time.time()
                        tracker[token_ca].append({'wallet': nombre, 'time': ahora})
                        
                        # Limpiar registros antiguos de este token
                        tracker[token_ca] = [t for t in tracker[token_ca] if ahora - t['time'] < VENTANA_TIEMPO]
                        
                        ops = list(set(t['wallet'] for t in tracker[token_ca]))
                        
                        # Log para ver en Render qué está pasando
                        print(f"LECTURA: {nombre} compró {token_ca}. Equipo: {len(ops)}")

                        if len(ops) >= 2:
                            msg = (f"🚨 *CONFLUENCIA DETECTADA*\n\n"
                                   f"💎 *Token:* `{token_ca}`\n"
                                   f"👥 *Equipo:* {', '.join(ops)}\n"
                                   f"⏱️ *Ventana:* 30 min\n\n"
                                   f"🔗 [DexScreener](https://dexscreener.com/solana/{token_ca})")
                            enviar_telegram(msg)
                            
                            # Limpiamos para no repetir la alerta inmediatamente
                            tracker[token_ca] = [] 
        
        return "OK", 200
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
