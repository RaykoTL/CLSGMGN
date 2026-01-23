import os
from flask import Flask, request
import requests
import time

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN = "8332101681:AAEbroUVbM_DkjhcuK-3onb095PpmFuCeyU"
CHAT_ID = "6120143616"

# Solo las dos billeteras confirmadas
WALLETS = {
    "3uuiw3YF1NCPYVc3FmCmg1DaBCPwQQVhzQYuz3PMXb9s": "ELITE PRINCIPAL (3uui)",
    "7xcyExghtNPWY4zzpgLXfgZsZ1CgW4DswuQipYn4b9ag": "ELITE SECUNDARIA (7xcy)"
}

# Diccionario para rastrear precios de entrada y gestionar alertas de venta
tokens_en_seguimiento = {} 
last_alert_time = {} 
last_sell_alert = {} 

SILENCIO_COMPRA = 300  # 5 minutos para evitar spam si compra en varias partes
SILENCIO_VENTA = 300 

def obtener_datos_token(address):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        res = requests.get(url, timeout=5).json()
        pair = res.get('pairs', [])[0] if res.get('pairs') else None
        if pair:
            mcap = pair.get('fdv', 0)
            liq = pair.get('liquidity', {}).get('usd', 0)
            price = float(pair.get('priceUsd', 0))
            return mcap, liq, price
    except: pass
    return 0, 0, 0

def enviar_telegram(mensaje, token_ca=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": mensaje, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    # Si es una compra, añadimos botones útiles
    if token_ca:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": "📊 GMGN", "url": f"https://gmgn.ai/sol/token/{token_ca}"},
                    {"text": "🎯 BullX", "url": f"https://neo.bullx.io/terminal?chain_id=137&address={token_ca}"}
                ]
            ]
        }
    
    requests.post(url, json=payload)

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        data = request.json
        ahora = time.time()

        for tx in data:
            ejecutor = tx.get('feePayer')
            if ejecutor not in WALLETS: continue
            nombre = WALLETS[ejecutor]

            if 'tokenTransfers' in tx:
                for tf in tx['tokenTransfers']:
                    token_ca = tf.get('mint')
                    # Filtrar SOL, USDC, etc.
                    if token_ca in ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"]: 
                        continue

                    # --- DETECTAR COMPRA ---
                    if tf.get('toUserAccount') == ejecutor:
                        id_compra = f"{token_ca}_{ejecutor}"
                        if id_compra in last_alert_time and ahora - last_alert_time[id_compra] < SILENCIO_COMPRA:
                            continue

                        mcap, liq, price = obtener_datos_token(token_ca)
                        tokens_en_seguimiento[token_ca] = price
                        last_alert_time[id_compra] = ahora
                        
                        mcap_str = f"${mcap/1000000:.2f}M" if mcap > 1000000 else f"${mcap/1000:.1f}K"
                        
                        msg = (f"🟢 *COMPRA DETECTADA*\n"
                               f"👤 *Origen:* {nombre}\n"
                               f"💎 *Token:* `{token_ca}`\n\n"
                               f"💰 *MCap:* {mcap_str} | 💧 *Liq:* ${liq:,.0f}")
                        enviar_telegram(msg, token_ca)

                    # --- DETECTAR VENTA ---
                    elif tf.get('fromUserAccount') == ejecutor:
                        id_venta = f"{token_ca}_{ejecutor}"
                        if id_venta in last_sell_alert and ahora - last_sell_alert[id_venta] < SILENCIO_VENTA:
                            continue

                        last_sell_alert[id_venta] = ahora
                        msg_v = (f"🔴 *VENTA DETECTADA*\n"
                                 f"👤 *Origen:* {nombre}\n"
                                 f"💎 *Token:* `{token_ca}`\n"
                                 f"⚠️ *Nota:* El operador está reduciendo posición.")
                        enviar_telegram(msg_v)
        
        return "OK", 200
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
