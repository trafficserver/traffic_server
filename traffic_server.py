import logging
import random
import threading
import time
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import urllib3
import json

# ==============================================================================
# >> ÁREA DE CONFIGURAÇÃO FINAL <<
# ==============================================================================
URL_DO_SEU_SITE = "https://gravacaodevinheta.com.br"
NOME_DO_SEU_SITE = "Gravação de Vinheta"
GA_API_SECRET = "u2ME7KqVTfu7S6BLosJsyQ"
# ==============================================================================

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Sua lista de proxies
proxies_list_raw = [
    # ... (a sua lista completa de proxies vai aqui, omiti para economizar espaço)
    {"ip_address": "39.102.208.189", "port": 8080}, {"ip_address": "47.250.155.254", "port": 4145},
    {"ip_address": "198.177.252.24", "port": 4145}
]
proxies_pool = [
    {"http": f"http://{p['ip_address']}:{p['port']}", "https": f"http://{p['ip_address']}:{p['port']}"}
    for p in proxies_list_raw
]
logging.info(f"✅ Carregados {len(proxies_pool)} proxies da lista estática.")

city_names = list(set([
    "São Paulo", "Rio de Janeiro", "Brasília", "Fortaleza", "Salvador", "Belo Horizonte", "Manaus", "Curitiba", "Recife", "Goiânia",
    "Porto Alegre", "Belém", "Guarulhos", "Campinas", "São Luís", "Maceió", "Campo Grande", "São Gonçalo", "Teresina", "João Pessoa"
]))
default_keywords = ["vinheta", "anuncio", "propaganda", "carro de som", "audio", "gravação"]
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
]
backlink_sites = ["https://www.globo.com", "https://www.uol.com.br", "https://www.terra.com.br"]

# --- NOVO: Mapeamento de cidades para IPs brasileiros simulados ---
# Usamos IPs de uma faixa que é conhecida por ser do Brasil (ex: 177.x, 189.x)
# Cada cidade terá um IP único para o Google poder diferenciá-las.
city_to_ip_map = {city: f"189.5.{i}.1" for i, city in enumerate(city_names)}

def get_referrer(traffic_type, keyword):
    if traffic_type == "organic": return f"https://www.google.com.br/search?q={keyword.replace(' ', '+')}"
    elif traffic_type == "social": return random.choice(["https://www.facebook.com/", "https://t.co/"])
    elif traffic_type == "backlink": return random.choice(backlink_sites)
    else: return "https://www.exemplo-referencia.com"

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None):
    city = random.choice(city_names)
    simulated_ip = city_to_ip_map.get(city) # Pega o IP simulado para a cidade
    keyword = random.choice(keywords) if keywords else random.choice(default_keywords)
    traffic_type = fixed_traffic_type if fixed_traffic_type else random.choice(["organic", "social", "backlink", "reference"])
    referrer = get_referrer(traffic_type, keyword)
    
    session_cookie = str(uuid.uuid4())
    user_agent = random.choice(user_agents)
    headers = { "Referer": referrer, "User-Agent": user_agent, "Cookie": f"session_id={session_cookie}" }
    
    proxies = None
    if proxies_pool: proxies = random.choice(proxies_pool)
    
    try:
        response = requests.get(URL_DO_SEU_SITE, headers=headers, proxies=proxies, timeout=20, verify=False)
        if response.status_code == 200:
            engagement_time = random.randint(30000, 90000)
            logging.info(f"✅ Acesso p/ {city} OK. Aguardando {engagement_time/1000}s.")
            time.sleep(engagement_time / 1000)

            # ****** MUDANÇA PRINCIPAL AQUI ******
            # Adicionamos o parâmetro "ip_override" para forçar a geolocalização
            event_data = {
                "client_id": str(random.randint(10**9, 10**10 - 1)),
                "events": [{
                    "name": "page_view",
                    "params": {
                        "page_location": URL_DO_SEU_SITE,
                        "page_title": NOME_DO_SEU_SITE,
                        "engagement_time_msec": engagement_time,
                        "session_id": session_cookie,
                        "ip_override": simulated_ip, # Força o IP
                        "user_agent_override": user_agent, # Força o User Agent
                        "city": city,
                        "traffic_source": traffic_type,
                        "region": "BR"
                    }
                }]
            }

            ga_url = f"https://www.google-analytics.com/mp/collect?measurement_id={analytics_id}&api_secret={GA_API_SECRET}"
            # O envio para o GA é sempre feito sem proxy para garantir a entrega.
            ga_response = requests.post(ga_url, json=event_data, timeout=20)
            
            if ga_response.status_code in [200, 204]:
                logging.info(f"📊 Evento enviado p/ GA com IP de {city} ({simulated_ip}). Sucesso!")
            else:
                logging.warning(f"⚠️ Falha ao enviar evento p/ GA ({ga_response.status_code}): {ga_response.text}")
        else:
            logging.warning(f"⚠️ Acesso falhou ({response.status_code}) para {URL_DO_SEU_SITE}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Erro ao gerar tráfego: {e}")
        if proxies and proxies in proxies_pool:
            try:
                proxies_pool.remove(proxies)
            except ValueError: pass

@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api():
    try:
        data = request.get_json(force=True)
        def worker():
            total_visits = int(data.get("totalVisits", 100))
            threads = []
            for i in range(total_visits):
                thread = threading.Thread(target=gerar_visita, args=(data.get("analyticsId"), data.get("keywords"), data.get("trafficType")))
                threads.append(thread)
                thread.start()
                time.sleep(random.uniform(1, 3))
            for thread in threads:
                thread.join()
            logging.info(f"Geração de {total_visits} visitas concluída.")
        threading.Thread(target=worker).start()
        return jsonify({"message": "Processo de geração iniciado com sucesso."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "Traffic Server Worker v2 (com IP Override) está online."