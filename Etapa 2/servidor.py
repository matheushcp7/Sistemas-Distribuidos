import socket
import threading
import itertools

# --- Configurações do Servidor ---
HOST = '127.0.0.1'
PORT = 65432

# --- Arrays de Memória ---
clients = {}
vagas = {}
candidaturas = {}
chats_aprovados = {}
chat_historicos = {}

#Cria a "Fechadura"(objeto) da porta para dois individuos não alterarem dados em uma thread ao mesmo tempo
lock = threading.Lock()

# --- Geradores de ID ---
id_client_gen = itertools.count()
id_vaga_gen = itertools.count()

"""
    Função executada por uma thread para cada cliente conectado.
    Gerencia todas as comunicações com aquele cliente.
"""
def handle_client(conn, addr):
    print(f"[NOVA CONEXÃO] {addr} conectado.")
    client_id = str(next(id_client_gen))
    client_type = None
    client_name = None

    try:
        while True:
            data = conn.recv(2048).decode('utf-8')
            if not data:
                break

            parts = data.strip().split(';')
            command = parts[0]

            with lock:
                # --- Comandos de Login ---
                if command == "LOGIN_EMP":
                    client_type = 'empresa'
                    client_name = parts[1]
                    clients[client_id] = (conn, client_type, client_name)
                    """
                    .sendall() garante que toda a mensagem chegue ao destinatario, (por estar usando TCP)
                    """
                    conn.sendall(f"LOGIN_OK;{client_id};{client_name}".encode('utf-8'))
                    print(f"[LOGIN] Empresa '{client_name}' (ID: {client_id}) logou.")

                elif command == "LOGIN_CAN":
                    client_type = 'candidato'
                    client_name = parts[1]
                    clients[client_id] = (conn, client_type, client_name)
                    conn.sendall(f"LOGIN_OK;{client_id};{client_name}".encode('utf-8'))
                    print(f"[LOGIN] Candidato '{client_name}' (ID: {client_id}) logou.")

                # --- Comandos da Empresa ---
                elif command == "POST_VAGA":
                    if client_type == 'empresa':
                        vaga_id = str(next(id_vaga_gen))
                        titulo, desc = parts[1], parts[2]
                        vagas[vaga_id] = {'titulo': titulo, 'desc': desc, 'empresa_id': client_id}
                        candidaturas[vaga_id] = []
                        conn.sendall(f"INFO;Vaga '{titulo}' postada com sucesso (ID: {vaga_id})".encode('utf-8'))
                        print(f"[VAGA] Empresa '{client_name}' postou a vaga '{titulo}'.")

                elif command == "VER_CANDIDATURAS":
                     if client_type == 'empresa':
                        vaga_id = parts[1]
                        if vaga_id in vagas and vagas[vaga_id]['empresa_id'] == client_id:
                            lista_candidatos_id = candidaturas.get(vaga_id, [])
                            if not lista_candidatos_id:
                                conn.sendall("INFO;Nenhum candidato para esta vaga.".encode('utf-8'))
                            else:
                                resposta = "CANDIDATOS_LIST;"
                                for cand_id in lista_candidatos_id:
                                    """
                                    _,_, cand_name = desempacota o cliente e pega apenas o nome dele e descarta o restante do dicionario 
                                    """
                                    _, _, cand_name = clients.get(cand_id, (None, None, "Desconhecido"))
                                    resposta += f"{cand_id}:{cand_name},"
                                conn.sendall(resposta.encode('utf-8'))
                        else:
                            conn.sendall("ERRO;Vaga não encontrada ou não pertence a você.".encode('utf-8'))

                elif command == "APROVAR":
                    if client_type == 'empresa':
                        vaga_id, candidato_id = parts[1], parts[2]
                        if vaga_id in vagas and vagas[vaga_id]['empresa_id'] == client_id and candidato_id in candidaturas.get(vaga_id, []):
                            """"setdefault(client_id, set()) verifica se a empresa (client_id) 
                            já tem uma entrada no dicionário chats_aprovados; se não, cria uma 
                            com um conjunto (set) vazio. Em seguida, .add(candidato_id) adiciona o
                              ID do candidato a esse conjunto, liberando o chat entre eles."""
                            chats_aprovados.setdefault(client_id, set()).add(candidato_id)
                            chats_aprovados.setdefault(candidato_id, set()).add(client_id)
                            
                            conn.sendall(f"INFO;Chat liberado com o candidato {clients[candidato_id][2]} (ID: {candidato_id}).".encode('utf-8'))
                            
                            conn_candidato = clients[candidato_id][0]
                            nome_vaga = vagas[vaga_id]['titulo']
                            conn_candidato.sendall(f"NOTIFICACAO_APROVADO;{client_id};Você foi aprovado para a vaga '{nome_vaga}'! O chat com a empresa '{client_name}' está liberado.".encode('utf-8'))
                            print(f"[CHAT] Chat liberado entre '{client_name}' e '{clients[candidato_id][2]}'.")
                        else:
                            conn.sendall("ERRO;Não foi possível aprovar. Verifique os IDs.".encode('utf-8'))

                # --- Comandos do Candidato ---
                elif command == "LISTAR_VAGAS":
                    if not vagas:
                        conn.sendall("INFO;Nenhuma vaga disponível no momento.".encode('utf-8'))
                    else:
                        resposta = "VAGAS_LIST;"
                        for vaga_id, info in vagas.items():
                            empresa_nome = clients.get(info['empresa_id'], (None, None, "Empresa Desconhecida"))[2]
                            resposta += f"ID:{vaga_id}, Vaga:'{info['titulo']}', Empresa:'{empresa_nome}' | "
                        conn.sendall(resposta.encode('utf-8'))

                elif command == "APLICAR":
                    if client_type == 'candidato':
                        vaga_id = parts[1]
                        if vaga_id in vagas and client_id not in candidaturas.get(vaga_id, []):
                            candidaturas[vaga_id].append(client_id)
                            conn.sendall(f"INFO;Você se candidatou com sucesso para a vaga '{vagas[vaga_id]['titulo']}'".encode('utf-8'))
                            print(f"[APLICAÇÃO] Candidato '{client_name}' aplicou para a vaga ID {vaga_id}.")
                        else:
                            conn.sendall("ERRO;Vaga não existe ou você já se candidatou.".encode('utf-8'))
                
                # --- Comandos de Chat (geral) ---
                elif command == "LISTAR_CHATS":
                    if client_type == 'empresa':
                        chat_partners = chats_aprovados.get(client_id, set())
                        resposta = "CHATS_LIST;" 
                        if chat_partners:
                            for partner_id in chat_partners:
                                _, _, partner_name = clients.get(partner_id, (None, None, "Desconhecido"))
                                resposta += f"{partner_id}:{partner_name},"
                        conn.sendall(resposta.encode('utf-8'))
                
                # Comando para buscar o histórico de um chat específico
                elif command == "GET_HISTORICO":
                    if len(parts) >= 2:
                        partner_id = parts[1]
                        # A chave do chat é um frozenset para que a ordem dos IDs não importe
                        chat_key = frozenset((client_id, partner_id))
                        
                        historico = chat_historicos.get(chat_key, [])
                        # Envia o histórico como uma string, com mensagens separadas por '|||'
                        resposta = "HISTORICO_CHAT;" + "|||".join(historico)
                        conn.sendall(resposta.encode('utf-8'))
                
                elif command == "CHAT_MSG":
                    if len(parts) >= 3:
                        dest_id = parts[1]
                        mensagem = ';'.join(parts[2:]) # Remonta a mensagem original ignorando ; se existir
                        
                        if client_id in chats_aprovados and dest_id in chats_aprovados.get(client_id, set()):
                            #frozenset indica que a ordem não importa(client_id,dest_id) ou (dest_id,client_id)
                            chat_key = frozenset((client_id, dest_id))
                            # Garante que a lista de histórico exista e adiciona a nova mensagem
                            chat_historicos.setdefault(chat_key, []).append(f"{client_name};{mensagem}")

                            # Envia a mensagem para o destinatário
                            if dest_id in clients:
                                conn_dest, _, _ = clients[dest_id]
                                conn_dest.sendall(f"CHAT_RECEBIDO;{client_name};{mensagem}".encode('utf-8'))
                                print(f"[CHAT] De '{client_name}' para '{clients[dest_id][2]}': {mensagem}")
                            else:
                                 conn.sendall("ERRO;O destinatário parece estar offline.".encode('utf-8'))
                        else:
                            conn.sendall("ERRO;O chat com este usuário não está liberado.".encode('utf-8'))
                    else:
                        conn.sendall("ERRO;Formato de mensagem inválido.".encode('utf-8'))

    except Exception as e:
        print(f"[ERRO] Erro com {addr}: {e}")
    finally:
        with lock:
            if client_id in clients:
                print(f"[DESCONECTADO] {client_name} ({addr}) desconectou.")
                
                if client_id in chats_aprovados:
                    partners = chats_aprovados.pop(client_id)
                    for partner_id in partners:
                        if partner_id in chats_aprovados:
                            chats_aprovados[partner_id].discard(client_id)

                del clients[client_id]
        conn.close()

