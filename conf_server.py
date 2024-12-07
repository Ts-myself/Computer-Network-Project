import json
import uuid  # generating unique conference IDs
from util import *
from flask import Flask, request, jsonify
from datetime import datetime
import threading
import socket


class ConferenceServer:
    def __init__(self, conference_id, data_ports, host_ip, server_ip):
        """
        Initialize a ConferenceServer instance.
        :param conference_id: Unique identifier for the conference.
        :param conf_serve_ports: Ports allocated for the conference.
        :param clients_info: Initial client information.
        """
        self.server_ip = server_ip
        self.conference_id = conference_id
        self.conf_serve_ports = data_ports
        self.data_ports = data_ports  # map data_type to port
        self.host_ip = host_ip

        self.clients_info = {}

        self.client_tcps_msg = dict()  
        self.client_tcps_camera = dict()
        self.client_tcps_screen = dict()
        self.client_udps = set()  # set of client_addr

        self.mode = "Client-Server"  # Default mode
        self.running = True

    def handle_data(self, reader, writer, data_type):
        """
        Receive streaming data from a client and forward it to other participants.
        :param reader: TCP/UDP socket for receiving data.
        :param writer: TCP/UDP socket for sending data.
        :param data_type: Type of data being handled (msg, screen, camera, or audio).
        """
        if data_type == "msg":
            try:
                while self.running:
                    data = reader.recv(BUFFER_SIZE)
                    if not data:
                        break
                    print(f"Received message: {data.decode()}")
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
                    # Receive audio data via UDP
                    data, addr = reader.recvfrom(BIG_BUFFER_SIZE)

                    if addr not in self.client_udps:
                        self.client_udps.add(addr)
                        print(f"Added {addr} to client_udps")

                    # Forward the audio data to all other clients
                    for client_addr in self.client_udps:
                        if client_addr != addr:  # Don't send back to the sender
                            writer.sendto(data, client_addr)

            except Exception as e:
                print(f"[Error] Audio handling error: {str(e)}")
        elif data_type == "screen":
            try:
                while self.running:
                    # Receive camera data via TCP
                    # data = reader.recv(BIG_BUFFER_SIZE)
                    print(reader.getpeername())
                    header = reader.recv(4)
                    if not header:
                        break
                    import struct
                    frame_length = struct.unpack(">I", header)[0]
                    print(f"Received screen header: {frame_length} bytes")
                    data = reader.recv(frame_length)
                    print(f"Received screen data: {len(data)} bytes")
                    # Forward the camera data to all other clients
                    for client_conn in self.client_tcps_screen.values():
                        # if client_conn != reader:
                        client_conn.send(header)
                        client_conn.send(data)
                        print(f"Successfully forwarded camera data to {client_conn.getpeername()}")
            except Exception as e:
                print(f"[Error] Camera handling error: {str(e)}") 
        elif data_type == "camera":
            try:
                while self.running:
                    # Receive camera data via TCP
                    # data = reader.recv(BIG_BUFFER_SIZE)
                    print(reader.getpeername())
                    header = reader.recv(4)
                    if not header:
                        break
                    import struct
                    frame_length = struct.unpack(">I", header)[0]
                    print(f"Received camera header: {frame_length} bytes")
                    data = reader.recv(frame_length)
                    print(f"Received camera data: {len(data)} bytes")
                    # Forward the camera data to all other clients
                    for client_conn in self.client_tcps_camera.values():
                        # if client_conn != reader:
                        client_conn.send(header)
                        client_conn.send(data)
                        print(f"Successfully forwarded camera data to {client_conn.getpeername()}")
            except Exception as e:
                print(f"[Error] Camera handling error: {str(e)}")
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

    def cancel_conference(self):
        """
        Cancel the conference and disconnect all clients.
        """
        # try:
        #     self.running = False
        #     print(f"[INFO] Cancelling conference {self.conference_id}.")
        #     for client_id, client_writer in self.client_conns.items():
        #         client_writer.close()
        #         await client_writer.wait_closed()
        #     self.client_conns.clear()
        #     print(
        #         f"[INFO] Conference {self.conference_id} has been successfully cancelled."
        #     )
        # except Exception as e:
        #     print(f"[ERROR] Error while cancelling conference: {e}")

    def start(self):
        """
        Start the ConferenceServer and begin handling clients and data streams.
        """
        # message
        self.sock_msg = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Message server started at {self.server_ip}:{self.data_ports['msg']}")
        self.sock_msg.bind((self.server_ip, self.data_ports["msg"]))
        self.sock_msg.listen(5)

        # camera
        self.sock_camera = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Camera server started at {self.server_ip}:{self.data_ports['camera']}")
        self.sock_camera.bind((self.server_ip, self.data_ports["camera"]))
        self.sock_camera.listen(5)
        
        # screen
        self.sock_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Camera server started at {self.server_ip}:{self.data_ports['screen']}")
        self.sock_screen.bind((self.server_ip, self.data_ports["screen"]))
        self.sock_screen.listen(5) 

        # # audio
        # print(f"Audio server started at {self.server_ip}:{self.data_ports['audio']}")
        # self.sock_aud = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # self.sock_aud.bind((self.server_ip, self.data_ports["audio"]))

        # # Start audio handler thread
        # threading.Thread(
        #     target=self.handle_data,
        #     args=(self.sock_aud, self.sock_aud, "audio"),
        #     daemon=True,
        # ).start()

        while self.running:
            # Accept new TCP client for message handling
            client_conn, client_addr = self.sock_msg.accept()
            # self.client_tcps[client_addr] = client_conn
            self.client_tcps_msg[client_addr] = client_conn
            threading.Thread(target=self.handle_data, args=(client_conn, self.client_tcps_msg, "msg")).start()

            # Accept new TCP client for camera handling
            client_conn, client_addr = self.sock_camera.accept()
            # self.client_tcps[client_addr] = client_conn
            self.client_tcps_camera[client_addr] = client_conn
            threading.Thread(target=self.handle_data, args=(client_conn, self.client_tcps_camera, "camera")).start()
            
            # Accept new TCP client for screen handling
            client_conn, client_addr = self.sock_screen.accept()
            # self.client_tcps[client_addr] = client_conn
            self.client_tcps_screen[client_addr] = client_conn
            threading.Thread(target=self.handle_data, args=(client_conn, self.client_tcps_screen, "screen")).start()


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
        self.conference_servers = {}  # map conference_id to ConferenceServer
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
            client_ip = request.remote_addr
            conf_id = self.generate_conference_id()
            self.conference_servers[conf_id] = ConferenceServer(conf_id, self.conf_ports, client_ip, self.server_ip)
            threading.Thread(target=self.conference_servers[conf_id].start).start()
            print(f"[INFO] Created conference {conf_id} for {client_ip}")
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

            if conference_id not in self.conference_servers:
                return (
                    jsonify({"status": "error", "message": "Conference not found"}),
                    404,
                )

            client_ip = request.remote_addr

            if client_ip in self.conference_servers[conference_id].clients_info.keys():
                return (
                    jsonify({"status": "error", "message": "Client already joined"}),
                    400,
                )

            conf_server = self.conference_servers[conference_id]
            conf_server.clients_info[client_ip] = {"join_time": getCurrentTime()}

            print(conf_server.clients_info)
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
            Quit conference: Remove a client from the specified ConferenceServer.
            :param client_id: Unique identifier of the client leaving the conference.
            :param conference_id: The ID of the conference the client wants to leave.
            :return: Dictionary with the result (success or error).
            """
            if conference_id in self.conference_servers:
                client_ip = request.remote_addr
                conf_server = self.conference_servers[conference_id]
                conf_server.clients_info.pop(client_ip)
                print(conf_server.clients_info)
                return jsonify({"status": "success"})
            return jsonify({"status": "error", "message": "Conference not found"}), 404

        @self.app.route("/cancel_conference/<conference_id>", methods=["POST"])
        def handle_cancel_conference(conference_id):
            """
            Cancel conference: Close the specified ConferenceServer and notify all clients.
            :param conference_id: The ID of the conference to be canceled.
            :return: Dictionary with the result (success or error).
            """
            if conference_id not in self.conference_servers:
                return (
                    jsonify({"status": "error", "message": "Conference not found"}),
                    404,
                )

            # TODO
            # all_clients = self.conference_servers[conference_id].clients_info.keys()
            # for client_ip in all_clients:
            #     requests.post(f"{client_ip}/cancel_conference/{conference_id}")
            del self.conference_servers[conference_id]
            print(self.conference_servers)
            return jsonify({"status": "success"})

    def start(self):
        """
        start MainServer
        """
        self.app.run(host=self.server_ip, port=self.server_port)


if __name__ == "__main__":

    server = MainServer(SERVER_IP_LOCAL, MAIN_SERVER_PORT, CONF_SERVE_PORTS)
    server.start()
