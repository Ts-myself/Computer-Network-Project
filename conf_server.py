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

        self.client_tcps_info = dict()
        self.client_tcps_control = dict()
        self.client_tcps_msg = dict()
        self.client_tcps_camera = dict()
        self.client_tcps_screen = dict()
        self.client_tcps_audio = dict()

        self.sock_info = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_control = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_msg = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_camera = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.mode = "Client-Server"  # Default mode
        self.running = True

    def receive_object(self, connection, length):
        object = b""
        while len(object) < length:
            packet = b""
            packet += connection.recv(length - len(object))
            if not packet:
                print("Connection closed")
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
        if data_type == "info":
            pass
        elif data_type == "msg":
            try:
                while self.running:
                    data = reader.recv(BUFFER_SIZE)
                    if not data:
                        break
                    # print(f"Received message: {data.decode()}")
                    # Forward the message to all other clients
                    for client_conn in self.client_tcps_msg.values():
                        # if client_conn != reader:
                        # print(f"Forwarding message to {client_conn.getpeername()}")
                        client_conn.send(data)
                        # print(f"Successfully forwarded message to {client_conn.getpeername()}")
            except Exception as e:
                print(f"[Error] Message handling error: {str(e)}")
        elif data_type == "audio":
            try:
                while self.running:
                    header = self.receive_object(reader, HEADER_LENGTH)
                    if not header:
                        break
                    audio_length, audio_time, audio_id, audio_ip = self.unpack_object(
                        header
                    )
                    audio_data = self.receive_object(reader, audio_length)
                    # print(f"Received audio data: {len(audio_data)} bytes")
                    for client_conn in self.client_tcps_audio.values():
                        # if client_conn == reader:  # debug only
                        if client_conn != reader:  # Don't send back to the sender
                            client_conn.send(header)
                            client_conn.send(audio_data)
                            # print(f"Successfully forwarded audio data to {client_conn.getpeername()}")

            except Exception as e:
                print(f"[Error] Audio handling error: {str(e)}")
        elif data_type == "screen":
            try:
                while self.running:
                    header = self.receive_object(reader, HEADER_LENGTH)
                    if not header:
                        break
                    screen_length, screen_time, screen_id, screen_ip = (
                        self.unpack_object(header)
                    )
                    screen_data = self.receive_object(reader, screen_length)
                    # print(f"Received screen data: {len(screen_data)} bytes")
                    for client_conn in self.client_tcps_screen.values():
                        # if client_conn != reader:
                        client_conn.send(header)
                        client_conn.send(screen_data)
                        # print(f"Successfully forwarded camera data to {client_conn.getpeername()}")
            except Exception as e:
                print(f"[Error] Camera handling error: {str(e)}")
        elif data_type == "camera":
            try:
                while self.running:
                    header = self.receive_object(reader, HEADER_LENGTH)
                    if not header:
                        break
                    camera_length, camera_time, camera_id, camera_ip = (
                        self.unpack_object(header)
                    )
                    data = self.receive_object(reader, camera_length)
                    # print(f"Received camera data: {len(data)} bytes")
                    for client_conn in self.client_tcps_camera.values():
                        # if client_conn != reader:
                        client_conn.send(header)
                        client_conn.send(data)
                        # print(f"Successfully forwarded camera data to {client_conn.getpeername()}")
            except Exception as e:
                print(f"[Error] Camera handling error: {str(e)}")
        elif data_type == "control":
            try:
                while self.running:
                    header = self.receive_object(reader, HEADER_LENGTH)
                    if not header:
                        break
                    control_message, control_time, control_id, control_ip = (
                        self.unpack_object(header)
                    )
                    if control_message == 1:
                        for client_conn in self.client_tcps_control.values():
                            client_conn.send(header)
                            # print(f"Successfully forwarded control message to {client_conn.getpeername()}")
                    elif control_message == 2:
                        for client_conn in self.client_tcps_control.values():
                            client_conn.send(header)
                            # print(f"Successfully forwarded control message to {client_conn.getpeername()}")

            except Exception as e:
                print(f"[Error] Control handling error: {str(e)}")
        else:
            print(f"[Error] Invalid data type: {data_type}")

    def log(self):
        """
        Periodically log server status.
        """
        # try:vue
        #     while self.running:
        #         print(
        #             f"[INFO] Logging server status for conference {self.conference_id}:"
        #         )
        #         print(f"Connected clients: {list(self.client_conns.keys())}")
        #         await asyncio.sleep(5)  # Log every 5 seconds
        # except asyncio.CancelledError:
        #     print("[INFO] Logging task was cancelled.")
        # except Exception as e:
        #     print(f"[ERROR] Error in logging task: {e}")

    def boardcast_client_info(self):
        """
        Boardcast client info to all clients.
        """
        # print(f"[INFO] Broadcasting client info to {len(self.client_tcps_info)} clients")
        for client_conn in self.client_tcps_info.values():
            try:
                # print(f"[INFO] Sending to client: {client_conn.getpeername()}")
                client_conn.send(json.dumps(self.clients_info).encode())
                print(f"[INFO] Successfully sent to {client_conn.getpeername()}")
            except Exception as e:
                print(f"[ERROR] Failed to send to client {client_conn}: {str(e)}")

    def cancel_conference(self):
        """
        Gracefully close all client TCP connections when the conference ends.
        """
        self.running = False
        all_connections = self.which_type_tcp("all")

        for conn_dict in all_connections:
            for client_conn in conn_dict.values():
                try:
                    client_conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                finally:
                    client_conn.close()

        self.sock_info.close()
        self.sock_control.close()
        self.sock_msg.close()
        self.sock_audio.close()
        self.sock_camera.close()
        self.sock_screen.close()

        print("All TCP connections are closed and dictionaries are cleared.")

    def quit_conference(self, client_id):
        """
        Quit conference: Remove a client from the specified ConferenceServer.
        :param client_id: Unique identifier of the client leaving the conference.
        :return: Dictionary with the result (success or error).
        """
        all_connections = self.which_type_tcp("all")

        for conn_dict in all_connections:
            if client_id in conn_dict:
                conn = conn_dict[client_id]
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                finally:
                    conn.close()
                    del conn_dict[client_id]
                    print(f"Connection with {client_id} closed and removed.")

        self.clients_info.pop(client_id)

        print(f"[INFO] Client {client_id} has left the {self.conference_id}.")

    def accept_connections(self, sock, sock_type):
        """
        Handle accepting connections for a specific socket type
        """
        while self.running:
            try:
                client_conn, client_addr = sock.accept()
                print(f"[{self.conference_id}] accept {sock_type}")

                self.which_type_tcp(sock_type)[client_addr] = client_conn
                threading.Thread(
                    target=self.handle_data,
                    args=(client_conn, self.which_type_tcp(sock_type), sock_type),
                    daemon=True,
                ).start()

            except Exception as e:
                if not self.running:
                    break
                print(f"[Error] Error accepting {sock_type} connection: {str(e)}")

    def start(self):
        """
        Start the ConferenceServer and begin handling clients and data streams.
        """

        sock_types = ["info", "control", "msg", "audio", "camera", "screen"]

        for sock_type in sock_types:
            self.which_type_sock(sock_type).setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            print(
                f"{sock_type} server started at {self.server_ip}:{self.data_ports[sock_type]}"
            )
            self.which_type_sock(sock_type).bind(
                (self.server_ip, self.data_ports[sock_type])
            )
            self.which_type_sock(sock_type).listen(5)

        for sock_type in sock_types:
            threading.Thread(
                target=self.accept_connections,
                args=(self.which_type_sock(sock_type), sock_type),
                daemon=True,
            ).start()

        # Keep main thread alive
        while self.running:
            time.sleep(1)

    def which_type_tcp(self, type):
        if type == "info":
            return self.client_tcps_info
        if type == "control":
            return self.client_tcps_control
        if type == "msg":
            return self.client_tcps_msg
        if type == "audio":
            return self.client_tcps_audio
        if type == "camera":
            return self.client_tcps_camera
        if type == "screen":
            return self.client_tcps_screen
        if type == "all":
            return [
                self.client_tcps_info,
                self.client_tcps_control,
                self.client_tcps_msg,
                self.client_tcps_audio,
                self.client_tcps_camera,
                self.client_tcps_screen,
            ]
        else:
            print(f"[Error] Invalid socket type: {type}")
            return None

    def which_type_sock(self, type):
        if type == "info":
            return self.sock_info
        if type == "control":
            return self.sock_control
        if type == "msg":
            return self.sock_msg
        if type == "audio":
            return self.sock_audio
        if type == "camera":
            return self.sock_camera
        if type == "screen":
            return self.sock_screen
        if type == "all":
            return [
                self.sock_info,
                self.sock_control,
                self.sock_msg,
                self.sock_audio,
                self.sock_camera,
                self.sock_screen,
            ]
        else:
            print(f"[Error] Invalid socket type: {type}")
            return None


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
            print(f"[INFO] Created conference {conf_id} for {client_id}")
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

            print(conf_server.clients_info)
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

                    print(f"[INFO] Conference {conference_id} is deleted by the host.")
                    print(
                        f"[INFO] Current conferences: {self.conference_servers.keys()}"
                    )

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

    server = MainServer(SERVER_IP_PUBLIC_TJL, MAIN_SERVER_PORT, CONF_SERVE_PORTS)
    server.start()
