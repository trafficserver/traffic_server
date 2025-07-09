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
# >> ÁREA DE CONFIGURAÇÃO <<
# ==============================================================================
URL_DO_SEU_SITE = "https://gravacaodevinheta.com.br"
NOME_DO_SEU_SITE = "Gravação de Vinheta"
GA_API_SECRET = "u2ME7KqVTfu7S6BLosJsyQ"
# ==============================================================================

# --- Configurações Iniciais ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- Pool Global de Proxies ---
proxies_pool = []

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

# ==============================================================================
# >> NOVA LÓGICA DE CARREGAMENTO DE PROXIES <<
# ==============================================================================
def load_proxies_from_file():
    """Carrega a lista de proxies do arquivo proxies.json."""
    global proxies_pool
    try:
        with open('proxies.json', 'r') as f:
            proxies_list_raw = json.load(f)
        
        # Converte a lista para o formato que a biblioteca requests espera
        proxies_pool = [
            {"http": f"http://{p['ip']}:{p['port']}", "https": f"http://{p['ip']}:{p['port']}"}
            for p in proxies_list_raw
        ]
        logging.info(f"✅ Carregados {len(proxies_pool)} proxies do arquivo proxies.json.")
        if not proxies_pool:
            logging.warning("⚠️ O arquivo proxies.json está vazio ou mal formatado.")
            
    except FileNotFoundError:
        logging.error("❌ Erro: Arquivo 'proxies.json' não encontrado. O tráfego será gerado sem proxies.")
        proxies_pool = []
    except Exception as e:
        logging.error(f"❌ Erro ao carregar ou processar 'proxies.json': {e}")
        proxies_pool = []

# ==============================================================================

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
                "events": [{"name": "page_view", "params": { "page_location": URL_DO_SEU_SITE, "page_title": NOME_DO_SEU_SITE, "engagement_time_msec": engagement_time, "session_id": session_cookie, "city": city, "traffic_source": traffic_type, "region": "BR"}}]
            }

            ga_url = f"https://www.google-analytics.com/mp/collect?measurement_id={analytics_id}&api_secret={GA_API_SECRET}"
            
            try:
                if not proxies:
                    raise ValueError("Nenhum proxy disponível para tentativa.")
                logging.info(f"Tentando enviar evento para o GA via {proxy_info}...")
                ga_response = requests.post(ga_url, json=event_data, proxies=proxies, timeout=20, verify=False)
                if ga_response.status_code in [200, 204]:
                    logging.info(f"📊 Evento enviado para o GA VIA PROXY com sucesso! Cidade: {city}")
                else:
                    raise ValueError(f"Proxy falhou com status {ga_response.status_code}")
            except (requests.exceptions.RequestException, ValueError) as e_proxy:
                logging.warning(f"❌ Envio via proxy falhou: {e_proxy}. Tentando conexão direta...")
                ga_response_direct = requests.post(ga_url, json=event_data, timeout=20)
                if ga_response_direct.status_code in [200, 204]:
                    logging.info("📊 Evento enviado via CONEXÃO DIRETA com sucesso.")
                else:
                    logging.error(f"❌❌ Falha no envio direto também ({ga_response_direct.status_code}): {ga_response_direct.text}")
        else:
            logging.warning(f"⚠️ Acesso ao site falhou ({response.status_code}) via {proxy_info}")
            
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Erro ao acessar o site via {proxy_info}: {e}")
        if proxies and proxies in proxies_pool:
            try:
                proxies_pool.remove(proxies)
                logging.info(f"Proxy {proxies.get('http')} removido.")
            except ValueError: pass

@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api():
    try:
        # Carrega os proxies do arquivo a cada nova requisição de lote
        load_proxies_from_file()
        
        data = request.get_json(force=True)
        def worker():
            total_visits = int(data.get("totalVisits", 100))
            logging.info(f"Iniciando a geração de {total_visits} visitas em background.")
            threads = []
            for _ in range(total_visits):
                thread = threading.Thread(target=gerar_visita, args=(data.get("analyticsId"), data.get("keywords"), data.get("trafficType")))
                threads.append(thread)
                thread.start()
                time.sleep(random.uniform(1, 3))
            for thread in threads:
                thread.join()
            logging.info(f"Geração de {total_visits} visitas concluída.")
            
        threading.Thread(target=worker).start()
        return jsonify({"message": "Processo de geração com proxies do arquivo JSON iniciado."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "Traffic Server Worker v5 (JSON-based) está online."

# Carrega os proxies uma vez quando o servidor inicia.
if __name__ != '__main__':
    load_proxies_from_file()