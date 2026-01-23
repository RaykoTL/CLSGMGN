import os
from flask import Flask, request
import requests
import time

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN = "8332101681:AAEbroUVbM_DkjhcuK-3onb095PpmFuCeyU"
CHAT_ID = "6120143616"

WALLETS = {
    "3uuiw3YF1NCPYVc3FmCmg1DaBCPwQQVhzQYuz3PMXb9s": "ELITE PRINCIPAL (3uui)",
    "7xcyExghtNPWY4zzpgLXfgZsZ1CgW4DswuQipYn4b9ag": "ELITE SECUNDARIA (7xcy)"
}

# Estructura: { wallet_address: { token_ca: { 'balance': float, 'precio_promedio': float } } }
portafolios = {w: {} for w in WALLETS}

last_alert_time = {} 
last_sell_alert = {} 

SILENCIO_COMPRA = 600  
SILENCIO_VENTA = 60   # Bajamos el silencio de venta para ver cierres parciales rápidos

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
    
    if token_ca:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "📊 GMGN", "url": f"https://gmgn.ai/sol/token/{token_ca}"},
                {"text": "🎯 BullX", "url": f"https://neo.bullx.io/terminal?chain_id=137&address={token_ca}"}
            ]]
        }
    
    try: requests.post(url, json=payload, timeout=5)
    except: pass

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        try:
            data = request.get_json(silent=True)
            if not data or not isinstance(data, list): return "OK", 200

            ahora = time.time()

            for tx in data:
                if not isinstance(tx, dict): continue
                ejecutor = tx.get('feePayer')
                if not ejecutor or ejecutor not in WALLETS: continue
                
                nombre = WALLETS[ejecutor]

                if 'tokenTransfers' in tx and isinstance(tx['tokenTransfers'], list):
                    for tf in tx['tokenTransfers']:
                        if not isinstance(tf, dict): continue
                        
                        token_ca = tf.get('mint')
                        if not token_ca or token_ca in ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"]: 
                            continue

                        cantidad = float(tf.get('tokenAmount', 0))
                        if cantidad == 0: continue

                        # --- LÓGICA DE COMPRA ---
                        if tf.get('toUserAccount') == ejecutor:
                            mcap, liq, price = obtener_datos_token(token_ca)
                            
                            # Actualizar portafolio interno
                            if token_ca not in portafolios[ejecutor]:
                                portafolios[ejecutor][token_ca] = {'balance': 0.0, 'precio_entrada': price}
                            
                            portafolios[ejecutor][token_ca]['balance'] += cantidad
                            
                            id_compra = f"{token_ca}_{ejecutor}"
                            if id_compra in last_alert_time and ahora - last_alert_time[id_compra] < SILENCIO_COMPRA:
                                continue

                            last_alert_time[id_compra] = ahora
                            mcap_str = f"${mcap/1000000:.2f}M" if mcap > 1000000 else f"${mcap/1000:.1f}K"
                            
                            msg = (f"🟢 *COMPRA DETECTADA*\n"
                                   f"👤 *Origen:* {nombre}\n"
                                   f"💎 *Token:* `{token_ca}`\n"
                                   f"💰 *MCap:* {mcap_str} | 💧 *Liq:* ${liq:,.0f}\n"
                                   f"💵 *Precio:* ${price:.10f}")
                            enviar_telegram(msg, token_ca)

                        # --- LÓGICA DE VENTA + PORCENTAJE + PROFIT ---
                        elif tf.get('fromUserAccount') == ejecutor:
                            id_venta = f"{token_ca}_{ejecutor}"
                            if id_venta in last_sell_alert and ahora - last_sell_alert[id_venta] < SILENCIO_VENTA:
                                continue

                            mcap, liq, precio_actual = obtener_datos_token(token_ca)
                            
                            # Calcular % de la bolsa vendida
                            info = portafolios[ejecutor].get(token_ca, {'balance': 0, 'precio_entrada': 0})
                            total_antes = info['balance']
                            
                            porcentaje_vendido = 0
                            if total_antes > 0:
                                porcentaje_vendido = (cantidad / total_antes) * 100
                                portafolios[ejecutor][token_ca]['balance'] -= cantidad
                            
                            # Calcular Profit %
                            profit_pct = 0
                            if info['precio_entrada'] > 0:
                                profit_pct = ((precio_actual - info['precio_entrada']) / info['precio_entrada']) * 100

                            emoji_profit = "🚀" if profit_pct > 0 else "📉"
                            
                            last_sell_alert[id_venta] = ahora
                            msg_v = (f"🔴 *VENTA DETECTADA*\n"
                                     f"👤 *Origen:* {nombre}\n"
                                     f"💎 *Token:* `{token_ca}`\n\n"
                                     f"📊 *Porcentaje Vendido:* {porcentaje_vendido:.1f}%\n"
                                     f"{emoji_profit} *Profit Actual:* {profit_pct:+.2f}%\n"
                                     f"⚠️ *Nota:* Está reduciendo posición.")
                            enviar_telegram(msg_v, token_ca)
                            
                            # Si vendió más del 95%, limpiar token del portafolio
                            if porcentaje_vendido > 95:
                                portafolios[ejecutor].pop(token_ca, None)

        except Exception as e: print(f"Error: {e}")
        return "OK", 200
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
