from util import *
import socket
import os
import multiprocessing

dynamic_port_list = list(range(9000, 9099))
dynamic_port_available = [False] * 100


def dynamic_port():
    for i in range(100):
        if not dynamic_port_available[i]:
            dynamic_port_available[i] = True
            return dynamic_port_list[i]
    return -1


def handle_client(client_socket, client_address):
    port = dynamic_port()
    if port == -1:
        return
    command = (
        f"C:/Users/33543/miniconda3/envs/comp-net-proj/python.exe "
        f"c:/Data/University/Study/Junior_First/computer_network/project/conf_client.py "
        f"-p {port} -r True"
    )
    client_socket.sendall(f"HTTP/1.1 302 Found\r\nLocation: http://10.20.147.91:{port}/conference\r\n\r\n".encode())
    client_socket.close()
    os.system(command)


def start_socket_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("10.20.147.91", 8886))
    server_socket.listen(10)
    print("Listening on 10.20.147.91:8886")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"Accepted connection from {client_address}")
        # create a process to handle the client
        process = multiprocessing.Process(target=handle_client, args=(client_socket, client_address))
        process.start()


if __name__ == "__main__":
    start_socket_server()

# 还有bug，而且还要remote传输音视频流，先别搞了
