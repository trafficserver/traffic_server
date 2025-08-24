# Configuração do Gunicorn para rodar com um único processo e múltiplas threads.
# Isso garante que nossa variável global ACTIVE_JOBS seja compartilhada.

workers = 1
# O número de threads. 10 é um bom número para lidar com algumas requisições
# simultâneas enquanto o agendador trabalha em background.
threads = 10
# Aumenta o timeout do worker. Essencial para que o Gunicorn não mate o processo
# por inatividade entre os lotes. 300 segundos = 5 minutos.
timeout = 300