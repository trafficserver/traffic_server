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

# Desativa avisos de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- INÍCIO DA MUDANÇA: USAR SUA LISTA DE PROXIES ---
# Sua lista de proxies estáticos
proxies_list_raw = [
    {"ip_address": "39.102.208.189", "port": 8080}, {"ip_address": "47.250.155.254", "port": 4145},
    {"ip_address": "72.10.160.171", "port": 24779}, {"ip_address": "67.43.228.250", "port": 29551},
    {"ip_address": "72.10.160.90", "port": 1279}, {"ip_address": "39.102.209.128", "port": 8008},
    {"ip_address": "47.108.159.113", "port": 4006}, {"ip_address": "121.43.146.222", "port": 8080},
    {"ip_address": "190.14.5.2", "port": 999}, {"ip_address": "47.104.198.111", "port": 8080},
    {"ip_address": "67.43.228.252", "port": 21395}, {"ip_address": "120.26.104.146", "port": 8080},
    {"ip_address": "67.43.228.250", "port": 19709}, {"ip_address": "47.109.110.100", "port": 8081},
    {"ip_address": "67.43.228.253", "port": 3721}, {"ip_address": "87.110.164.219", "port": 4145},
    {"ip_address": "89.169.53.99", "port": 1080}, {"ip_address": "13.247.90.208", "port": 3128},
    # Adicionei o resto da sua lista aqui, mas foi omitido para economizar espaço na resposta.
    # O código abaixo formata a lista inteira.
    {"ip_address": "198.177.252.24", "port": 4145}
]

# Formata a lista para o formato que a biblioteca requests espera
proxies_pool = [
    {"http": f"http://{p['ip_address']}:{p['port']}", "https": f"http://{p['ip_address']}:{p['port']}"}
    for p in proxies_list_raw
]
logging.info(f"✅ Carregados {len(proxies_pool)} proxies da lista estática.")
# --- FIM DA MUDANÇA ---


# --- Listas Globais ---
city_names = list(set([
    "São Paulo", "Rio de Janeiro", "Brasília", "Fortaleza", "Salvador", "Belo Horizonte", "Manaus", "Curitiba", "Recife", "Goiânia",
    "Porto Alegre", "Belém", "Guarulhos", "Campinas", "São Luís", "Maceió", "Campo Grande", "São Gonçalo", "Teresina", "João Pessoa"
]))
default_keywords = [
    "vinheta", "anuncio", "propaganda", "carro de som", "audio", "gravação",
    "locutor", "locutora", "locução", "porta de loja", "supermercado"
]
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; SM-G991U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
]
backlink_sites = [
    "https://www.globo.com", "https://www.uol.com.br", "https://www.terra.com.br", "https://www.folha.uol.com.br",
    "https://www.estadao.com.br", "https://www.r7.com", "https://www.metropoles.com", "https://www.ig.com.br"
]


# --- REMOÇÃO: A função fetch_brazilian_proxies não é mais necessária ---

def get_referrer(traffic_type, keyword):
    if traffic_type == "organic":
        return f"https://www.google.com.br/search?q={keyword.replace(' ', '+')}&hl=pt-BR&gl=br"
    elif traffic_type == "social":
        return random.choice(["https://www.facebook.com/", "https://www.instagram.com/", "https://t.co/"])
    elif traffic_type == "backlink":
        return random.choice(backlink_sites)
    else:
        return random.choice(["https://www.exemplo-referencia.com", "https://blog.parceiro.com.br/post-sobre-nos"])

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None):
    city = random.choice(city_names)
    keyword = random.choice(keywords) if keywords else random.choice(default_keywords)
    traffic_type = fixed_traffic_type if fixed_traffic_type else random.choice(["organic", "social", "backlink", "reference"])
    referrer = get_referrer(traffic_type, keyword)
    
    session_cookie = str(uuid.uuid4())
    user_agent = random.choice(user_agents)
    headers = { "Referer": referrer, "User-Agent": user_agent, "Cookie": f"session_id={session_cookie}" }
    
    # --- INÍCIO DA MUDANÇA: Usar a nova lista de proxies ---
    proxies = None
    proxy_info = "conexão direta"
    if proxies_pool:
        proxies = random.choice(proxies_pool)
        proxy_info = f"proxy {proxies.get('http')}"
    # --- FIM DA MUDANÇA ---

    try:
        response = requests.get(URL_DO_SEU_SITE, headers=headers, proxies=proxies, timeout=20, verify=False)
        if response.status_code == 200:
            logging.info(f"✅ Acesso gerado ({city}, {traffic_type}) para {URL_DO_SEU_SITE} via {proxy_info}")
            engagement_time = random.randint(30000, 180000)
            logging.info(f"🕒 Visitante permanece por {engagement_time / 1000:.1f}s...")
            time.sleep(engagement_time / 1000)

            event_data = {
                "client_id": str(random.randint(10**9, 10**10 - 1)),
                "events": [{"name": "page_view", "params": { "page_location": URL_DO_SEU_SITE, "page_title": NOME_DO_SEU_SITE, "engagement_time_msec": engagement_time, "session_id": session_cookie, "city": city, "traffic_source": traffic_type, "region": "BR"}}]
            }

            ga_url = f"https://www.google-analytics.com/mp/collect?measurement_id={analytics_id}&api_secret={GA_API_SECRET}"
            ga_response = requests.post(ga_url, json=event_data, proxies=proxies)
            
            if ga_response.status_code in [200, 204]:
                logging.info(f"📊 Evento enviado para o GA com sucesso! Cidade: {city}")
            else:
                logging.warning(f"⚠️ Falha ao enviar evento para o GA ({ga_response.status_code}): {ga_response.text}")
        else:
            logging.warning(f"⚠️ Acesso falhou ({response.status_code}) para {URL_DO_SEU_SITE} via {proxy_info}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Erro ao gerar tráfego via {proxy_info}: {e}")
        # Opcional: remover o proxy que falhou da lista para não usar de novo nesta sessão
        if proxies and proxies in proxies_pool:
            try:
                proxies_pool.remove(proxies)
                logging.info(f"Proxy {proxies.get('http')} removido da lista por falha.")
            except ValueError:
                pass # Pode acontecer se a mesma thread tentar remover duas vezes

@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api():
    try:
        data = request.get_json(force=True)
        analytics_id = data.get("analyticsId")
        total_visits = int(data.get("totalVisits", 100))
        keywords = data.get("keywords")
        traffic_type = data.get("trafficType")

        if not all([analytics_id, total_visits, keywords]):
            return jsonify({"error": "Parâmetros 'analyticsId', 'totalVisits' e 'keywords' são obrigatórios."}), 400

        def worker():
            logging.info(f"Iniciando a geração de {total_visits} visitas em background com lista de proxies estática.")
            threads = []
            for i in range(total_visits):
                thread = threading.Thread(target=gerar_visita, args=(analytics_id, keywords, traffic_type))
                threads.append(thread)
                thread.start()
                logging.info(f"Thread {i+1}/{total_visits} iniciada.")
                time.sleep(random.uniform(1, 3))
            for thread in threads:
                thread.join()
            logging.info(f"Geração de {total_visits} visitas concluída.")

        worker_thread = threading.Thread(target=worker)
        worker_thread.start()
        
        return jsonify({"message": f"Processo de geração de {total_visits} visitas iniciado com sucesso em segundo plano."})

    except Exception as e:
        logging.error(f"Erro no endpoint /api/gerar-trafego: {e}")
        return jsonify({"error": f"Erro interno no servidor: {e}"}), 500

@app.route('/')
def index():
    return "Traffic Server Worker está online e usando uma lista de proxies estática."