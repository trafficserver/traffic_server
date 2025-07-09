import logging
import random
import threading
import time
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import urllib3

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

# --- Listas de Dados ---
city_names = list(set([
    "São Paulo", "Rio de Janeiro", "Brasília", "Fortaleza", "Salvador", "Belo Horizonte", "Manaus", "Curitiba", "Recife", "Goiânia"
]))
default_keywords = ["vinheta", "anuncio", "propaganda", "carro de som", "audio"]
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1"
]
backlink_sites = ["https://www.globo.com", "https://www.uol.com.br", "https://www.terra.com.br"]

# Mapeamento de cidades para IPs brasileiros simulados
city_to_ip_map = {city: f"189.5.{i}.1" for i, city in enumerate(city_names)}

# REMOVIDO: A função load_proxies_from_file() e a lista de proxies não são mais necessárias.

def get_referrer(traffic_type, keyword):
    if traffic_type == "organic": return f"https://www.google.com.br/search?q={keyword.replace(' ', '+')}"
    elif traffic_type == "social": return random.choice(["https://www.facebook.com/", "https://t.co/"])
    elif traffic_type == "backlink": return random.choice(backlink_sites)
    else: return "https://www.exemplo-referencia.com"

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None):
    city = random.choice(city_names)
    simulated_ip = city_to_ip_map.get(city)
    keyword = random.choice(keywords) if keywords else random.choice(default_keywords)
    traffic_type = fixed_traffic_type if fixed_traffic_type else random.choice(["organic", "social", "backlink", "reference"])
    referrer = get_referrer(traffic_type, keyword)
    
    session_cookie = str(uuid.uuid4())
    user_agent = random.choice(user_agents)
    
    try:
        # A visita ao site é simulada, mas não essencial.
        # O envio do evento para o GA é a parte importante.
        engagement_time = random.randint(30000, 90000)
        logging.info(f"Simulando visita de {city} por {engagement_time/1000}s. Enviando evento para GA...")
        
        # O "sleep" pode ser removido pois o engagement_time é apenas um parâmetro.
        # time.sleep(engagement_time / 1000) 

        event_data = {
            "client_id": str(random.randint(10**9, 10**10 - 1)),
            "events": [{
                "name": "page_view",
                "params": {
                    "page_location": URL_DO_SEU_SITE,
                    "page_title": NOME_DO_SEU_SITE,
                    "engagement_time_msec": engagement_time,
                    "session_id": session_cookie,
                    "ip_override": simulated_ip,
                    "user_agent_override": user_agent,
                    "document_referrer": referrer,
                    "city": city,
                    "traffic_source": traffic_type,
                    "region": "BR"
                }
            }]
        }

        ga_url = f"https://www.google-analytics.com/mp/collect?measurement_id={analytics_id}&api_secret={GA_API_SECRET}"
        # Envio para o GA é sempre direto para garantir a entrega e a velocidade.
        ga_response = requests.post(ga_url, json=event_data, timeout=20)
        
        if ga_response.status_code in [200, 204]:
            logging.info(f"📊 Evento enviado p/ GA com IP de {city} ({simulated_ip}). Sucesso!")
        else:
            logging.warning(f"⚠️ Falha ao enviar evento p/ GA ({ga_response.status_code}): {ga_response.text}")

    except Exception as e:
        logging.error(f"❌ Erro inesperado durante a geração da visita: {e}")

@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api():
    try:
        data = request.get_json(force=True)
        def worker():
            total_visits = int(data.get("totalVisits", 100))
            threads = []
            for _ in range(total_visits):
                thread = threading.Thread(target=gerar_visita, args=(data.get("analyticsId"), data.get("keywords"), data.get("trafficType")))
                threads.append(thread)
                thread.start()
                # O espaçamento aqui é suficiente, não precisamos do timeout dos proxies
                time.sleep(random.uniform(0.1, 0.5))
            for t in threads:
                t.join()
            logging.info(f"Geração de {total_visits} visitas concluída.")
            
        threading.Thread(target=worker).start()
        return jsonify({"message": "Processo de geração iniciado com sucesso."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "Traffic Server v_final_estavel (IP Override) está online."