import uuid  # generating unique conference IDs
from util import *
from flask import Flask, request, jsonify
from datetime import datetime
import threading
import socket
import struct
import time
import json


class ConferenceServer:
    def __init__(self, conference_id, data_ports, host_id, server_ip):
        """
        Initialize a ConferenceServer instance.
        :param conference_id: Unique identifier for the conference.
        :param clients_info: Initial client information.
        """
        self.server_ip = server_ip
        self.conference_id = conference_id
        self.data_ports = data_ports
        self.host_id = host_id

        self.clients_info = {}

        self.types = ["info", "control", "msg", "audio", "camera", "screen"]

        self.tcps = {
            "info": dict(),
            "control": dict(),
            "msg": dict(),
            "audio": dict(),
            "camera": dict(),
            "screen": dict(),
        }

        self.socks = {
            "info": socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            "control": socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            "msg": socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            "audio": socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            "camera": socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            "screen": socket.socket(socket.AF_INET, socket.SOCK_STREAM),
        }

        self.mode = "Client-Server"  # Default mode
        self.running = True
        self.printer(
            "info", f"Conference {self.conference_id} is created by {self.host_id}"
        )

    def receive_object(self, connection, length):
        object = b""
        while len(object) < length:
            packet = b""
            packet += connection.recv(length - len(object))
            if not packet:
                break
            object += packet
        return object

    def unpack_object(self, data):
        object_length = struct.unpack(">I", data[:4])[0]
        object_time = struct.unpack(">d", data[4:12])[0]
        object_id = struct.unpack(">16s", data[12:28])[0]
        object_ip = struct.unpack(">4s", data[28:32])[0]
        return object_length, object_time, object_id, object_ip

    def handle_data(self, reader, writer, data_type):
        """
        Receive streaming data from a client and forward it to other participants.
        :param reader: TCP/UDP socket for receiving data.
        :param writer: TCP/UDP socket for sending data.
        :param data_type: Type of data being handled (msg, screen, camera, or audio).
        """
        try:
            if data_type == "info":
                pass
            elif data_type == "control":
                while self.running:
                    data = reader.recv(12)
                    if not data:
                        break
                    control_message = struct.unpack(">I", data[:4])[0]
                    if control_message == 1:
                        # Forward the control message to all other clients
                        for client_conn in self.tcps[data_type].values():
                            client_conn.send(data)
                    elif control_message == 2:
                        # Forward the control message to all other clients
                        for client_conn in self.tcps[data_type].values():
                            client_conn.send(data)
            elif data_type == "msg":
                while self.running:
                    data = reader.recv(BUFFER_SIZE)
                    if not data:
                        break
                    for client_conn in self.tcps[data_type].values():
                        client_conn.send(data)
            elif data_type == "audio":
                while self.running:
                    header = self.receive_object(reader, HEADER_LENGTH)
                    if not header:
                        break
                    audio_length, audio_time, audio_id, audio_ip = self.unpack_object(
                        header
                    )
                    audio_data = self.receive_object(reader, audio_length)
                    for client_conn in self.tcps[data_type].values():
                        # if client_conn == reader:  # debug only
                        if client_conn != reader:  # Don't send back to the sender
                            client_conn.send(header)
                            client_conn.send(audio_data)
            elif data_type == "screen":
                while self.running:
                    header = self.receive_object(reader, HEADER_LENGTH)
                    if not header:
                        break
                    screen_length, screen_time, screen_id, screen_ip = (
                        self.unpack_object(header)
                    )
                    screen_data = self.receive_object(reader, screen_length)
                    for client_conn in self.tcps[data_type].values():
                        client_conn.send(header)
                        client_conn.send(screen_data)
            elif data_type == "camera":
                while self.running:
                    header = self.receive_object(reader, HEADER_LENGTH)
                    if not header:
                        break
                    camera_length, camera_time, camera_id, camera_ip = (
                        self.unpack_object(header)
                    )
                    data = self.receive_object(reader, camera_length)
                    for client_conn in self.tcps[data_type].values():
                        client_conn.send(header)
                        client_conn.send(data)
            else:
                self.printer("warning", f"Unknown data type: {data_type}")
        except Exception as e:
            if self.running:
                self.printer("error", f"Error in handle_data: {str(e)} for", data_type)

    def boardcast_client_info(self):
        """
        Boardcast client info to all clients.
        """
        self.printer(
            "info",
            f"Broadcasting client info to {len(self.tcps['info'])} clients",
            "info",
        )
        for client_conn in self.tcps["info"].values():
            try:
                client_conn.send(json.dumps(self.clients_info).encode())
            except Exception as e:
                self.printer("error", f"Error in boardcast: {str(e)}", "info")

    def cancel_conference(self):
        """
        Gracefully close all client TCP connections when the conference ends.
        """
        self.running = False

        self.printer("info", "Closing all TCPs and sockets...")

        for tcp in self.tcps.values():
            for conn in tcp.values():
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                finally:
                    conn.close()

        for sock in self.socks.values():
            sock.close()

        self.printer("warning", f"Conference {self.conference_id} has been cancelled.")

    def quit_conference(self, client_addr):
        """
        Quit conference: Remove a client from the specified ConferenceServer.
        :param client_id: Unique identifier of the client leaving the conference.
        :return: Dictionary with the result (success or error).
        """
        all_connections = self.which_type_tcp("all")

        for conn_dict in all_connections:
            for client_id in conn_dict:
                conn = conn_dict[client_id]
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                finally:
                    conn.close()
                    del conn_dict[client_addr]
                    self.printer(
                        "info", f"Connection with {client_addr} closed and removed."
                    )

        self.clients_info.pop(client_addr)

        self.printer("info", f"Client {client_addr} has left the conference.")

    def accept_connections(self, sock, sock_type):
        while self.running:
            try:
                client_conn, client_addr = sock.accept()
                self.printer(
                    "info",
                    f"Connection established with {client_addr[0]}:{client_addr[1]} for",
                    sock_type,
                )

                self.tcps[sock_type][client_addr] = client_conn
                threading.Thread(
                    target=self.handle_data,
                    args=(client_conn, self.tcps[sock_type], sock_type),
                    daemon=True,
                ).start()

            except Exception as e:
                if not self.running:
                    break
                self.printer(
                    "error", f"Error in accept_connection: {str(e)} for", sock_type
                )

    def printer(self, state, message, type=""):
        if state == "info":
            print(
                f"[{self.conference_id}] \033[32m{message}\033[0m \033[36m{(type)}\033[0m"
            )
        elif state == "error":
            print(
                f"[{self.conference_id}] \033[31m{message}\033[0m \033[36m{(type)}\033[0m"
            )
        elif state == "warning":
            print(
                f"[{self.conference_id}] \033[33m{message}\033[0m \033[36m{(type)}\033[0m"
            )
        else:
            print(f"[{self.conference_id}] {message}")

    def start(self):

        for sock_type in self.types:
            self.socks[sock_type].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socks[sock_type].bind((self.server_ip, self.data_ports[sock_type]))
            self.socks[sock_type].listen(5)
            self.printer(
                "info",
                f"Listening on {self.server_ip}:{self.data_ports[sock_type]} for",
                sock_type,
            )

        for sock_type in self.types:
            threading.Thread(
                target=self.accept_connections,
                args=(self.socks[sock_type], sock_type),
                daemon=True,
            ).start()

        # Keep main thread alive
        while self.running:
            time.sleep(1)


