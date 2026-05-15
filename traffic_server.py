import logging
import random
import threading
import time
import uuid
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
import json
import queue

# ==============================================================================
# >> CONFIGURACAO <<
# ==============================================================================
URL_DO_SEU_SITE = "https://gravacaodevinheta.com.br"
NOME_DO_SEU_SITE = "Gravacao de Vinheta"
GA_API_SECRET = "u2ME7KqVTfu7S6BLosJsyQ"
NUM_WORKERS = 50
BATCH_SIZE = 500
TICK_INTERVAL = 60
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
# ==============================================================================

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

def create_resilient_session():
    session = requests.Session()
    retry_strategy = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    return session

http_session = create_resilient_session()

ACTIVE_JOBS = {}
JOBS_LOCK = threading.Lock()
SCHEDULER_STARTED = False

default_keywords = ["vinheta", "anuncio", "propaganda", "carro de som", "audio"]
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.43 Mobile Safari/537.36",
]
backlink_sites = ["https://www.globo.com", "https://www.uol.com.br", "https://www.terra.com.br"]

# ==============================================================================
# >> IPs REAIS BRASILEIROS POR ESTADO <<
# ==============================================================================
# Faixas de IP validas no Brasil, organizadas por estado
# Cada estado tem blocos /24 diferentes para aparecer como bolinhas separadas no mapa
IP_POR_ESTADO = {
    'SP': ['189.5.1.0', '189.5.2.0', '189.5.3.0', '189.5.4.0', '189.5.5.0',
           '191.6.10.0', '191.6.20.0', '191.6.30.0', '187.6.100.0', '187.6.200.0'],
    'RJ': ['189.5.10.0', '189.5.11.0', '189.5.12.0', '189.5.13.0', '189.5.14.0',
           '191.6.40.0', '191.6.50.0', '187.7.100.0', '187.7.150.0', '187.7.200.0'],
    'MG': ['189.5.20.0', '189.5.21.0', '189.5.22.0', '189.5.23.0', '189.5.24.0',
           '191.6.60.0', '191.6.70.0', '187.8.100.0', '187.8.150.0', '187.8.200.0'],
    'RS': ['189.5.30.0', '189.5.31.0', '189.5.32.0', '189.5.33.0', '189.5.34.0',
           '191.6.80.0', '191.6.90.0', '187.9.100.0', '187.9.150.0', '187.9.200.0'],
    'PR': ['189.5.40.0', '189.5.41.0', '189.5.42.0', '189.5.43.0', '189.5.44.0',
           '191.6.100.0', '191.6.110.0', '187.10.100.0', '187.10.150.0', '187.10.200.0'],
    'SC': ['189.5.50.0', '189.5.51.0', '189.5.52.0', '189.5.53.0', '189.5.54.0',
           '191.6.120.0', '191.6.130.0', '187.11.100.0', '187.11.150.0', '187.11.200.0'],
    'BA': ['189.5.60.0', '189.5.61.0', '189.5.62.0', '189.5.63.0', '189.5.64.0',
           '191.6.140.0', '191.6.150.0', '187.12.100.0', '187.12.150.0', '187.12.200.0'],
    'PE': ['189.5.70.0', '189.5.71.0', '189.5.72.0', '189.5.73.0', '189.5.74.0',
           '191.6.160.0', '191.6.170.0', '187.13.100.0', '187.13.150.0', '187.13.200.0'],
    'CE': ['189.5.80.0', '189.5.81.0', '189.5.82.0', '189.5.83.0', '189.5.84.0',
           '191.6.180.0', '191.6.190.0', '187.14.100.0', '187.14.150.0', '187.14.200.0'],
    'DF': ['189.5.90.0', '189.5.91.0', '189.5.92.0', '189.5.93.0', '189.5.94.0',
           '191.6.200.0', '191.6.210.0', '187.15.100.0', '187.15.150.0', '187.15.200.0'],
    'GO': ['189.5.100.0', '189.5.101.0', '189.5.102.0', '189.5.103.0', '189.5.104.0',
           '191.6.220.0', '191.6.230.0', '187.16.100.0', '187.16.150.0', '187.16.200.0'],
    'ES': ['189.5.110.0', '189.5.111.0', '189.5.112.0', '189.5.113.0', '189.5.114.0',
           '191.6.240.0', '191.6.250.0', '187.17.100.0', '187.17.150.0', '187.17.200.0'],
    'AM': ['189.5.120.0', '189.5.121.0', '189.5.122.0', '189.5.123.0', '189.5.124.0',
           '191.7.10.0', '191.7.20.0', '187.18.100.0', '187.18.150.0', '187.18.200.0'],
    'PA': ['189.5.130.0', '189.5.131.0', '189.5.132.0', '189.5.133.0', '189.5.134.0',
           '191.7.30.0', '191.7.40.0', '187.19.100.0', '187.19.150.0', '187.19.200.0'],
    'MA': ['189.5.140.0', '189.5.141.0', '189.5.142.0', '189.5.143.0', '189.5.144.0',
           '191.7.50.0', '191.7.60.0', '187.20.100.0', '187.20.150.0', '187.20.200.0'],
    'RN': ['189.5.150.0', '189.5.151.0', '189.5.152.0', '189.5.153.0', '189.5.154.0',
           '191.7.70.0', '191.7.80.0', '187.21.100.0', '187.21.150.0', '187.21.200.0'],
    'PB': ['189.5.160.0', '189.5.161.0', '189.5.162.0', '189.5.163.0', '189.5.164.0',
           '191.7.90.0', '191.7.100.0', '187.22.100.0', '187.22.150.0', '187.22.200.0'],
    'AL': ['189.5.170.0', '189.5.171.0', '189.5.172.0', '189.5.173.0', '189.5.174.0',
           '191.7.110.0', '191.7.120.0', '187.23.100.0', '187.23.150.0', '187.23.200.0'],
    'SE': ['189.5.180.0', '189.5.181.0', '189.5.182.0', '189.5.183.0', '189.5.184.0',
           '191.7.130.0', '191.7.140.0', '187.24.100.0', '187.24.150.0', '187.24.200.0'],
    'PI': ['189.5.190.0', '189.5.191.0', '189.5.192.0', '189.5.193.0', '189.5.194.0',
           '191.7.150.0', '191.7.160.0', '187.25.100.0', '187.25.150.0', '187.25.200.0'],
    'MT': ['189.5.200.0', '189.5.201.0', '189.5.202.0', '189.5.203.0', '189.5.204.0',
           '191.7.170.0', '191.7.180.0', '187.26.100.0', '187.26.150.0', '187.26.200.0'],
    'MS': ['189.5.210.0', '189.5.211.0', '189.5.212.0', '189.5.213.0', '189.5.214.0',
           '191.7.190.0', '191.7.200.0', '187.27.100.0', '187.27.150.0', '187.27.200.0'],
    'TO': ['189.5.220.0', '189.5.221.0', '189.5.222.0', '189.5.223.0', '189.5.224.0',
           '191.7.210.0', '191.7.220.0', '187.28.100.0', '187.28.150.0', '187.28.200.0'],
    'RO': ['189.5.230.0', '189.5.231.0', '189.5.232.0', '189.5.233.0', '189.5.234.0',
           '191.7.230.0', '191.7.240.0', '187.29.100.0', '187.29.150.0', '187.29.200.0'],
    'AC': ['189.5.240.0', '189.5.241.0', '189.5.242.0', '189.5.243.0', '189.5.244.0',
           '191.8.10.0', '191.8.20.0', '187.30.100.0', '187.30.150.0', '187.30.200.0'],
    'AP': ['189.5.245.0', '189.5.246.0', '189.5.247.0', '189.5.248.0', '189.5.249.0',
           '191.8.30.0', '191.8.40.0', '187.31.100.0', '187.31.150.0', '187.31.200.0'],
    'RR': ['189.5.250.0', '189.5.251.0', '189.5.252.0', '189.5.253.0', '189.5.254.0',
           '191.8.50.0', '191.8.60.0', '187.32.100.0', '187.32.150.0', '187.32.200.0'],
}

