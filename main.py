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
VENTANA_TIEMPO = 1800 
SILENCIO_POST_ALERTA = 900 

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
    # Filtro de seguridad básico
    if mcap > 100_000_000 or mcap == 0 or liq == 0: return 0, ""
    
    puntos = 0
    ratio_liq = mcap / liq

    # --- FILTRO 1: RATIO DE LIQUIDEZ (Anti-Caídas Instantáneas) ---
    # Si el MCap es más de 5 veces la liquidez, el token es puro aire.
    if ratio_liq > 5.5: return 1, "FILTRADO (LIQ FRÁGIL)"

    # --- FILTRO 2: TECHO DE MARKET CAP ---
    # Penalizamos tokens de más de $1M (como XOGE) porque duplicar es mucho más lento.
    if mcap > 1_000_000:
        puntos -= 30
    elif mcap < 300_000:
        puntos += 30 # Bonus para "Mooncats" pequeños

    # --- FILTRO 3: EDAD Y CONFLUENCIA ---
    if edad < 60: puntos += 40
    elif edad < 1440: puntos += 20
    
    puntos += (ops_count * 15)

    # --- CLASIFICACIÓN FINAL ---
    if puntos >= 85: return 5, "⭐⭐⭐⭐⭐ (GEMA ALPHA)"
    if puntos >= 65: return 4, "⭐⭐⭐⭐ (POTENCIAL ALTO)"
    return 1, "FILTRADO"

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown", "disable_web_page_preview": True})
    except: pass

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        data = request.json
        for tx in data:
            comprador = tx.get('feePayer')
            if comprador not in WALLETS: continue
            nombre = WALLETS[comprador]
            ahora = time.time()

            if 'tokenTransfers' in tx:
                for tf in tx['tokenTransfers']:
                    token_ca = tf.get('mint')
                    if token_ca in ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"]: continue

                    # LÓGICA DE COMPRA
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
                                tokens_en_seguimiento.add(token_ca) 
                                alerta_liq = "🚨 *RIESGO DE LIQUIDEZ*" if liq < 10000 else ""
                                mcap_str = f"${mcap/1000000:.2f}M" if mcap > 1000000 else f"${mcap/1000:.1f}K"
                                
                                msg = (f"{etiqueta}\n━━━━━━━━━━━━━━━\n"
                                       f"💎 *Token:* `{token_ca}`\n"
                                       f"👥 *Equipo:* {', '.join(ops)}\n\n"
                                       f"💰 *MCap:* {mcap_str} | 💧 *Liq:* ${liq:,.0f} {alerta_liq}\n"
                                       f"⏳ *Edad:* {edad} min\n\n"
                                       f"🛡️ [RugCheck](https://rugcheck.xyz/tokens/{token_ca})\n"
                                       f"📊 [DexScreener](https://dexscreener.com/solana/{token_ca})")
                                enviar_telegram(msg)
                                tracker[token_ca] = [] 

                    # LÓGICA DE VENTA (ALERTA URGENTE)
                    if tf.get('fromUserAccount') == comprador:
                        if token_ca in tokens_en_seguimiento:
                            msg_v = (f"🚨🚨 *SALIDA URGENTE DETECTADA* 🚨🚨\n\n"
                                     f"👤 *El operador {nombre} acaba de VENDER.*\n"
                                     f"💎 *Token:* `{token_ca}`\n"
                                     f"⚠️ *Acción:* Protege ganancias o cierra posición YA. La confluencia se está rompiendo.")
                            enviar_telegram(msg_v)
        
        return "OK", 200
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
