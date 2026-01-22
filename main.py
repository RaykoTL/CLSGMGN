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
tokens_en_seguimiento = set() 
last_alert_time = {} 
# NUEVO: Para evitar el spam de ventas repetidas
last_sell_alert = {} 

VENTANA_TIEMPO = 1800 
SILENCIO_POST_ALERTA = 900 
SILENCIO_VENTA = 600 # 10 minutos de silencio tras avisar una venta del mismo OP

def obtener_datos_token(address):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        res = requests.get(url, timeout=5).json()
        pair = res.get('pairs', [])[0] if res.get('pairs') else None
        if pair:
            mcap = pair.get('fdv', 0)
            liq = pair.get('liquidity', {}).get('usd', 0)
            created_at = pair.get('pairCreatedAt', 0)
            edad_min = int((time.time() * 1000 - created_at) / 60000) if created_at else 0
            return mcap, edad_min, liq
    except: pass
    return 0, 0, 0

def calcular_prioridad(mcap, edad, ops_count, liq):
    if mcap > 100_000_000 or mcap == 0 or liq == 0: return 0, ""
    puntos = 0
    ratio_liq = mcap / liq

    if ratio_liq > 5.5: return 1, "FILTRADO (LIQ FRÁGIL)"
    if mcap > 1_000_000: puntos -= 30
    elif mcap < 300_000: puntos += 30 
    if edad < 60: puntos += 40
    elif edad < 1440: puntos += 20
    puntos += (ops_count * 15)

    if puntos >= 85: return 5, "⭐⭐⭐⭐⭐ (GEMA ALPHA)"
    if puntos >= 65: return 4, "⭐⭐⭐⭐ (POTENCIAL ALTO)"
    return 1, "FILTRADO"

def enviar_telegram_con_botones(mensaje, token_ca):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "🔔 Seguir Salidas", "callback_data": f"track_{token_ca}"},
                    {"text": "📊 GMGN", "url": f"https://gmgn.ai/sol/token/{token_ca}"}
                ],
                [{"text": "❌ Ignorar", "callback_data": "ignore"}]
            ]
        }
    }
    requests.post(url, json=payload)

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        data = request.json

        if 'callback_query' in data:
            callback = data['callback_query']
            choice = callback['data']
            if choice.startswith("track_"):
                ca = choice.split("_")[1]
                tokens_en_seguimiento.add(ca)
                enviar_telegram(f"✅ *Seguimiento activado* para `{ca}`.")
            return "OK", 200

        for tx in data:
            comprador = tx.get('feePayer')
            if comprador not in WALLETS: continue
            nombre = WALLETS[comprador]
            ahora = time.time()

            if 'tokenTransfers' in tx:
                for tf in tx['tokenTransfers']:
                    token_ca = tf.get('mint')
                    
                    if token_ca in ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "11111111111111111111111111111111"]: 
                        continue

                    # --- LÓGICA DE COMPRA ---
                    if tf.get('toUserAccount') == comprador:
                        if token_ca in last_alert_time and ahora - last_alert_time[token_ca] < SILENCIO_POST_ALERTA: continue
                        tracker[token_ca].append({'wallet': nombre, 'time': ahora})
                        tracker[token_ca] = [t for t in tracker[token_ca] if ahora - t['time'] < VENTANA_TIEMPO]
                        ops = list(set(t['wallet'] for t in tracker[token_ca]))

                        if len(ops) >= 2:
                            mcap, edad, liq = obtener_datos_token(token_ca)
                            estrellas, etiqueta = calcular_prioridad(mcap, edad, len(ops), liq)
                            
                            if estrellas >= 4: 
                                last_alert_time[token_ca] = ahora
                                mcap_str = f"${mcap/1000000:.2f}M" if mcap > 1000000 else f"${mcap/1000:.1f}K"
                                msg = (f"{etiqueta}\n━━━━━━━━━━━━━━━\n"
                                       f"💎 *Token:* `{token_ca}`\n"
                                       f"👥 *Equipo:* {', '.join(ops)}\n\n"
                                       f"💰 *MCap:* {mcap_str} | 💧 *Liq:* ${liq:,.0f}\n"
                                       f"⏳ *Edad:* {edad} min")
                                enviar_telegram_con_botones(msg, token_ca)
                                tracker[token_ca] = [] 

                    # --- LÓGICA DE VENTA (CON ANTI-SPAM) ---
                    if tf.get('fromUserAccount') == comprador:
                        if token_ca in tokens_en_seguimiento:
                            # Creamos una llave única: "Token + NombreOperador"
                            id_alerta = f"{token_ca}_{nombre}"
                            
                            # Si ya avisamos de este operador vendiendo este token hace menos de 10 min, ignoramos
                            if id_alerta in last_sell_alert and ahora - last_sell_alert[id_alerta] < SILENCIO_VENTA:
                                continue

                            last_sell_alert[id_alerta] = ahora
                            msg_v = (f"🚨🚨 *SALIDA DETECTADA* 🚨🚨\n\n"
                                     f"👤 *El operador {nombre} está vendiendo.*\n"
                                     f"💎 *Token:* `{token_ca}`\n"
                                     f"⚠️ *Acción:* Revisa tu posición.")
                            enviar_telegram(msg_v)
        
        return "OK", 200
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
