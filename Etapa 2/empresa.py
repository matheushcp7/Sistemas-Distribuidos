import socket
import threading
import time

HOST = '127.0.0.1'
PORT = 65432

#Variáveis de Controle de Thread
chat_list_received = threading.Event()
# Variável para saber se a lista de chats veio vazia
chat_list_was_empty = False 

def listen_for_server_messages(sock):
    """Escuta mensagens do servidor em uma thread separada do cliente empresa. 
    Ou seja, mesmo quando estiver digitando aparecerá a notificação de uma nova mensagem"""
    global chat_list_received, chat_list_was_empty 
    
    while True:
        try:
            message = sock.recv(2048).decode('utf-8')
            if not message:
                print("\n[INFO] Desconectado do servidor.")
                break
            
            cleaned_message = message.strip()
            if not cleaned_message:
                continue

            # Separa apenas o comando do resto da mensagem
            parts = cleaned_message.split(';', 1)
            command = parts[0].strip()

            if command in ("INFO", "ERRO"):
                print(f"\n[SERVIDOR] {parts[1]}")
            elif command == "NOTIFICACAO_APROVADO":
                print(f"\n[SERVIDOR] {parts[1]}")
            elif command == "CANDIDATOS_LIST":
                print("\n--- Candidatos para a Vaga ---")
                candidatos_str = parts[1].strip(',')
                if not candidatos_str:
                    print("  Nenhum candidato no momento.")
                else:
                    for c in candidatos_str.split(','):
                        if c: print(f"  - {c}")
                print("------------------------------")
            elif command == "CHATS_LIST":
                print("\n--- Chats Aprovados ---")
                chats_str = ""
                if len(parts) > 1:
                    chats_str = parts[1].strip(',')
                
                if not chats_str:
                    print("  Nenhum chat ativo.")
                    chat_list_was_empty = True 
                else:
                    chat_list_was_empty = False 
                    for c in chats_str.split(','):
                        if c: print(f"  - {c}")
                print("-------------------------")
                chat_list_received.set() 

            #Lógica para receber e exibir o histórico do chat
            elif command == "HISTORICO_CHAT":
                print("\n--- Histórico do Chat ---")
                if len(parts) > 1 and parts[1]:
                    # Mensagens são separadas por '|||'
                    mensagens_hist = parts[1].split('|||')
                    for msg_data in mensagens_hist:
                        # Cada mensagem tem o formato "NomeRemetente;Texto"
                        sender_name, text = msg_data.split(';', 1)
                        print(f"  [{sender_name}]: {text}")
                else:
                    print("  (Nenhuma mensagem anterior)")
                print("-------------------------")

            elif command == "CHAT_RECEBIDO":
                #Garante que a mensagem completa seja exibida
                remetente, msg = parts[1].split(';', 1)
                print(f"\n[CHAT de {remetente}]: {msg}")
            else:
                 print(f"\n[DEBUG] Comando não reconhecido: {message}")

        except ConnectionResetError:
            print("\n[ERRO] A conexão foi forçadamente fechada pelo servidor.")
            break
        except Exception as e:
            print(f"\n[ERRO] Conexão perdida ou erro no processamento: {e}")
            break

def print_menu():
    print("\n--- Menu da Empresa ---")
    print("1. Postar nova vaga")
    print("2. Ver candidatos de uma vaga")
    print("3. Aprovar candidato para chat")
    print("4. Gerenciar Chats (Ver histórico e Enviar mensagem)")
    print("5. Sair")
    print("-----------------------")

def start_client():
    global chat_list_received, chat_list_was_empty
    # Cria um soquete para a empresa TCP IPV4
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # cria a conexão da empresa com o servidor
        client_socket.connect((HOST, PORT))
    except ConnectionRefusedError:
        print("[ERRO] Não foi possível conectar ao servidor. Ele está online?")
        return

    nome_empresa = input("Digite o nome da sua empresa: ")
    client_socket.sendall(f"LOGIN_EMP;{nome_empresa}".encode('utf-8'))
    
    try:
        """
        a empresa para e aguarda a confirmação do servidor para saber se o login foi bem-sucedido.
        .recv faz a empresa parar até receber a confirmação do servidor

        """
        login_response = client_socket.recv(1024).decode('utf-8')
    except ConnectionResetError:
        print("[ERRO] O servidor encerrou a conexão durante o login.")
        return

    if login_response.startswith("LOGIN_OK"):
        my_id, my_name = login_response.split(';')[1:3]
        print(f"Login realizado com sucesso! Bem-vinda, {my_name} (ID: {my_id})!")
    else:
        print("Falha no login.")
        client_socket.close()
        return

    thread = threading.Thread(target=listen_for_server_messages, args=(client_socket,), daemon=True)
    thread.start()

    while True:
        print_menu()
        escolha = input("Digite sua escolha: ")

        if escolha == '1':
            titulo = input("Digite o título da vaga: ")
            desc = input("Digite a descrição da vaga: ")
            client_socket.sendall(f"POST_VAGA;{titulo};{desc}".encode('utf-8'))
        
        elif escolha == '2':
            vaga_id = input("Digite o ID da vaga para ver os candidatos: ")
            client_socket.sendall(f"VER_CANDIDATURAS;{vaga_id}".encode('utf-8'))
        
        elif escolha == '3':
            vaga_id = input("Digite o ID da vaga: ")
            candidato_id = input("Digite o ID do candidato que deseja aprovar: ")
            client_socket.sendall(f"APROVAR;{vaga_id};{candidato_id}".encode('utf-8'))
        
        # MODIFICADO: A opção 4 agora busca o histórico antes de enviar a mensagem
        elif escolha == '4':
            """
            clear = "reset" que garante que o mecanismo de sincronização funcione corretamente toda vez que
              a operação for executada, e não apenas na primeira.
            """
            chat_list_received.clear()
            client_socket.sendall("LISTAR_CHATS".encode('utf-8'))
            
            print("\nCarregando sua lista de chats...")
            received = chat_list_received.wait(timeout=3)

            if not received:
                 print("Não foi possível carregar a lista (o servidor não respondeu a tempo).")
                 continue
            
            if chat_list_was_empty:
                time.sleep(1)
                continue

            dest_id = input("Digite o ID do candidato para ver o chat e enviar mensagem (ou enter para voltar): ")
            if not dest_id.strip():
                continue
            
            # Pede o histórico ao servidor
            client_socket.sendall(f"GET_HISTORICO;{dest_id}".encode('utf-8'))
            time.sleep(0.5) # Pausa para o histórico ser recebido e impresso na outra thread

            # Pede a nova mensagem
            mensagem = input(f"Digite sua mensagem para o candidato {dest_id} (ou enter para voltar): ")
            if mensagem:
                client_socket.sendall(f"CHAT_MSG;{dest_id};{mensagem}".encode('utf-8'))

        elif escolha == '5':
            print("Encerrando conexão...")
            break
        
        else:
            print("Opção inválida. Tente novamente.")
        
        time.sleep(0.5)

    client_socket.close()

if __name__ == "__main__":
    start_client()