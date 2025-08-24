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
import queue # NOVO: Importa a biblioteca de fila, essencial para o pool de workers

# ==============================================================================
# >> ÁREA DE CONFIGURAÇÃO <<
# ==============================================================================
URL_DO_SEU_SITE = "https://gravacaodevinheta.com.br"
NOME_DO_SEU_SITE = "Gravação de Vinheta"
GA_API_SECRET = "u2ME7KqVTfu7S6BLosJsyQ"
# NOVO: Define o número de trabalhadores simultâneos. 100 é um bom número para não sobrecarregar o Render.
NUM_WORKERS = 100 
# ==============================================================================

# --- Configurações Iniciais ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- Variáveis Globais para os dados carregados ---
city_names = []
city_to_ip_map = {}

# --- Listas de Dados Padrão ---
default_keywords = ["vinheta", "anuncio", "propaganda", "carro de som", "audio"]
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1"
]
backlink_sites = ["https://www.globo.com", "https://www.uol.com.br", "https://www.terra.com.br"]

# ==============================================================================
# >> FUNÇÃO DE CARREGAMENTO DE CIDADES <<
# ==============================================================================
def load_cities_from_file():
    """Carrega a lista de cidades do arquivo cities.json."""
    global city_names, city_to_ip_map
    try:
        with open('cities.json', 'r', encoding='utf-8') as f:
            city_names = list(set(json.load(f)))
        
        city_to_ip_map = {city: f"189.5.{i // 256}.{i % 256}" for i, city in enumerate(city_names)}
        logging.info(f"✅ Carregadas {len(city_names)} cidades do arquivo cities.json.")
        if not city_names:
            logging.critical("Lista de cidades está vazia! A simulação não pode continuar.")
            
    except FileNotFoundError:
        logging.critical("❌ ERRO CRÍTICO: Arquivo 'cities.json' não encontrado. Abortando.")
        city_names = []
    except Exception as e:
        logging.critical(f"❌ ERRO CRÍTICO ao carregar 'cities.json': {e}")
        city_names = []

# ==============================================================================

def get_referrer(traffic_type, keyword):
    if traffic_type == "organic": return f"https://www.google.com.br/search?q={keyword.replace(' ', '+')}"
    elif traffic_type == "social": return random.choice(["https://www.facebook.com/", "https://t.co/", "https://www.instagram.com/"])
    elif traffic_type == "backlink": return random.choice(backlink_sites)
    else: return "https://www.exemplo-referencia.com"

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None):
    """Gera um evento de visita e o envia diretamente para o Google Analytics."""
    if not city_names:
        logging.warning("Nenhuma cidade disponível, pulando geração de visita.")
        return

    try:
        city = random.choice(city_names)
        simulated_ip = city_to_ip_map.get(city)
        keyword = random.choice(keywords) if keywords else random.choice(default_keywords)
        traffic_type = fixed_traffic_type if fixed_traffic_type else random.choice(["organic", "social", "backlink", "reference"])
        referrer = get_referrer(traffic_type, keyword)
        
        session_cookie = str(uuid.uuid4())
        user_agent = random.choice(user_agents)
        engagement_time = random.randint(40000, 120000)

        event_data = {
            "client_id": str(random.randint(10**9, 10**10 - 1)),
            "events": [{
                "name": "page_view",
                "params": {
                    "page_location": URL_DO_SEU_SITE,
                    "page_title": NOME_DO_SEU_SITE,
                    "engagement_time_msec": str(engagement_time),
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
        
        ga_response = requests.post(ga_url, json=event_data, timeout=20)
        
        if ga_response.status_code in [200, 204]:
            logging.info(f"📊 Evento enviado p/ GA com IP de {city} ({simulated_ip}). Sucesso!")
        else:
            logging.warning(f"⚠️ Falha ao enviar evento p/ GA ({ga_response.status_code}): {ga_response.text}")

    except Exception as e:
        logging.error(f"❌ Erro inesperado durante a geração da visita: {e}")

# ==============================================================================
# >> ROTA DA API (TOTALMENTE REFEITA) <<
# ==============================================================================
@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api():
    try:
        data = request.get_json(force=True)
        
        # A função que cada um dos nossos trabalhadores (threads) irá executar
        def thread_worker(q, analytics_id, keywords, traffic_type):
            while not q.empty():
                try:
                    # Pega uma tarefa da fila
                    _ = q.get() 
                    gerar_visita(analytics_id, keywords, traffic_type)
                    # Marca a tarefa como concluída
                    q.task_done()
                    # Pequeno delay para não sobrecarregar a API do Google
                    time.sleep(random.uniform(0.1, 0.3))
                except Exception as e:
                    logging.error(f"Erro no worker: {e}")

        # A função principal que orquestra o trabalho em background
        def background_task_orchestrator():
            total_visits = int(data.get("totalVisits", 100))
            analytics_id = data.get("analyticsId")
            keywords = data.get("keywords")
            traffic_type = data.get("trafficType")

            if not analytics_id or not keywords:
                logging.error("analyticsId ou keywords faltando no payload.")
                return

            logging.info(f"Iniciando a geração de {total_visits} eventos com uma equipe de {NUM_WORKERS} workers.")
            
            # 1. Cria a fila de tarefas
            task_queue = queue.Queue()
            
            # 2. Preenche a fila com o número de visitas desejado
            for _ in range(total_visits):
                task_queue.put(None) # O item em si não importa, apenas a contagem

            # 3. Cria e inicia a equipe de trabalhadores (threads)
            threads = []
            for _ in range(NUM_WORKERS):
                thread = threading.Thread(target=thread_worker, args=(task_queue, analytics_id, keywords, traffic_type))
                thread.daemon = True # Permite que o programa principal saia mesmo se as threads estiverem rodando
                thread.start()
                threads.append(thread)

            # 4. Espera a fila esvaziar (todas as tarefas serem concluídas)
            task_queue.join()
            
            logging.info(f"✅ Geração de {total_visits} eventos concluída.")
            
        # Inicia o orquestrador em uma thread separada para não bloquear a resposta da API
        threading.Thread(target=background_task_orchestrator).start()
        
        return jsonify({"message": "Processo de geração de eventos iniciado com sucesso."})
    except Exception as e:
        logging.error(f"Erro na rota /api/gerar-trafego: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "Traffic Server v_final_estavel (IP Override & Worker Pool) está online."

# Carrega os dados do arquivo de cidades uma vez quando o servidor Gunicorn inicia.
if __name__ != '__main__':
    load_cities_from_file()