# Mapa de cidades para estados (capitais + cidades principais)
CIDADE_PARA_ESTADO = {
    'SP': ['Sao Paulo', 'Campinas', 'Santos', 'Ribeirao Preto', 'Sao Jose dos Campos',
           'Sorocaba', 'Jundiai', 'Piracicaba', 'Bauru', 'Sao Jose do Rio Preto'],
    'RJ': ['Rio de Janeiro', 'Niteroi', 'Duque de Caxias', 'Nova Iguacu', 'Campos dos Goytacazes',
           'Petropolis', 'Volta Redonda', 'Mage', 'Angra dos Reis', 'Teresopolis'],
    'MG': ['Belo Horizonte', 'Uberlandia', 'Contagem', 'Juiz de Fora', 'Uberaba',
           'Betim', 'Montes Claros', 'Ribeirao das Neves', 'Ipatinga', 'Divinopolis'],
    'RS': ['Porto Alegre', 'Caxias do Sul', 'Gravatai', 'Novo Hamburgo', 'Sao Leopoldo',
           'Pelotas', 'Canoas', 'Santa Maria', 'Passo Fundo', 'Bento Goncalves'],
    'PR': ['Curitiba', 'Londrina', 'Maringa', 'Ponta Grossa', 'Cascavel',
           'Sao Jose dos Pinhais', 'Foz do Iguacu', 'Colombo', 'Guarapuava', 'Paranagua'],
    'SC': ['Florianopolis', 'Joinville', 'Blumenau', 'Sao Jose', 'Criciuma',
           'Chapeco', 'Lages', 'Itajai', 'Jaragua do Sul', 'Palhoca'],
    'BA': ['Salvador', 'Feira de Santana', 'Ilheus', 'Vitoria da Conquista', 'Juazeiro',
           'Lauro de Freitas', 'Itabuna', 'Porto Seguro', 'Barreiras', 'Alagoinhas'],
    'PE': ['Recife', 'Olinda', 'Caruaru', 'Jaboatao dos Guararapes', 'Paulista',
           'Petrolina', 'Cabo de Santo Agostinho', 'Camaragibe', 'Garanhuns', 'Vitoria de Santo Antao'],
    'CE': ['Fortaleza', 'Juazeiro do Norte', 'Sobral', 'Caucaia', 'Maracanau',
           'Crato', 'Iguatu', 'Quixada', 'Pacajus', 'Aracati'],
    'DF': ['Brasilia', 'Taguatinga', 'Ceilandia', 'Samambaia', 'Planaltina',
           'Guara', 'Sobradinho', 'Gama', 'Santa Maria', 'Recanto das Emas'],
    'GO': ['Goiania', 'Anapolis', 'Luziania', 'Rio Verde', 'Aparecida de Goiania',
           'Caldas Novas', 'Itumbiara', 'Catalao', 'Jatai', 'Trindade'],
    'ES': ['Vitoria', 'Vila Velha', 'Serra', 'Cariacica', 'Linhares',
           'Colatina', 'Guarapari', 'Aracruz', 'Sao Mateus', 'Cachoeiro de Itapemirim'],
    'AM': ['Manaus', 'Parintins', 'Itacoatiara', 'Manacapuru', 'Coari',
           'Tabatinga', 'Maues', 'Tefe', 'Iranduba', 'Sao Gabriel da Cachoeira'],
    'PA': ['Belem', 'Ananindeua', 'Santarem', 'Maraba', 'Castanhal',
           'Sao Felix do Xingu', 'Barcarena', 'Tucurui', 'Parauapebas', 'Altamira'],
    'MA': ['Sao Luis', 'Imperatriz', 'Codo', 'Timom', 'Caxias',
           'Pinheiro', 'Santa Ines', 'Bacabal', 'Aracuai', 'Balsas'],
    'RN': ['Natal', 'Mossoro', 'Parnamirim', 'Santa Cruz', 'Ceara-Mirim',
           'Macau', 'Assu', 'Currais Novos', 'Caico', 'Pau dos Ferros'],
    'PB': ['Joao Pessoa', 'Camaragibe', 'Santa Rita', 'Patos', 'Bayeux',
           'Sousa', 'Cajazeiras', 'Cabedelo', 'Guarabira', 'Sapé'],
    'AL': ['Maceio', 'Arapiraca', 'Rio Largo', 'Palmeira dos Indios', 'Penedo',
           'Sao Miguel dos Campos', 'Coruripe', 'Campo Alegre', 'Teotonio Vilela', 'Uniao dos Palmares'],
    'SE': ['Aracaju', 'Itabaiana', 'Lagarto', 'Estancia', 'Propria',
           'Sao Cristovao', 'Nossa Senhora do Socorro', 'Tobias Barreto', 'Simao Dias', 'Nossa Senhora da Gloria'],
    'PI': ['Teresina', 'Parnaiba', 'Picos', 'Campo Maior', 'Floriano',
           'Oeiras', 'Cocal', 'Piripiri', 'Barras', 'Miguel Alves'],
    'MT': ['Cuiaba', 'Varzea Grande', 'Rondonopolis', 'Sinop', 'Tangara da Serra',
           'Caceres', 'Primavera do Leste', 'Barra do Garcas', 'Sorriso', 'Lucas do Rio Verde'],
    'MS': ['Campo Grande', 'Dourados', 'Tres Lagoas', 'Corumba', 'Ponta Pora',
           'Navirai', 'Nova Andradina', 'Aquidauana', 'Rio Brilhante', 'Amambai'],
    'TO': ['Palmas', 'Araguaina', 'Gurupi', 'Porto Nacional', 'Paraiso do Tocantins',
           'Colinas do Tocantins', 'Araguatins', 'Guarai', 'Tocantinopolis', 'Miracema do Tocantins'],
    'RO': ['Porto Velho', 'Ji-Parana', 'Ariquemes', 'Vilhena', 'Cacoal',
           'Rolim de Moura', 'Jaru', 'Pimenta Bueno', 'Guajara-Mirim', 'Ouro Preto do Oeste'],
    'AC': ['Rio Branco', 'Cruzeiro do Sul', 'Sena Madureira', 'Tarauaca', 'Feijo',
           'Brasileia', 'Epitaciolandia', 'Placido de Castro', 'Xapuri', 'Manoel Urbano'],
    'AP': ['Macapa', 'Santana', 'Laranjal do Jari', 'Oiapoque', 'Porto Grande',
           'Mazagao', 'Tartarugalzinho', 'Ferreira Gomes', 'Calcoene', 'Amapa'],
    'RR': ['Boa Vista', 'Caracarai', 'Normandia', 'Pacaraima', 'Mucajai',
           'Alto Alegre', 'Bonfim', 'Iracema', 'Cantá', 'Rorainopolis'],
}

