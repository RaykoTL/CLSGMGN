import os
from flask import Flask, request
import requests
import time

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN = "8332101681:AAEbroUVbM_DkjhcuK-3onb095PpmFuCeyU"
CHAT_ID = "6120143616"

# Wallets a monitorear
WALLETS = {
    "3uuiw3YF1NCPYVc3FmCmg1DaBCPwQQVhzQYuz3PMXb9s": "ELITE PRINCIPAL (3uui)",
    "7xcyExghtNPWY4zzpgLXfgZsZ1CgW4DswuQipYn4b9ag": "ELITE SECUNDARIA (7xcy)"
}

# Lista negra de tokens de infraestructura y stables (Para limpiar el ruido)
BLACKLIST = [
    "So11111111111111111111111111111111111111112", # WSOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", # USDT
    "3NZ9J7Nkf6YDxU7W6dh4UTrUM3yW7jtJzQUeAJfFdgob", # WBTC
    "cbbtcf3aa214zXHbiAZQwf4122FBYbraNdFqgw4iMij", # WBTC variant
    "USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB", # USDS
    "AGFEByKWvUjB99mPr6is9E18vRk7Fv1WbtKnt7tAnYgy", # mSOL
    "juno7u2H36pYShmRNcYvV38D8N86Xb2pAsE8V9HkRrj"  # JitoSOL
]

# Diccionario para trackear el precio de entrada y balance
portafolios = {w: {} for w in WALLETS}

def obtener_datos_token(address):
    """Obtiene Market Cap y Precio de DexScreener"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        res = requests.get(url, timeout=3).json()
        pair = res.get('pairs', [])[0] if res.get('pairs') else None
        if pair:
            mcap = pair.get('fdv', 0)
            price = float(pair.get('priceUsd', 0))
            return mcap, price
    except:
        pass
    return 0, 0

def enviar_telegram(mensaje, token_ca=None):
    """Envía la alerta a Telegram con botones de análisis"""
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
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        data = request.get_json(silent=True)
        if not data or not isinstance(data, list):
            return "OK", 200

        for tx in data:
            # Identificar quién ejecuta la transacción
            ejecutor = tx.get('feePayer')
            if not ejecutor or ejecutor not in WALLETS:
                continue
            
            nombre_wallet = WALLETS[ejecutor]
            transfers = tx.get('tokenTransfers', [])

            for tf in transfers:
                token_ca = tf.get('mint')
                
                # Omitir si el token está en la lista negra (USDC, SOL, etc.)
                if not token_ca or token_ca in BLACKLIST:
                    continue
                
                cantidad = float(tf.get('tokenAmount', 0))
                if cantidad == 0:
                    continue

                # Obtener datos de mercado en tiempo real
                mcap, precio_actual = obtener_datos_token(token_ca)
                mcap_str = f"${mcap/1000000:.2f}M" if mcap > 1000000 else f"${mcap/1000:.1f}K"

                # --- LÓGICA DE COMPRA ---
                if tf.get('toUserAccount') == ejecutor:
                    # Guardar en memoria para calcular profit luego
                    if token_ca not in portafolios[ejecutor]:
                        portafolios[ejecutor][token_ca] = {'balance': 0.0, 'entrada': precio_actual}
                    
                    portafolios[ejecutor][token_ca]['balance'] += cantidad
                    
                    msg = (f"🟢 *COMPRA DETECTADA*\n"
                           f"👤 *Origen:* {nombre_wallet}\n"
                           f"💎 *Token:* `{token_ca}`\n"
                           f"💰 *MCap:* {mcap_str}\n"
                           f"💵 *Precio:* ${precio_actual:.10f}")
                    enviar_telegram(msg, token_ca)

                # --- LÓGICA DE VENTA ---
                elif tf.get('fromUserAccount') == ejecutor:
                    info = portafolios[ejecutor].get(token_ca, {'balance': 0.0, 'entrada': 0.0})
                    
                    # Calcular Profit si tenemos registro de la compra
                    if info['entrada'] > 0:
                        profit_pct = ((precio_actual - info['entrada']) / info['entrada']) * 100
                    else:
                        profit_pct = 0.0
                    
                    emoji_p = "🚀" if profit_pct > 0 else "📉"
                    
                    msg = (f"🔴 *VENTA DETECTADA*\n"
                           f"👤 *Origen:* {nombre_wallet}\n"
                           f"💎 *Token:* `{token_ca}`\n\n"
                           f"{emoji_p} *Profit:* {profit_pct:+.2f}%\n"
                           f"💰 *MCap Actual:* {mcap_str}")
                    enviar_telegram(msg, token_ca)
                    
                    # Si vende casi todo, limpiar memoria del token
                    if cantidad >= info['balance'] * 0.9:
                        portafolios[ejecutor].pop(token_ca, None)

        return "OK", 200
    
    return "Servidor Activo", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
