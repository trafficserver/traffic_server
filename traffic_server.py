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

# Desativa avisos de SSL (útil para proxies gratuitos)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
# Habilita CORS para aceitar requisições de qualquer origem para a API
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- Sua lista de proxies estáticos ---
# O ideal é usar uma lista grande e atualizada. A lista completa foi omitida aqui para economizar espaço.
proxies_list_raw = [
    {"ip_address": "39.102.208.189", "port": 8080}, {"ip_address": "47.250.155.254", "port": 4145},
    {"ip_address": "72.10.160.171", "port": 24779}, {"ip_address": "67.43.228.250", "port": 29551},
    {"ip_address": "72.10.160.90", "port": 1279}, {"ip_address": "39.102.209.128", "port": 8008},
    {"ip_address": "47.108.159.113", "port": 4006}, {"ip_address": "121.43.146.222", "port": 8080},
    {"ip_address": "190.14.5.2", "port": 999}, {"ip_address": "47.104.198.111", "port": 8080},
    # ... e o resto da sua lista de proxies
    {"ip_address": "198.177.252.24", "port": 4145}
]
proxies_pool = [
    {"http": f"http://{p['ip_address']}:{p['port']}", "https": f"http://{p['ip_address']}:{p['port']}"}
    for p in proxies_list_raw
]
logging.info(f"✅ Carregados {len(proxies_pool)} proxies da lista estática.")

# --- Listas Globais de Dados ---
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

def get_referrer(traffic_type, keyword):
    if traffic_type == "organic": return f"https://www.google.com.br/search?q={keyword.replace(' ', '+')}"
    elif traffic_type == "social": return random.choice(["https://www.facebook.com/", "https://t.co/"])
    elif traffic_type == "backlink": return random.choice(backlink_sites)
    else: return "https://www.exemplo-referencia.com"

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None):
    city = random.choice(city_names)
    keyword = random.choice(keywords) if keywords else random.choice(default_keywords)
    traffic_type = fixed_traffic_type if fixed_traffic_type else random.choice(["organic", "social", "backlink", "reference"])
    referrer = get_referrer(traffic_type, keyword)
    
    session_cookie = str(uuid.uuid4())
    user_agent = random.choice(user_agents)
    headers = { "Referer": referrer, "User-Agent": user_agent, "Cookie": f"session_id={session_cookie}" }
    
    proxies = None
    proxy_info = "conexão direta"
    if proxies_pool:
        proxies = random.choice(proxies_pool)
        proxy_info = f"proxy {proxies.get('http')}"

    try:
        response = requests.get(URL_DO_SEU_SITE, headers=headers, proxies=proxies, timeout=20, verify=False)
        if response.status_code == 200:
            engagement_time = random.randint(30000, 90000)
            logging.info(f"✅ Acesso p/ {city} OK via {proxy_info}. Aguardando {engagement_time/1000}s.")
            time.sleep(engagement_time / 1000)

            event_data = {
                "client_id": str(random.randint(10**9, 10**10 - 1)),
                "events": [{
                    "name": "page_view",
                    "params": {
                        "page_location": URL_DO_SEU_SITE,
                        "page_title": NOME_DO_SEU_SITE,
                        "engagement_time_msec": engagement_time,
                        "session_id": session_cookie,
                        "city": city,
                        "traffic_source": traffic_type,
                        "region": "BR"
                    }
                }]
            }

            ga_url = f"https://www.google-analytics.com/mp/collect?measurement_id={analytics_id}&api_secret={GA_API_SECRET}"
            
            # Tenta enviar o evento para o GA usando o proxy para geolocalização correta no mapa.
            try:
                if not proxies:
                    raise ValueError("Nenhum proxy disponível para tentativa.")
                
                logging.info(f"Tentando enviar evento para o GA via {proxy_info}...")
                ga_response = requests.post(ga_url, json=event_data, proxies=proxies, timeout=20, verify=False)
                
                if ga_response.status_code in [200, 204]:
                    logging.info(f"📊 Evento enviado para o GA VIA PROXY com sucesso! Cidade: {city}")
                else:
                    logging.warning(f"⚠️ Falha ao enviar via proxy ({ga_response.status_code}). Tentando sem proxy...")
                    raise ValueError("Proxy failed HTTP check")

            except (requests.exceptions.RequestException, ValueError) as e_proxy:
                logging.warning(f"❌ Erro no envio via proxy: {e_proxy}. Tentando conexão direta...")
                # Fallback: se o proxy falhar, envia diretamente para garantir a contagem.
                ga_response_direct = requests.post(ga_url, json=event_data, timeout=20)
                if ga_response_direct.status_code in [200, 204]:
                    logging.info("📊 Evento enviado para o GA via CONEXÃO DIRETA com sucesso.")
                else:
                    logging.error(f"❌❌ Falha no envio direto também ({ga_response_direct.status_code}): {ga_response_direct.text}")
        else:
            logging.warning(f"⚠️ Acesso ao site falhou ({response.status_code}) via {proxy_info}")
            
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Erro ao acessar o site via {proxy_info}: {e}")
        if proxies and proxies in proxies_pool:
            try:
                proxies_pool.remove(proxies)
                logging.info(f"Proxy {proxies.get('http')} removido da lista.")
            except ValueError: pass

@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api():
    try:
        data = request.get_json(force=True)
        def worker():
            total_visits = int(data.get("totalVisits", 100))
            logging.info(f"Iniciando a geração de {total_visits} visitas em background.")
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
        return jsonify({"message": f"Processo de geração de {data.get('totalVisits', 100)} visitas iniciado com sucesso."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "Traffic Server Worker v3 (Proxy-First-Send) está online."