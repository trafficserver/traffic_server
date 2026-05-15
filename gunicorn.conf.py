# Configuração do Gunicorn para rodar com um único processo e múltiplas threads.
workers = 1
threads = 10
timeout = 300

# NOVO: "Hook" do Gunicorn. Esta é a linha mais importante.
# Ela executa uma função logo após um worker ser inicializado.
def post_worker_init(worker):
    from traffic_server import start_scheduler_if_not_running
    start_scheduler_if_not_running()