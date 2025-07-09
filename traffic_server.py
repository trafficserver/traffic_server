import logging
import random
import threading
import time
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import urllib3
from fp.fp import FreeProxy

# Desativa avisos de SSL (não recomendado em produção, mas útil para proxies gratuitos)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuração do Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app) # Habilita CORS para permitir chamadas da Hostinger

brazilian_proxies = []

# --- INÍCIO DAS LISTAS GLOBAIS ---
city_names = list(set([
    "São Paulo", "Rio de Janeiro", "Brasília", "Fortaleza", "Salvador", "Belo Horizonte", "Manaus", "Curitiba", "Recife", "Goiânia",
    "Porto Alegre", "Belém", "Guarulhos", "Campinas", "São Luís", "Maceió", "Campo Grande", "São Gonçalo", "Teresina", "João Pessoa"
    # Adicione mais cidades se desejar, mas uma amostra já é suficiente
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

GA_API_SECRET = "x7qjOor0S12kx5zsxmkmig" # Lembre-se de manter isso seguro

backlink_sites = [
    "https://www.globo.com", "https://www.uol.com.br", "https://www.terra.com.br", "https://www.folha.uol.com.br",
    "https://www.estadao.com.br", "https://www.r7.com", "https://www.metropoles.com", "https://www.ig.com.br"
]
# --- FIM DAS LISTAS GLOBAIS ---


def fetch_brazilian_proxies():
    global brazilian_proxies
    logging.info("🔎 Buscando proxies gratuitos do Brasil...")
    try:
        proxy_address = FreeProxy(country_id=['BR'], https=True, timeout=5).get()
        if proxy_address:
            proxy_dict = {"http": proxy_address, "https": proxy_address}
            if proxy_dict not in brazilian_proxies:
                brazilian_proxies.append(proxy_dict)
            logging.info(f"✅ Proxy brasileiro encontrado e adicionado: {proxy_address}")
        else:
            logging.warning("⚠️ Nenhum proxy gratuito do Brasil foi encontrado nesta tentativa.")
    except Exception as e:
        logging.error(f"❌ Falha ao buscar proxy: {e}")

def get_referrer(traffic_type, keyword, city):
    if traffic_type == "organic":
        return f"https://www.google.com.br/search?q={keyword.replace(' ', '+')}&hl=pt-BR&gl=br"
    elif traffic_type == "social":
        return random.choice(["https://www.facebook.com/", "https://www.instagram.com/", "https://t.co/"])
    elif traffic_type == "backlink":
        return random.choice(backlink_sites)
    else: # reference ou None
        return random.choice(["https://www.exemplo-referencia.com", "https://blog.parceiro.com.br/post-sobre-nos"])

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None):
    city = random.choice(city_names)
    keyword = random.choice(keywords) if keywords else random.choice(default_keywords)
    traffic_type = fixed_traffic_type if fixed_traffic_type else random.choice(["organic", "social", "backlink", "reference"])
    referrer = get_referrer(traffic_type, keyword, city)
    
    session_cookie = str(uuid.uuid4())
    user_agent = random.choice(user_agents)
    headers = { "Referer": referrer, "User-Agent": user_agent, "Cookie": f"session_id={session_cookie}" }
    
    proxies = None
    proxy_info = "conexão direta"
    if brazilian_proxies:
        proxies = random.choice(brazilian_proxies)
        proxy_info = f"proxy {proxies.get('http')}"

    try:
        response = requests.get("https://propagandacidade.site", headers=headers, proxies=proxies, timeout=30, verify=False)
        if response.status_code == 200:
            logging.info(f"✅ Acesso gerado ({city}, {traffic_type}) via {proxy_info}")
            engagement_time = random.randint(30000, 180000)
            logging.info(f"🕒 Visitante permanece por {engagement_time / 1000:.1f}s...")
            time.sleep(engagement_time / 1000)

            event_data = {
                "client_id": str(random.randint(10**9, 10**10 - 1)),
                "user_properties": { "city": {"value": city}, "region": {"value": "BR"} },
                "events": [{"name": "page_view", "params": { "page_location": "https://propagandacidade.site", "page_title": "Propaganda Cidade", "engagement_time_msec": engagement_time, "geo_id": city, "city": city, "region": "BR"}}]
            }
            ga_url = f"https://www.google-analytics.com/mp/collect?measurement_id={analytics_id}&api_secret={GA_API_SECRET}"
            ga_response = requests.post(ga_url, json=event_data, proxies=proxies)
            if ga_response.status_code in [200, 204]:
                logging.info(f"📊 Evento enviado para o GA com sucesso! Cidade: {city}, Tráfego: {traffic_type}")
            else:
                logging.warning(f"⚠️ Falha ao enviar evento para o GA ({ga_response.status_code}): {ga_response.text}")
        else:
            logging.warning(f"⚠️ Acesso falhou ({response.status_code}) para https://propagandacidade.site via {proxy_info}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Erro ao gerar tráfego via {proxy_info}: {e}")
        if proxies and proxies in brazilian_proxies:
            logging.info(f"Removendo proxy com falha: {proxies.get('http')}")
            brazilian_proxies.remove(proxies)

@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api():
    try:
        data = request.get_json(force=True)
        analytics_id = data.get("analyticsId")
        total_visits = int(data.get("totalVisits", 100))
        keywords = data.get("keywords")
        traffic_type = data.get("trafficType") # Será None se não for enviado, o que é tratado em gerar_visita

        if not all([analytics_id, total_visits, keywords]):
            return jsonify({"error": "Parâmetros 'analyticsId', 'totalVisits' e 'keywords' são obrigatórios."}), 400

        def worker():
            if not brazilian_proxies:
                fetch_brazilian_proxies()
            
            logging.info(f"Iniciando a geração de {total_visits} visitas em background.")
            threads = []
            for i in range(total_visits):
                thread = threading.Thread(target=gerar_visita, args=(analytics_id, keywords, traffic_type))
                threads.append(thread)
                thread.start()
                logging.info(f"Thread {i+1}/{total_visits} iniciada.")
                time.sleep(random.uniform(1, 3)) # Espaçamento maior para não sobrecarregar
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
    return "Traffic Server Worker está online. Use o endpoint /api/gerar-trafego para simular visitas."