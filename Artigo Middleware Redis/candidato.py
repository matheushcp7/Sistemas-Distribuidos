import redis
import threading
import json
import time

# Conexão com o Redis
try:
    r = redis.Redis(decode_responses=True)
    r.ping()
    print("[INFO] Conexão com o Redis bem-sucedida!")
except redis.exceptions.ConnectionError as e:
    print(f"[ERRO] Não foi possível conectar ao Redis: {e}")
    exit()

my_id = None
my_name = None

def listen_for_redis_messages():
    """Escuta mensagens nos canais do Redis em uma thread separada."""
    global my_id
    if not my_id:
        return

    pubsub = r.pubsub()
    # O candidato se inscreve em seu canal de notificações e de chat
    pubsub.subscribe(f"notifications:{my_id}")
    pubsub.subscribe(f"chat:{my_id}")
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            channel = message['channel']
            
            # Tenta decodificar como JSON (para mensagens de chat)
            try:
                data = json.loads(message['data'])
                remetente = data['remetente_nome']
                texto = data['texto']
                print(f"\n[NOVA MENSAGEM de {remetente}]: {texto}")
            except (json.JSONDecodeError, TypeError):
                # Se não for JSON, trata como notificação de texto simples
                print(f"\n[NOTIFICAÇÃO]: {message['data']}")


def print_menu():
    print("\n--- Menu do Candidato ---")
    print("1. Ver vagas disponíveis")
    print("2. Candidatar-se a uma vaga")
    print("3. Enviar mensagem no chat (após aprovação)")
    print("4. Sair")
    print("---------------------------")

def start_client():
    global my_id, my_name

    nome_candidato = input("Digite o seu nome: ")

    # --- Login de candidato com Redis ---
    existing_id = r.get(f"candidato:nome:{nome_candidato}")
    if existing_id:
        my_id = existing_id
    else:
        my_id = str(r.incr("next_candidato_id"))
        r.set(f"candidato:nome:{nome_candidato}", my_id)
        r.hset(f"candidato:{my_id}", "nome", nome_candidato)

    my_name = nome_candidato
    print(f"Login realizado com sucesso! Boa sorte, {my_name} (ID: {my_id})!")

    thread = threading.Thread(target=listen_for_redis_messages, daemon=True)
    thread.start()

    while True:
        print_menu()
        escolha = input("Digite sua escolha: ")
        #Ver vagas disponíveis
        if escolha == '1':
            vaga_ids = r.keys("vaga:*")
            print("\n--- Vagas Disponíveis ---")
            if not vaga_ids:
                print("Nenhuma vaga disponível no momento.")
            else:
                for vaga_key in vaga_ids:
                    vaga_id = vaga_key.split(":")[1]
                    vaga_info = r.hgetall(vaga_key)
                    print(f"  - ID:{vaga_id}, Vaga:'{vaga_info.get('titulo','')}', Empresa:'{vaga_info.get('empresa_nome','')}'")
            print("-------------------------")
        #Candidatar-se a uma vaga
        elif escolha == '2':
            vaga_id = input("Digite o ID da vaga para se candidatar: ")
            if r.exists(f"vaga:{vaga_id}"):
                # sadd retorna 1 se o item foi adicionado, 0 se já existia
                if r.sadd(f"candidaturas:{vaga_id}", my_id):
                    print("INFO: Você se candidatou com sucesso!")
                else:
                    print("ERRO: Você já se candidatou para esta vaga.")
            else:
                print("ERRO: Vaga não existe.")
        #Enviar mensagem no chat (após aprovação)
        elif escolha == '3':
            chats_aprovados_ids = r.smembers(f"chats:{my_id}")
            if not chats_aprovados_ids:
                print("Você precisa ser aprovado em uma vaga para usar o chat.")
                continue
            
            print("\n--- Chats Disponíveis ---")
            for partner_id in chats_aprovados_ids:
                partner_name = r.hget(f"empresa:{partner_id}", "nome") or "Desconhecido"
                print(f"  - ID: {partner_id}, Empresa: {partner_name}")
            print("-------------------------")
            
            dest_id = input("Digite o ID da empresa para conversar (ou enter para voltar): ")
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

        elif escolha == '4':
            print("Encerrando...")
            break
        else:
            print("Opção inválida. Tente novamente.")
        time.sleep(0.5)

if __name__ == "__main__":
    start_client()