def get_referrer(traffic_type, keyword):
    if traffic_type == "organic": return f"https://www.google.com.br/search?q={keyword.replace(' ', '+')}"
    if traffic_type == "social": return random.choice(["https://www.facebook.com/", "https://t.co/", "https://www.instagram.com/"])
    if traffic_type == "backlink": return random.choice(backlink_sites)
    return "https://www.exemplo-referencia.com"

def gerar_visita(analytics_id, keywords, fixed_traffic_type=None, regions=None):
    try:
        keyword = random.choice(keywords) if keywords else random.choice(default_keywords)
        traffic_type_final = fixed_traffic_type if fixed_traffic_type else random.choice(["organic", "social", "backlink", "reference"])
        
        # ========== ESCOLHER ESTADO E CIDADE ==========
        if regions and len(regions) > 0:
            # Filtra apenas estados validos
            estados_validos = [r for r in regions if r in IP_POR_ESTADO]
            if estados_validos:
                estado = random.choice(estados_validos)
            else:
                estado = random.choice(list(IP_POR_ESTADO.keys()))
        else:
            estado = random.choice(list(IP_POR_ESTADO.keys()))
        
        cidades = CIDADE_PARA_ESTADO.get(estado, ['Sao Paulo'])
        cidade = random.choice(cidades)
        
        # Pegar um IP real do estado
        ip_pool = IP_POR_ESTADO.get(estado, ['189.5.1.0'])
        base_ip = random.choice(ip_pool)
        # Variar o ultimo octeto para dar mais diversidade
        ip_override = f"{base_ip.rsplit('.', 1)[0]}.{random.randint(1, 254)}"
        
        # ========== MONTAR PAYLOAD GA4 (CORRETO!) ==========
        event_data = {
            "client_id": str(uuid.uuid4()),
            "ip_override": ip_override,  # <<< CORRETO: nivel raiz do payload
            "events": [{
                "name": "page_view",
                "params": {
                    "page_location": URL_DO_SEU_SITE,
                    "page_title": NOME_DO_SEU_SITE,
                    "engagement_time_msec": str(random.randint(40000, 120000)),
                    "session_id": str(uuid.uuid4()),
                    "user_agent_override": random.choice(user_agents),
                    "document_referrer": get_referrer(traffic_type_final, keyword),
                    "city": cidade,
                    "region": estado,
                    "country": "BR",
                    "traffic_source": traffic_type_final
                }
            }]
        }
        
        ga_url = f"https://www.google-analytics.com/mp/collect?measurement_id={analytics_id}&api_secret={GA_API_SECRET}"
        response = http_session.post(ga_url, json=event_data, timeout=15)
        response.raise_for_status()
        
    except Exception as e:
        logging.error(f"Erro persistente ao gerar visita: {e}")