class MainServer:
    def __init__(self, server_ip, main_port, conf_ports):
        """
        Initialize MainServer instance.
        :param server_ip: The IP address where the server will run.
        :param main_port: The port number for the main server.
        """
        self.server_ip = server_ip
        self.server_port = main_port
        self.conf_ports = conf_ports
        self.main_server = None
        self.conference_servers = {}  # dict conference_id: ConferenceServer
        self.app = Flask(__name__)
        self.setup_routes()

    def generate_conference_id(self):
        """
        Generate a unique conference ID using UUID.
        :return: A unique 8-digit string ID.
        """
        return str(uuid.uuid4().int)[:8]

    def setup_routes(self):
        @self.app.route("/create_conference", methods=["POST"])
        def handle_creat_conference():
            """
            Create a new conference: Initialize and start a new ConferenceServer instance.
            :return: A dictionary with {status, message, conference_id, ports}.
            """
            data = request.get_json()
            client_ip = data["client_ip"]
            client_id = data["id"]
            conf_id = self.generate_conference_id()
            self.conference_servers[conf_id] = ConferenceServer(
                conf_id, self.conf_ports, client_id, self.server_ip
            )
            threading.Thread(target=self.conference_servers[conf_id].start).start()
            return jsonify(
                {
                    "status": "success",
                    "conference_id": conf_id,
                    "ports": self.conf_ports,
                }
            )

        @self.app.route("/join_conference/<conference_id>", methods=["POST"])
        def handle_join_conference(conference_id):
            """
            Join conference: Search corresponding conference_info and ConferenceServer,
            and reply necessary info to client.
            :param conference_id: The ID of the conference the client wants to join.
            :return: Dictionary with the result (success or error).
            """
            data = request.get_json()
            client_username = data["username"]
            client_ip = request.remote_addr
            client_id = data["id"]

            if conference_id not in self.conference_servers:
                return (
                    jsonify({"status": "error", "message": "Conference not found"}),
                    404,
                )

            if client_id in self.conference_servers[conference_id].clients_info.keys():
                return (
                    jsonify({"status": "error", "message": "Client already joined"}),
                    400,
                )

            conf_server = self.conference_servers[conference_id]
            conf_server.clients_info[client_id] = {
                "username": client_username,
                "join_time": getCurrentTime(),
            }

            # print(conf_server.clients_info)
            conf_server.boardcast_client_info()
            return jsonify(
                {
                    "status": "success",
                    "conference_id": conference_id,
                    "clients": conf_server.clients_info,
                }
            )

        @self.app.route("/quit_conference/<conference_id>", methods=["POST"])
        def handle_quit_conference(conference_id):
            """
            Quit conference: Remove a client from the specified ConferenceServer. If the client is the host, cancel the conference.
            """
            if conference_id in self.conference_servers:
                client_id = request.get_json()["id"]
                conf_server = self.conference_servers[conference_id]

                if client_id == conf_server.host_id:
                    # quit & cancel
                    conf_server.cancel_conference()
                    del self.conference_servers[conference_id]

                else:
                    # quit
                    conf_server.quit_conference(client_id)

                conf_server.boardcast_client_info()

                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "Client has left the conference",
                        }
                    ),
                    200,
                )
            else:
                return (
                    jsonify({"status": "error", "message": "Conference not found"}),
                    404,
                )

    def start(self):
        """
        start MainServer
        """
        self.app.run(host=self.server_ip, port=self.server_port)


if __name__ == "__main__":

    server = MainServer(SERVER_IP_LOCAL, MAIN_SERVER_PORT, CONF_SERVE_PORTS)
    server.start()
