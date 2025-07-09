import logging
import random
import threading
import time
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS # Importar CORS
import requests
import urllib3
from fp.fp import FreeProxy

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
# IMPORTANTE: Habilitar CORS para que seu site na Hostinger possa chamar esta API no Render
CORS(app)

brazilian_proxies = []

# (Mantenha todas as suas listas: city_names, default_keywords, user_agents, backlink_sites, GA_API_SECRET)
# ...

def fetch_brazilian_proxies():
    # ... (mantenha a função como na versão anterior)
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
    # ... (mantenha a função como na versão anterior)
    # ...

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None):
    # ... (mantenha a função como na versão anterior)
    # ...

@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api(): # Renomeado para evitar conflito
    data = request.get_json(force=True)
    analytics_id = data.get("analyticsId")
    total_visits = int(data.get("totalVisits", 100))
    keywords = data.get("keywords")
    traffic_type = data.get("trafficType")

    # Inicia a busca de proxies e a geração de visitas em uma nova thread
    # para retornar a resposta ao PHP imediatamente.
    def worker():
        if not brazilian_proxies:
            fetch_brazilian_proxies()
        
        logging.info(f"Iniciando a geração de {total_visits} visitas em background.")
        threads = []
        for _ in range(total_visits):
            thread = threading.Thread(target=gerar_visita, args=(analytics_id, keywords, traffic_type))
            threads.append(thread)
            thread.start()
            # Um pequeno delay para não sobrecarregar os proxies gratuitos
            time.sleep(random.uniform(0.5, 2)) 
        for thread in threads:
            thread.join()
        logging.info("Geração de visitas em background concluída.")

    # Inicia a thread do worker e retorna
    worker_thread = threading.Thread(target=worker)
    worker_thread.start()
    
    return jsonify({"message": f"Processo de geração de {total_visits} visitas iniciado em segundo plano."})

# Endpoint de verificação para saber se o servidor está online
@app.route('/')
def index():
    return "Traffic Server Worker está online."

# Não precisa mais do if __name__ == '__main__' para rodar com 'app.run'. 
# O Render usará um servidor WSGI como o Gunicorn.