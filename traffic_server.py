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
import queue

# ==============================================================================
# >> ÁREA DE CONFIGURAÇÃO <<
# ==============================================================================
URL_DO_SEU_SITE = "https://gravacaodevinheta.com.br"
NOME_DO_SEU_SITE = "Gravação de Vinheta"
GA_API_SECRET = "u2ME7KqVTfu7S6BLosJsyQ"
NUM_WORKERS = 50  # Número de trabalhadores simultâneos por lote
# NOVO: Define o tamanho de cada lote de visitas a ser processado por vez.
BATCH_SIZE = 500
# NOVO: Define o intervalo (em segundos) entre a verificação de lotes.
TICK_INTERVAL = 60 # 60 segundos = 1 minuto
# ==============================================================================

# --- Configurações Iniciais ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- Estrutura para Gerenciamento de Trabalhos em Background ---
# NOVO: Dicionário para armazenar os trabalhos ativos.
ACTIVE_JOBS = {}
# NOVO: Lock para garantir que o acesso ao dicionário de jobs seja seguro entre threads.
JOBS_LOCK = threading.Lock()

# --- Variáveis Globais para os dados carregados ---
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
        city_names = []

def get_referrer(traffic_type, keyword):
    if traffic_type == "organic": return f"https://www.google.com.br/search?q={keyword.replace(' ', '+')}"
    if traffic_type == "social": return random.choice(["https://www.facebook.com/", "https://t.co/", "https://www.instagram.com/"])
    if traffic_type == "backlink": return random.choice(backlink_sites)
    return "https://www.exemplo-referencia.com"

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None):
    if not city_names: return
    try:
        city = random.choice(city_names)
        event_data = {
            "client_id": str(uuid.uuid4()),
            "events": [{
                "name": "page_view",
                "params": {
                    "page_location": URL_DO_SEU_SITE, "page_title": NOME_DO_SEU_SITE,
                    "engagement_time_msec": str(random.randint(40000, 120000)),
                    "session_id": str(uuid.uuid4()), "ip_override": city_to_ip_map.get(city),
                    "user_agent_override": random.choice(user_agents),
                    "document_referrer": get_referrer(fixed_traffic_type if fixed_traffic_type else random.choice(["organic", "social", "backlink", "reference"]), random.choice(keywords) if keywords else random.choice(default_keywords)),
                    "city": city, "region": "BR"
                }
            }]
        }
        ga_url = f"https://www.google-analytics.com/mp/collect?measurement_id={analytics_id}&api_secret={GA_API_SECRET}"
        requests.post(ga_url, json=event_data, timeout=20, verify=False)
    except Exception as e:
        logging.error(f"❌ Erro ao gerar visita: {e}")

# ==============================================================================
# >> NOVA ARQUITETURA DE PROCESSAMENTO EM LOTES <<
# ==============================================================================

def run_visit_batch(job_id, analytics_id, keywords, traffic_type, visits_to_run):
    """Executa um lote específico de visitas usando um pool de workers."""
    logging.info(f"Iniciando lote para Job '{job_id}': gerando {visits_to_run} visitas.")
    
    task_queue = queue.Queue()
    for _ in range(visits_to_run):
        task_queue.put(None)

    def worker():
        while not task_queue.empty():
            try:
                task_queue.get()
                gerar_visita(analytics_id, keywords, traffic_type)
                task_queue.task_done()
            except Exception as e:
                logging.error(f"Erro no worker do lote: {e}")
    
    threads = []
    for _ in range(NUM_WORKERS):
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        threads.append(thread)
    
    task_queue.join()
    logging.info(f"Lote para Job '{job_id}' concluído.")

def job_scheduler_tick():
    """Função que roda a cada X segundos para verificar e processar os jobs."""
    while True:
        with JOBS_LOCK:
            # Itera sobre uma cópia para poder modificar o dicionário original
            for job_id, job_details in list(ACTIVE_JOBS.items()):
                if job_details['processed'] < job_details['total']:
                    
                    remaining = job_details['total'] - job_details['processed']
                    visits_for_this_batch = min(remaining, BATCH_SIZE)
                    
                    # Atualiza o contador ANTES de iniciar, para não agendar o mesmo lote duas vezes
                    job_details['processed'] += visits_for_this_batch
                    
                    logging.info(f"Agendando novo lote para Job '{job_id}'. Progresso: {job_details['processed']}/{job_details['total']}")
                    
                    # Inicia a execução do lote em uma nova thread para não bloquear o scheduler
                    batch_thread = threading.Thread(target=run_visit_batch, args=(
                        job_id,
                        job_details['analytics_id'],
                        job_details['keywords'],
                        job_details['traffic_type'],
                        visits_for_this_batch
                    ))
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
    """Esta rota agora apenas agenda o trabalho e retorna imediatamente."""
    try:
        data = request.get_json(force=True)
        total_visits = int(data.get("totalVisits", 100))
        analytics_id = data.get("analyticsId")
        keywords = data.get("keywords")
        traffic_type = data.get("trafficType")

        if not all([analytics_id, keywords]):
            return jsonify({"error": "analyticsId e keywords são obrigatórios."}), 400

        job_id = str(uuid.uuid4())
        
        with JOBS_LOCK:
            ACTIVE_JOBS[job_id] = {
                "total": total_visits,
                "processed": 0,
                "analytics_id": analytics_id,
                "keywords": keywords,
                "traffic_type": traffic_type
            }
        
        logging.info(f"Novo trabalho agendado com ID '{job_id}' para {total_visits} visitas.")
        return jsonify({"message": f"Trabalho para gerar {total_visits} visitas foi agendado com sucesso.", "job_id": job_id})

    except Exception as e:
        logging.error(f"Erro ao agendar trabalho: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "Traffic Server v_lotes (Batch Scheduler) está online."

# ==============================================================================
# >> INICIALIZAÇÃO DO SERVIDOR <<
# ==============================================================================
if __name__ != '__main__':
    load_cities_from_file()
    # Inicia a thread do "gerente" (scheduler) quando o servidor inicia.
    scheduler_thread = threading.Thread(target=job_scheduler_tick)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    logging.info("🚀 Servidor iniciado e agendador de lotes está ativo.")