import socket
import threading
import time

HOST = '127.0.0.1'
PORT = 65432
# Dicionário para armazenar com quem o chat está ativo (ID da empresa)
chat_partner_id = None

def listen_for_server_messages(sock):
    """Escuta mensagens do servidor em uma thread separada."""
    global chat_partner_id
    while True:
        try:
            
            message = sock.recv(2048).decode('utf-8')
            if not message:
                print("\n[INFO] Desconectado do servidor.")
                break
            
            # Separa apenas o comando do resto da mensagem
            parts = message.split(';', 1)
            command = parts[0]

            if command in ("INFO", "ERRO"):
                print(f"\n[SERVIDOR] {parts[1]}")
            elif command == "NOTIFICACAO_APROVADO":
                #pega o id do "parceiro", nesse caso da empresa e a mensagem da notificação da empresa
                _, partner_id_recv, mensagem_notificacao = message.split(';', 2)
                chat_partner_id = partner_id_recv
                print(f"\n[PARABÉNS!] {mensagem_notificacao}")
            elif command == "VAGAS_LIST":
                print("\n--- Vagas Disponíveis ---")
                vagas_str = parts[1]
                if "Nenhuma vaga" in vagas_str:
                    print(vagas_str)
                else:
                    vagas_lista = vagas_str.strip().split(' | ')
                    for v in vagas_lista:
                        if v: print(f"  - {v}")
                print("-------------------------")

            # Lógica para receber e exibir o histórico do chat
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
                # MODIFICADO: Garante que a mensagem completa seja exibida
                remetente, msg = parts[1].split(';', 1)
                print(f"\n[CHAT de {remetente}]: {msg}")
            else:
                print(f"\n[DEBUG] {message}")

        except Exception as e:
            print(f"\n[ERRO] Conexão perdida ou erro: {e}")
            break

def print_menu():
    print("\n--- Menu do Candidato ---")
    print("1. Ver vagas disponíveis")
    print("2. Candidatar-se a uma vaga")
    print("3. Enviar mensagem no chat (após aprovação)")
    print("4. Sair")
    print("---------------------------")

def start_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((HOST, PORT))
    except ConnectionRefusedError:
        print("[ERRO] Não foi possível conectar ao servidor. Ele está online?")
        return

    nome_candidato = input("Digite o seu nome: ")
    client_socket.sendall(f"LOGIN_CAN;{nome_candidato}".encode('utf-8'))
    
    try:
        login_response = client_socket.recv(1024).decode('utf-8')
    except ConnectionResetError:
        print("[ERRO] O servidor encerrou a conexão durante o login.")
        return

    if login_response.startswith("LOGIN_OK"):
        my_id, my_name = login_response.split(';')[1:3]
        print(f"Login realizado com sucesso! Boa sorte, {my_name} (ID: {my_id})!")
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
            client_socket.sendall("LISTAR_VAGAS".encode('utf-8'))
        
        elif escolha == '2':
            vaga_id = input("Digite o ID da vaga para se candidatar: ")
            client_socket.sendall(f"APLICAR;{vaga_id}".encode('utf-8'))
        
        # MODIFICADO: A opção 3 agora busca o histórico antes de enviar a mensagem
        elif escolha == '3':
            if not chat_partner_id:
                print("Você precisa ser aprovado em uma vaga para usar o chat.")
                continue
            
            # 1. Pede o histórico ao servidor
            client_socket.sendall(f"GET_HISTORICO;{chat_partner_id}".encode('utf-8'))
            time.sleep(0.5) # Pausa para o histórico ser recebido e impresso

            # 2. Pede a nova mensagem
            mensagem = input("Digite sua mensagem para a empresa (ou enter para voltar): ")
            if mensagem:
                client_socket.sendall(f"CHAT_MSG;{chat_partner_id};{mensagem}".encode('utf-8'))
            
        elif escolha == '4':
            print("Encerrando conexão...")
            break
            
        else:
            print("Opção inválida. Tente novamente.")

        time.sleep(0.5) # Pequena pausa para as mensagens do servidor chegarem

    client_socket.close()

if __name__ == "__main__":
    start_client()