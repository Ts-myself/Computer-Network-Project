import asyncio
import json
import uuid  # generating unique conference IDs
from util import *
from flask import Flask, request, jsonify
from datetime import datetime
import requests


def getCurrentTime():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ConferenceServer:
    def __init__(self, conference_id, conf_serve_ports, host_ip):
        """
        Initialize a ConferenceServer instance.
        :param conference_id: Unique identifier for the conference.
        :param conf_serve_ports: Ports allocated for the conference.
        :param clients_info: Initial client information.
        """
        self.conference_id = conference_id
        self.conf_serve_ports = conf_serve_ports
        self.data_serve_ports = {
            data_type: port
            for data_type, port in zip(["screen", "camera", "audio"], conf_serve_ports)
        }  # map data_type to port
        self.data_types = ["screen", "camera", "audio"]

        self.host_ip = host_ip
        self.clients_info = {}
        # self.client_conns = {}
        self.mode = "Client-Server"  # Default mode
        self.running = True

    async def handle_data(self, reader, writer, data_type):
        """
        Receive streaming data from a client and forward it to other participants.
        :param reader: asyncio StreamReader instance for receiving data.
        :param writer: asyncio StreamWriter instance for sending data.
        :param data_type: Type of data being handled (screen, camera, or audio).
        """
        try:
            while True:
                # Read data from the client
                data = await reader.read(1024)
                if not data:
                    break

                print(
                    f"[INFO] Received {len(data)} bytes of {data_type} data from a client."
                )

                # Forward the data to all connected clients except the sender
                for client_id, client_writer in self.client_conns.items():
                    if client_writer != writer:
                        client_writer.write(data)
                        await client_writer.drain()

        except asyncio.CancelledError:
            print(f"[INFO] Data handling task for {data_type} was cancelled.")
        except Exception as e:
            print(f"[ERROR] Error while handling {data_type} data: {e}")
        finally:
            print(f"[INFO] Closing data handling for {data_type}.")
            writer.close()
            await writer.wait_closed()

    async def handle_client(self, reader, writer):
        """
        Handle client requests during the conference.
        :param reader: asyncio StreamReader instance for receiving client messages.
        :param writer: asyncio StreamWriter instance for responding to clients.
        """
        try:
            while True:
                # Read client request
                data = await reader.read(1024)
                if not data:
                    break
                message = data.decode()
                print(f"[INFO] Received message: {message}")

                # Parse the JSON request
                try:
                    request = json.loads(message)
                except json.JSONDecodeError:
                    print("[WARNING] Invalid JSON format received.")
                    continue

                # Process the request
                if request.get("action") == "leave":
                    client_id = request.get("client_id")
                    if client_id and client_id in self.client_conns:
                        self.client_conns.pop(client_id).close()
                        print(f"[INFO] Client {client_id} has left the conference.")
                else:
                    print(f"[WARNING] Unrecognized client request: {request}")

        except asyncio.CancelledError:
            print("[INFO] Client handler task was cancelled.")
        except Exception as e:
            print(f"[ERROR] Error in client handler: {e}")
        finally:
            print("[INFO] Closing client connection.")
            writer.close()
            await writer.wait_closed()

    async def log(self):
        """
        Periodically log server status.
        """
        try:
            while self.running:
                print(
                    f"[INFO] Logging server status for conference {self.conference_id}:"
                )
                print(f"Connected clients: {list(self.client_conns.keys())}")
                await asyncio.sleep(5)  # Log every 5 seconds
        except asyncio.CancelledError:
            print("[INFO] Logging task was cancelled.")
        except Exception as e:
            print(f"[ERROR] Error in logging task: {e}")

    async def cancel_conference(self):
        """
        Cancel the conference and disconnect all clients.
        """
        try:
            self.running = False
            print(f"[INFO] Cancelling conference {self.conference_id}.")
            for client_id, client_writer in self.client_conns.items():
                client_writer.close()
                await client_writer.wait_closed()
            self.client_conns.clear()
            print(
                f"[INFO] Conference {self.conference_id} has been successfully cancelled."
            )
        except Exception as e:
            print(f"[ERROR] Error while cancelling conference: {e}")

    def start(self):
        """
        Start the ConferenceServer and begin handling clients and data streams.
        """
        print(f"[INFO] Starting ConferenceServer for conference {self.conference_id}.")

        async def main_server_task():
            # Run logging as a background task
            log_task = asyncio.create_task(self.log())

            try:
                # Wait until server is stopped
                while self.running:
                    await asyncio.sleep(1)
            finally:
                log_task.cancel()
                await log_task

        asyncio.run(main_server_task())