def run_visit_batch(job_id, analytics_id, keywords, traffic_type, visits_to_run, regions=None):
    logging.info(f"Iniciando lote para Job '{job_id}': gerando {visits_to_run} visitas em {regions or 'todos estados'}.")
    task_queue = queue.Queue()
    for _ in range(visits_to_run): task_queue.put(None)
    
    def worker():
        while not task_queue.empty():
            try:
                task_queue.get_nowait()
                gerar_visita(analytics_id, keywords, traffic_type, regions)
                task_queue.task_done()
                time.sleep(random.uniform(0.1, 0.5))
            except queue.Empty: continue
            except Exception: pass
    
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(NUM_WORKERS)]
    for t in threads: t.start()
    task_queue.join()
    logging.info(f"Lote para Job '{job_id}' concluido.")

def job_scheduler_tick():
    while True:
        try:
            time.sleep(TICK_INTERVAL)
            if RENDER_EXTERNAL_URL: http_session.get(RENDER_EXTERNAL_URL, timeout=10)
            
            with JOBS_LOCK:
                if not ACTIVE_JOBS: continue
                for job_id, job_details in list(ACTIVE_JOBS.items()):
                    if job_details['processed'] < job_details['total']:
                        remaining = job_details['total'] - job_details['processed']
                        visits_for_this_batch = min(remaining, BATCH_SIZE)
                        job_details['processed'] += visits_for_this_batch
                        logging.info(f"Processando lote para Job '{job_id}'. Progresso: {job_details['processed']}/{job_details['total']}")
                        threading.Thread(target=run_visit_batch, args=(
                            job_id, job_details['analytics_id'], job_details['keywords'], 
                            job_details['traffic_type'], visits_for_this_batch, job_details.get('regions')
                        ), daemon=True).start()
                    else:
                        logging.info(f"Trabalho '{job_id}' concluido!")
                        del ACTIVE_JOBS[job_id]
        except Exception as e: logging.error(f"Erro no loop do scheduler: {e}")

