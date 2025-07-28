import redis
import threading
import json
import time

# Conexão com o Redis
# decode_responses=True garante que as respostas do Redis venham como strings
try:
    r = redis.Redis(decode_responses=True)
    r.ping() # Verifica se a conexão foi bem-sucedida
    print("[INFO] Conexão com o Redis bem-sucedida!")
except redis.exceptions.ConnectionError as e:
    print(f"[ERRO] Não foi possível conectar ao Redis: {e}")
    exit()

# Variáveis globais para armazenar o ID e nome da empresa logada
my_id = None
my_name = None

def listen_for_redis_messages():
    """Escuta mensagens nos canais do Redis em uma thread separada."""
    pubsub = r.pubsub()
    # A empresa se inscreve em seu próprio canal para receber mensagens de chat
    pubsub.subscribe(f"chat:{my_id}")

    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                # As mensagens são enviadas e recebidas como objetos JSON
                data = json.loads(message['data'])
                remetente = data['remetente_nome']
                texto = data['texto']
                print(f"\n[NOVA MENSAGEM de {remetente}]: {texto}")
            except (json.JSONDecodeError, KeyError):
                print(f"\n[INFO] Recebida notificação: {message['data']}")

def print_menu():
    print("\n--- Menu da Empresa ---")
    print("1. Postar nova vaga")
    print("2. Ver candidatos de uma vaga")
    print("3. Aprovar candidato para chat")
    print("4. Gerenciar Chats (Ver histórico e Enviar mensagem)")
    print("5. Sair")
    print("-----------------------")

def start_client():
    global my_id, my_name

    nome_empresa = input("Digite o nome da sua empresa: ")
    
    # Login de empresa com Redis
    # Busca se a empresa já existe. Se não, cria um novo ID.
    existing_id = r.get(f"empresa:nome:{nome_empresa}")
    if existing_id:
        my_id = existing_id
    else:
        my_id = str(r.incr("next_empresa_id"))
        r.set(f"empresa:nome:{nome_empresa}", my_id)
        r.hset(f"empresa:{my_id}", "nome", nome_empresa)
        
    my_name = nome_empresa
    print(f"Login realizado com sucesso! Bem-vinda, {my_name} (ID: {my_id})!")

    # Inicia a thread para escutar mensagens do Redis
    thread = threading.Thread(target=listen_for_redis_messages, daemon=True)
    thread.start()

    while True:
        print_menu()
        escolha = input("Digite sua escolha: ")
        #Postar Vaga
        if escolha == '1':
            titulo = input("Digite o título da vaga: ")
            desc = input("Digite a descrição da vaga: ")
            vaga_id = str(r.incr("next_vaga_id"))
            r.hset(f"vaga:{vaga_id}", mapping={
                "titulo": titulo,
                "desc": desc,
                "empresa_id": my_id,
                "empresa_nome": my_name
            })
            print(f"INFO: Vaga '{titulo}' postada com sucesso (ID: {vaga_id})")
        #Ver candidatos a vaga
        elif escolha == '2':
            vaga_id = input("Digite o ID da vaga para ver os candidatos: ")
            candidatos_ids = r.smembers(f"candidaturas:{vaga_id}")
            print("\n--- Candidatos para a Vaga ---")
            if not candidatos_ids:
                print("  Nenhum candidato no momento.")
            else:
                for cand_id in candidatos_ids:
                    cand_name = r.hget(f"candidato:{cand_id}", "nome") or "Desconhecido"
                    print(f"  - ID: {cand_id}, Nome: {cand_name}")
            print("------------------------------")
        #aprovar candidato
        elif escolha == '3':
            vaga_id = input("Digite o ID da vaga: ")
            candidato_id = input("Digite o ID do candidato que deseja aprovar: ")
            if r.exists(f"vaga:{vaga_id}") and r.sismember(f"candidaturas:{vaga_id}", candidato_id):
                # Libera o chat para ambos os lados
                r.sadd(f"chats:{my_id}", candidato_id)
                r.sadd(f"chats:{candidato_id}", my_id)
                
                # Notifica o candidato via Pub/Sub
                nome_vaga = r.hget(f"vaga:{vaga_id}", "titulo")
                candidato_nome = r.hget(f"candidato:{candidato_id}", "nome")
                notificacao = f"Parabéns, {candidato_nome}! Você foi aprovado para a vaga '{nome_vaga}'. O chat com a empresa '{my_name}' está liberado."
                r.publish(f"notifications:{candidato_id}", notificacao)
                
                print(f"INFO: Chat liberado com o candidato {candidato_nome} (ID: {candidato_id}).")

            else:
                # Se a verificação falhar, informa o erro ao usuário.
                print("ERRO: O ID da vaga não existe ou o candidato informado não se aplicou para esta vaga.")
        #Mostra os chats disponiveis 
        elif escolha == '4':
            chats_aprovados_ids = r.smembers(f"chats:{my_id}")
            print("\n--- Chats Disponíveis ---")
            if not chats_aprovados_ids:
                print("  Nenhum chat disponível.")
                continue

            for partner_id in chats_aprovados_ids:
                partner_name = r.hget(f"candidato:{partner_id}", "nome") or "Desconhecido"
                print(f"  - ID: {partner_id}, Nome: {partner_name}")
            print("-------------------------")

            dest_id = input("Digite o ID do candidato para conversar (ou enter para voltar): ")
            if not dest_id:
                continue

            # Mostra o histórico
            chat_key = f"chat:hist:{frozenset((my_id, dest_id))}"
            historico = r.lrange(chat_key, 0, -1)
            print("\n--- Histórico do Chat ---")
            if not historico:
                print("  (Nenhuma mensagem anterior)")
            else:
                for msg_json in historico:
                    msg = json.loads(msg_json)
                    print(f"  [{msg['remetente_nome']}]: {msg['texto']}")
            print("-------------------------")

            # Envia nova mensagem
            mensagem_texto = input("Digite sua mensagem: ")
            if mensagem_texto:
                mensagem_obj = {
                    "remetente_id": my_id,
                    "remetente_nome": my_name,
                    "texto": mensagem_texto
                }
                # Publica no canal de chat do destinatário
                r.publish(f"chat:{dest_id}", json.dumps(mensagem_obj))
                # Salva no histórico compartilhado
                r.rpush(chat_key, json.dumps(mensagem_obj))
        
        elif escolha == '5':
            print("Encerrando...")
            break
        else:
            print("Opção inválida.")
        time.sleep(0.5)

if __name__ == "__main__":
    start_client()