def start_server():
    #cria o socket do servidor de comunicação TCP(SOCK_STREAM) com IPV4(AF_INET)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #associa o socket a um endereço(HOST (endereço proprio desse computador)) e porta(PORT) específicos
    server_socket.bind((HOST, PORT))
    #coloca o socket em modo de escuta
    server_socket.listen()
    print(f"[ESCUTANDO] Servidor está escutando em {HOST}:{PORT}")

    while True:
        """
        .accept: O servidor para nessa linha e fica esperando até que um cliente tente se conectar.Quando um cliente se conecta, a função "acorda" e retorna o conn e o addr:
        conn: Um novo objeto de socket, que representa a conexão direta e exclusiva com aquele cliente específico
        addr: Um par de valores contendo o endereço IP e a porta do cliente que se conectou.
        """
        conn, addr = server_socket.accept()
        """
        thread: Em vez de lidar com o cliente no loop principal (o que o impediria de aceitar outros),
        ele cria uma nova thread (uma linha de execução paralela)
        target=handle_client: Define que a função a ser executada nesta nova thread é a handle_client.
        args=(conn, addr): Diz que os argumentos passados para a função handle_client
        são os objetos conn e addr que acabamos de receber do .accept()
        """
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        #inicia a thread em segundo plano
        thread.start()

if __name__ == "__main__":
    start_server()