def start_scheduler_if_not_running():
    global SCHEDULER_STARTED
    if not SCHEDULER_STARTED:
        threading.Thread(target=job_scheduler_tick, daemon=True).start()
        SCHEDULER_STARTED = True
        logging.info("Agendador de tarefas iniciado.")

@app.route('/api/gerar-trafego', methods=['POST'])
def gerar_trafego_api():
    try:
        data = request.get_json(force=True)
        total_visits = int(data.get("totalVisits", 100))
        analytics_id = data.get("analyticsId")
        if not analytics_id: return jsonify({"error": "analyticsId e obrigatorio."}), 400
        
        job_id = str(uuid.uuid4())
        regions = data.get("regions", None)
        
        with JOBS_LOCK:
            ACTIVE_JOBS[job_id] = {
                "total": total_visits,
                "processed": 0,
                "analytics_id": analytics_id,
                "keywords": data.get("keywords"),
                "traffic_type": data.get("trafficType"),
                "regions": regions
            }
        
        reg_msg = f" em {len(regions)} estados" if regions else ""
        logging.info(f"Novo trabalho '{job_id}' para {total_visits} visitas{reg_msg}.")
        return jsonify({"message": f"Trabalho para gerar {total_visits} visitas{reg_msg} foi agendado.", "job_id": job_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "Traffic Server v2 - Com correcao de IP por estado (bolinhas azuis)!"

# Inicia o scheduler na carga do modulo (funciona com gunicorn no Render)
start_scheduler_if_not_running()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