class MainServer:
    def __init__(self, server_ip, main_port):
        """
        Initialize MainServer instance.
        :param server_ip: The IP address where the server will run.
        :param main_port: The port number for the main server.
        """
        self.server_ip = server_ip
        self.server_port = main_port
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
            new_id = self.generate_conference_id()
            self.conference_servers[new_id] = ConferenceServer(
                new_id, CONF_SERVE_PORTS, client_ip
            )
            print(f"[INFO] Created conference {new_id} for {client_ip}")
            return jsonify(
                {
                    "status": "success",
                    "conference_id": new_id,
                    "ports": CONF_SERVE_PORTS,
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
            # if conference_id in self.conference_servers:
            #     conference_server = self.conference_servers[conference_id]
            #     return {
            #         "status": "success",
            #         "message": "Joined conference successfully",
            #         "ports": conference_server.conf_serve_ports,
            #     }
            # else:
            #     return {"status": "error", "message": "Conference not found"}

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
            # if conference_id in self.conference_servers:
            #     conference_server = self.conference_servers[conference_id]
            #     if client_id in conference_server.client_conns:
            #         writer = conference_server.client_conns.pop(client_id)
            #         writer.close()
            #         asyncio.create_task(writer.wait_closed())
            #         print(f"[INFO] Client {client_id} left conference {conference_id}")
            #         return {
            #             "status": "success",
            #             "message": "Client left the conference",
            #         }
            #     else:
            #         return {
            #             "status": "error",
            #             "message": "Client not found in conference",
            #         }
            # else:
            #     return {"status": "error", "message": "Conference not found"}
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
            # if conference_id in self.conference_servers:
            #     conference_server = self.conference_servers.pop(conference_id)
            #     asyncio.create_task(conference_server.cancel_conference())
            #     print(f"[INFO] Conference {conference_id} canceled.")
            #     return {"status": "success", "message": "Conference canceled"}
            # else:
            #     return {"status": "error", "message": "Conference not found"}
            if conference_id in self.conference_servers:
                # TODO
                # all_clients = self.conference_servers[conference_id].clients_info.keys()
                # for client_ip in all_clients:
                #     requests.post(f"{client_ip}/cancel_conference/{conference_id}")
                del self.conference_servers[conference_id]
                print(self.conference_servers)
                return jsonify({"status": "success"})
            return jsonify({"status": "error", "message": "Conference not found"}), 404

        async def request_handler(self, reader, writer):
            """
            Running task: Handle out-meeting (or also in-meeting) requests from clients using JSON.
            """
            try:
                # Read the request data sent by the client
                data = await reader.read(BUFFER_SIZE)
                message = data.decode()
                addr = writer.get_extra_info("peername")

                print(f"[INFO] Received message from {addr}: {message}")

                # Parse the JSON message
                try:
                    request = json.loads(message)
                except json.JSONDecodeError:
                    print(f"[WARNING] Invalid JSON format from {addr}")
                    response = {"status": "error", "message": "Invalid JSON format"}
                    writer.write(json.dumps(response).encode() + b"\n")
                    await writer.drain()
                    return

                # Check for required keys in the JSON object
                if "action" not in request:
                    print(f"[WARNING] Missing 'action' field from {addr}")
                    response = {"status": "error", "message": "Missing 'action' field"}
                    writer.write(json.dumps(response).encode() + b"\n")
                    await writer.drain()
                    return

                action = request.get("action")

                # Process the action field
                if action == "CREATE":
                    response = self.handle_creat_conference()
                elif action == "JOIN":
                    conference_id = request.get("conference_id")
                    if conference_id:
                        response = self.handle_join_conference(conference_id)
                    else:
                        response = {
                            "status": "error",
                            "message": "Missing 'conference_id' field",
                        }
                elif action == "QUIT":
                    client_id = request.get("client_id")
                    conference_id = request.get("conference_id")
                    if client_id and conference_id:
                        response = self.handle_quit_conference(client_id, conference_id)
                    else:
                        response = {
                            "status": "error",
                            "message": "Missing 'client_id' or 'conference_id' field",
                        }
                elif action == "CANCEL":
                    conference_id = request.get("conference_id")
                    if conference_id:
                        response = self.handle_cancel_conference(conference_id)
                    else:
                        response = {
                            "status": "error",
                            "message": "Missing 'conference_id' field",
                        }
                else:
                    print(f"[WARNING] Unrecognized action '{action}' from {addr}")
                    response = {
                        "status": "error",
                        "message": f"Unrecognized action '{action}'",
                    }

                # Send acknowledgment back to the client
                writer.write(json.dumps(response).encode() + b"\n")
                await writer.drain()

            except Exception as e:
                print(f"[ERROR] Error handling client request: {e}")
                response = {"status": "error", "message": "Internal server error"}
                writer.write(json.dumps(response).encode() + b"\n")
                await writer.drain()

            finally:
                print(f"[INFO] Closing connection from {addr}")
                writer.close()
                await writer.wait_closed()

    def start(self):
        """
        start MainServer
        """
        self.app.run(host=self.server_ip, port=self.server_port)


if __name__ == "__main__":
    server = MainServer(SERVER_IP_PUBLIC_TJL, MAIN_SERVER_PORT)
    server.start()
