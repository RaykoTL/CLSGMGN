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
last_alert_time = {} 
VENTANA_TIEMPO = 1800 
SILENCIO_POST_ALERTA = 900 

def obtener_datos_token(address):
    """Obtiene Market Cap y edad del token vía DexScreener"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        res = requests.get(url, timeout=5).json()
        pair = res.get('pairs', [])[0] if res.get('pairs') else None
        if pair:
            mcap = pair.get('fdv', 0)
            created_at = pair.get('pairCreatedAt', 0)
            # Calcular edad en minutos
            edad_min = int((time.time() * 1000 - created_at) / 60000) if created_at else 0
            
            # Formatear MCAP
            if mcap >= 1000000:
                mcap_str = f"${mcap/1000000:.2f}M"
            else:
                mcap_str = f"${mcap/1000:.1f}K"
                
            return mcap_str, edad_min
    except:
        pass
    return "Desconocido", "Desconocida"

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown", "disable_web_page_preview": True})
    except: pass

def obtener_rango(ops):
    nombres = " ".join(ops)
    if len(ops) >= 3:
        return "💎 *DIAMOND CALL* 💎\n🔥 Probabilidad de éxito altísima. 3+ Operadores Élite."
    if "OP_ZETA" in nombres and "OP_ALFA" in nombres:
        return "🎖️ *SÚPER ÉLITE (TRIPLE A)*\nEntrada institucional/ballena pesada."
    if "OP_ZETA" in nombres and "OP_DELTA" in nombres:
        return "🎯 *PRECISIÓN TÉCNICA*\nBuenos fundamentales o gráfica limpia."
    if "OP_DELTA" in nombres and "OP_SIGMA" in nombres:
        return "🕵️ *SMART MONEY EARLY*\nEntrada de bajo perfil. Posible gema temprana."
    return "📈 *CONFLUENCIA ESTÁNDAR*\nSeguimiento de flujo activo."

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        data = request.json
        if not data: return "OK", 200
        
        for tx in data:
            comprador = tx.get('feePayer')
            if comprador not in WALLETS: continue
            nombre = WALLETS[comprador]
            ahora = time.time()

            if 'tokenTransfers' in tx:
                for tf in tx['tokenTransfers']:
                    token_ca = tf.get('mint')
                    black_list = ["So11111111111111111111111111111111111111112", "11111111111111111111111111111111", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", "USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB"]
                    if token_ca in black_list: continue

                    # --- DETECTAR COMPRA ---
                    if tf.get('toUserAccount') == comprador:
                        if token_ca in last_alert_time and ahora - last_alert_time[token_ca] < SILENCIO_POST_ALERTA:
                            continue

                        tracker[token_ca].append({'wallet': nombre, 'time': ahora})
                        tracker[token_ca] = [t for t in tracker[token_ca] if ahora - t['time'] < VENTANA_TIEMPO]
                        ops = list(set(t['wallet'] for t in tracker[token_ca]))

                        if len(ops) >= 2:
                            last_alert_time[token_ca] = ahora
                            rango = obtener_rango(ops)
                            mcap, edad = obtener_datos_token(token_ca)
                            
                            msg = (f"{rango}\n\n"
                                   f"💎 *Token:* `{token_ca}`\n"
                                   f"👥 *Equipo:* {', '.join(ops)}\n"
                                   f"💰 *Mkt Cap:* {mcap}\n"
                                   f"⏳ *Edad:* {edad} min\n\n"
                                   f"🛡️ *Seguridad:* [RugCheck](https://rugcheck.xyz/tokens/{token_ca})\n"
                                   f"📊 *Gráfica:* [DexScreener](https://dexscreener.com/solana/{token_ca})")
                            enviar_telegram(msg)
                            tracker[token_ca] = [] 

                    # --- DETECTAR VENTA ---
                    if tf.get('fromUserAccount') == comprador:
                        msg = (f"⚠️ *AVISO DE SALIDA / VENTA*\n\n"
                               f"👤 *Operador:* {nombre}\n"
                               f"💎 *Token:* `{token_ca}`\n"
                               f"📉 Reduciendo posición.\n\n"
                               f"🔗 [DexScreener](https://dexscreener.com/solana/{token_ca})")
                        enviar_telegram(msg)
        
        return "OK", 200
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
