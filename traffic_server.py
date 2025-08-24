import logging
import random
import threading
import time
import uuid
import os # NOVO
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import urllib3
import json
import queue

# ==============================================================================
# >> ÁREA DE CONFIGURAÇÃO <<
# ==============================================================================
URL_DO_SEU_SITE = "https://gravacaodevinheta.com.br"
NOME_DO_SEU_SITE = "Gravação de Vinheta"
GA_API_SECRET = "u2ME7KqVTfu7S6BLosJsyQ"
NUM_WORKERS = 50
BATCH_SIZE = 500
TICK_INTERVAL = 60 # 60 segundos = 1 minuto

# NOVO: URL pública do próprio servidor para mantê-lo acordado.
# Será lida a partir das variáveis de ambiente do Render.
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
# ==============================================================================

# --- Configurações Iniciais ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- Estrutura de Gerenciamento de Trabalhos ---
ACTIVE_JOBS = {}
JOBS_LOCK = threading.Lock()

# --- Variáveis Globais (cidades, etc.) ---
city_names = []
city_to_ip_map = {}
default_keywords = ["vinheta", "anuncio", "propaganda", "carro de som", "audio"]
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1"
]
backlink_sites = ["https://www.globo.com", "https://www.uol.com.br", "https://www.terra.com.br"]

# ==============================================================================
# >> FUNÇÕES DE GERAÇÃO DE VISITA (sem alterações) <<
# ==============================================================================
def load_cities_from_file():
    global city_names, city_to_ip_map
    try:
        with open('cities.json', 'r', encoding='utf-8') as f: city_names = list(set(json.load(f)))
        city_to_ip_map = {city: f"189.5.{i // 256}.{i % 256}" for i, city in enumerate(city_names)}
        logging.info(f"✅ Carregadas {len(city_names)} cidades.")
    except Exception as e:
        logging.critical(f"❌ ERRO CRÍTICO ao carregar 'cities.json': {e}")

def get_referrer(traffic_type, keyword):
    if traffic_type == "organic": return f"https://www.google.com.br/search?q={keyword.replace(' ', '+')}"
    if traffic_type == "social": return random.choice(["https://www.facebook.com/", "https://t.co/", "https://www.instagram.com/"])
    if traffic_type == "backlink": return random.choice(backlink_sites)
    return "https://www.exemplo-referencia.com"

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None):
    if not city_names: return
    try:
        city = random.choice(city_names)
        keyword = random.choice(keywords) if keywords else random.choice(default_keywords)
        traffic_type_final = fixed_traffic_type if fixed_traffic_type else random.choice(["organic", "social", "backlink", "reference"])
        
        event_data = {
            "client_id": str(uuid.uuid4()),
            "events": [{
                "name": "page_view",
                "params": {
                    "page_location": URL_DO_SEU_SITE, "page_title": NOME_DO_SEU_SITE,
                    "engagement_time_msec": str(random.randint(40000, 120000)),
                    "session_id": str(uuid.uuid4()), "ip_override": city_to_ip_map.get(city),
                    "user_agent_override": random.choice(user_agents),
                    "document_referrer": get_referrer(traffic_type_final, keyword),
                    "city": city, "region": "BR", "traffic_source": traffic_type_final
                }
            }]
        }
        ga_url = f"https://www.google-analytics.com/mp/collect?measurement_id={analytics_id}&api_secret={GA_API_SECRET}"
        ga_response = requests.post(ga_url, json=event_data, timeout=20, verify=False)
        if ga_response.status_code not in [200, 204]:
             logging.warning(f"⚠️ Falha ao enviar evento p/ GA ({ga_response.status_code}): {ga_response.text}")

    except Exception as e:
        logging.error(f"❌ Erro ao gerar visita: {e}")

# ==============================================================================
# >> ARQUITETURA DE PROCESSAMENTO EM LOTES (COM DESPERTADOR) <<
# ==============================================================================
def run_visit_batch(job_id, analytics_id, keywords, traffic_type, visits_to_run):
    logging.info(f"Iniciando lote para Job '{job_id}': gerando {visits_to_run} visitas.")
    task_queue = queue.Queue()
    for _ in range(visits_to_run): task_queue.put(None)

    def worker():
        while not task_queue.empty():
            try:
                task_queue.get()
                gerar_visita(analytics_id, keywords, traffic_type)
                task_queue.task_done()
            except Exception: pass
    
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(NUM_WORKERS)]
    for t in threads: t.start()
    task_queue.join()
    logging.info(f"Lote para Job '{job_id}' concluído.")

def job_scheduler_tick():
    """Função que roda a cada X segundos para verificar jobs E manter o servidor acordado."""
    while True:
        # --- Parte 1: Manter o servidor acordado ---
        # NOVO: Adicionado o "despertador"
        if RENDER_EXTERNAL_URL:
            try:
                # Faz uma requisição a si mesmo para resetar o timer de inatividade do Render
                requests.get(RENDER_EXTERNAL_URL, timeout=10)
                logging.info("Ping 'keep-alive' enviado para si mesmo com sucesso.")
            except Exception as e:
                logging.warning(f"Falha ao enviar o ping 'keep-alive': {e}")
        
        # --- Parte 2: Processar os trabalhos agendados ---
        with JOBS_LOCK:
            if not ACTIVE_JOBS:
                logging.info("Nenhum trabalho ativo. Aguardando...")
            else:
                for job_id, job_details in list(ACTIVE_JOBS.items()):
                    if job_details['processed'] < job_details['total']:
                        remaining = job_details['total'] - job_details['processed']
                        visits_for_this_batch = min(remaining, BATCH_SIZE)
                        job_details['processed'] += visits_for_this_batch
                        
                        logging.info(f"Agendando novo lote para Job '{job_id}'. Progresso: {job_details['processed']}/{job_details['total']}")
                        
                        batch_thread = threading.Thread(target=run_visit_batch, args=(job_id, job_details['analytics_id'], job_details['keywords'], job_details['traffic_type'], visits_for_this_batch))
                        batch_thread.start()
                    else:
                        logging.info(f"✅ Trabalho '{job_id}' concluído! Removendo da fila.")
                        del ACTIVE_JOBS[job_id]
        
        time.sleep(TICK_INTERVAL)

# ==============================================================================
# >> ROTAS DA API <<
# ==============================================================================
@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api():
    try:
        data = request.get_json(force=True)
        total_visits = int(data.get("totalVisits", 100))
        analytics_id = data.get("analyticsId")
        keywords = data.get("keywords")
        if not all([analytics_id, keywords]): return jsonify({"error": "analyticsId e keywords são obrigatórios."}), 400

        job_id = str(uuid.uuid4())
        with JOBS_LOCK:
            ACTIVE_JOBS[job_id] = { "total": total_visits, "processed": 0, "analytics_id": analytics_id, "keywords": keywords, "traffic_type": data.get("trafficType") }
        
        logging.info(f"Novo trabalho agendado com ID '{job_id}' para {total_visits} visitas.")
        return jsonify({"message": f"Trabalho para gerar {total_visits} visitas foi agendado com sucesso.", "job_id": job_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "Traffic Server v_despertador (Keep-Alive) está online."

# ==============================================================================
# >> INICIALIZAÇÃO DO SERVIDOR <<
# ==============================================================================
if __name__ != '__main__':
    load_cities_from_file()
    scheduler_thread = threading.Thread(target=job_scheduler_tick, daemon=True)
    scheduler_thread.start()
    logging.info("🚀 Servidor iniciado e agendador com despertador está ativo.")