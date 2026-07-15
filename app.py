import threading
import asyncio
from flask import Flask, jsonify, render_template_string
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, GiftEvent, DisconnectEvent

app = Flask(__name__)

# ==========================================
# 1. ESTADO GLOBAL DEL JUEGO
# ==========================================
game_state = {
    "mexico_goals": 0,
    "argentina_goals": 0,
    "roses": 0,
    "donuts": 0,
    "events": [],
    "is_live": False
}

# ==========================================
# 2. PÁGINA WEB (HTML + CSS Retro + JavaScript)
# ==========================================
JUEGO_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>México vs Argentina - Retro TikTok Live</title>
    <link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
    <style>
        body { background-color: #2E8B57; color: white; font-family: 'Press Start 2P', cursive; text-align: center; margin: 0; padding: 20px; box-sizing: border-box; height: 100vh; border: 10px solid white; position: relative; }
        h1 { color: #FFD700; text-shadow: 4px 4px black; font-size: 24px; margin-bottom: 40px; margin-top: 20px; }
        .status-container { position: absolute; top: 20px; right: 20px; display: flex; align-items: center; font-size: 12px; background: rgba(0,0,0,0.5); padding: 10px; border-radius: 8px; border: 2px solid white; }
        .status-light { width: 15px; height: 15px; border-radius: 50%; background-color: red; margin-right: 10px; border: 2px solid white; box-shadow: 0 0 10px red; transition: all 0.3s; }
        .status-light.active { background-color: #00FF00; box-shadow: 0 0 15px #00FF00; }
        #liveStatusText { color: red; }
        #liveStatusText.active { color: #00FF00; }
        .scoreboard { font-size: 40px; margin: 20px auto; background: black; padding: 20px; border-radius: 10px; border: 4px dashed white; display: inline-block; text-shadow: 2px 2px #555; }
        .teams { display: flex; justify-content: space-around; margin-top: 30px; }
        .team { background: rgba(0, 0, 0, 0.6); padding: 20px; border-radius: 15px; width: 40%; border: 2px solid white; box-shadow: 5px 5px 0px black; }
        .flag { font-size: 60px; margin-bottom: 10px; }
        .team-name { font-size: 20px; margin-bottom: 15px; }
        .progress { font-size: 14px; color: #FFEA00; margin-top: 15px; line-height: 1.5; }
        .feed { margin-top: 40px; background: black; border: 2px solid white; padding: 10px; height: 120px; overflow: hidden; text-align: left; font-size: 12px; line-height: 1.8; color: #00FF00; }
        .goal-animation { animation: blink 0.5s infinite; }
        @keyframes blink { 0% { color: white; } 50% { color: #FFD700; } 100% { color: white; } }
    </style>
</head>
<body>
    <div class="status-container">
        <div class="status-light" id="liveStatusLight"></div>
        <span id="liveStatusText">OFFLINE</span>
    </div>
    <h1>⚽ FÚTBOL ETERNO ⚽</h1>
    <div class="scoreboard" id="scoreDisplay">🇲🇽 0 - 0 🇦🇷</div>
    <div class="teams">
        <div class="team" id="teamMex">
            <div class="flag">🇲🇽</div>
            <div class="team-name">MÉXICO</div>
            <div style="font-size: 12px;">Envíen Rosas 🌹</div>
            <div class="progress" id="progMex">Rosas: 0 / 10</div>
        </div>
        <div class="team" id="teamArg">
            <div class="flag">🇦🇷</div>
            <div class="team-name">ARGENTINA</div>
            <div style="font-size: 12px;">Envíen Donas 🍩</div>
            <div class="progress" id="progArg">Donas: 0 / 10</div>
        </div>
    </div>
    <div class="feed" id="eventFeed"><div>> Sistema iniciado. Esperando regalos...</div></div>
    <script>
        let lastGoalMx = 0; let lastGoalAr = 0;
        async function fetchState() {
            try {
                const response = await fetch('/api/state');
                const data = await response.json();
                const statusLight = document.getElementById('liveStatusLight');
                const statusText = document.getElementById('liveStatusText');
                if (data.is_live) { statusLight.classList.add('active'); statusText.classList.add('active'); statusText.innerText = "ONLINE"; }
                else { statusLight.classList.remove('active'); statusText.classList.remove('active'); statusText.innerText = "OFFLINE"; }
                document.getElementById('scoreDisplay').innerText = `🇲🇽 ${data.mexico_goals} - ${data.argentina_goals} 🇦🇷`;
                document.getElementById('progMex').innerText = `Rosas: ${data.roses} / 10`;
                document.getElementById('progArg').innerText = `Donas: ${data.donuts} / 10`;
                if (data.mexico_goals > lastGoalMx) { document.getElementById('scoreDisplay').classList.add('goal-animation'); setTimeout(() => document.getElementById('scoreDisplay').classList.remove('goal-animation'), 3000); lastGoalMx = data.mexico_goals; }
                if (data.argentina_goals > lastGoalAr) { document.getElementById('scoreDisplay').classList.add('goal-animation'); setTimeout(() => document.getElementById('scoreDisplay').classList.remove('goal-animation'), 3000); lastGoalAr = data.argentina_goals; }
                const feedDiv = document.getElementById('eventFeed'); feedDiv.innerHTML = "";
                data.events.forEach(evt => { const el = document.createElement("div"); el.innerText = evt; feedDiv.appendChild(el); });
            } catch (error) { console.error("Error:", error); }
        }
        setInterval(fetchState, 1000);
    </script>
</body>
</html>
"""

# ==========================================
# 3. RUTAS DE FLASK
# ==========================================
@app.route('/')
def home():
    return render_template_string(JUEGO_HTML)

@app.route('/api/state')
def get_state():
    return jsonify(game_state)

def add_event(message):
    game_state["events"].insert(0, f"> {message}")
    if len(game_state["events"]) > 5: game_state["events"].pop()

# ==========================================
# 4. CONEXIÓN A TIKTOK LIVE
# ==========================================
def start_tiktok_client():
    # USUARIO ACTUALIZADO (Sin el símbolo @)
    TIKTOK_USERNAME = "firu0123456789"

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)

    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent):
        game_state["is_live"] = True
        add_event("Conectado a TikTok Live exitosamente.")

    @client.on(DisconnectEvent)
    async def on_disconnect(event: DisconnectEvent):
        game_state["is_live"] = False
        add_event("Desconectado del Live.")

    @client.on(GiftEvent)
    async def on_gift(event: GiftEvent):
        gift_name = event.gift.name.lower()
        user = event.user.nickname
        if "rose" in gift_name or "rosa" in gift_name:
            game_state["roses"] += 1
            add_event(f"{user} envió una Rosa 🌹")
            if game_state["roses"] >= 10:
                game_state["mexico_goals"] += 1
                game_state["roses"] -= 10
                add_event("¡GOOOOOOOL DE MÉXICO! 🇲🇽⚽")
        elif "doughnut" in gift_name or "dona" in gift_name or "donut" in gift_name:
            game_state["donuts"] += 1
            add_event(f"{user} envió una Dona 🍩")
            if game_state["donuts"] >= 10:
                game_state["argentina_goals"] += 1
                game_state["donuts"] -= 10
                add_event("¡GOOOOOOOL DE ARGENTINA! 🇦🇷⚽")

    try:
        client.run()
    except Exception as e:
        game_state["is_live"] = False
        print(f"Error en TikTok Client: {e}")

if __name__ == '__main__':
    tiktok_thread = threading.Thread(target=start_tiktok_client, daemon=True)
    tiktok_thread.start()
    app.run(host='0.0.0.0', port=5000)
