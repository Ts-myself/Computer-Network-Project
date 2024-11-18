import asyncio
import json
from util import *


class ConferenceServer:
    def __init__(self, ):
        # async server
        self.conference_id = None  # conference_id for distinguish difference conference
        self.conf_serve_ports = None
        self.data_serve_ports = {}
        self.data_types = ['screen', 'camera', 'audio']  # example data types in a video conference
        self.clients_info = None
        self.client_conns = None
        self.mode = 'Client-Server'  # or 'P2P' if you want to support peer-to-peer conference mode

    async def handle_data(self, reader, writer, data_type):
        """
        running task: receive sharing stream data from a client and decide how to forward them to the rest clients
        """

    async def handle_client(self, reader, writer):
        """
        running task: handle the in-meeting requests or messages from clients
        """

    async def log(self):
        while self.running:
            print('Something about server status')
            await asyncio.sleep(LOG_INTERVAL)

    async def cancel_conference(self):
        """
        handle cancel conference request: disconnect all connections to cancel the conference
        """

    def start(self):
        '''
        start the ConferenceServer and necessary running tasks to handle clients in this conference
        '''


class MainServer:
    def __init__(self, server_ip, main_port):
        # async server
        self.server_ip = server_ip
        self.server_port = main_port
        self.main_server = None

        self.conference_conns = None
        self.conference_servers = {}  # self.conference_servers[conference_id] = ConferenceManager

    def handle_creat_conference(self,):
        """
        create conference: create and start the corresponding ConferenceServer, and reply necessary info to client
        """

    def handle_join_conference(self, conference_id):
        """
        join conference: search corresponding conference_info and ConferenceServer, and reply necessary info to client
        """

    def handle_quit_conference(self):
        """
        quit conference (in-meeting request & or no need to request)
        """
        pass

    def handle_cancel_conference(self):
        """
        cancel conference (in-meeting request, a ConferenceServer should be closed by the MainServer)
        """
        pass

    async def request_handler(self, reader, writer):
        """
        Running task: Handle out-meeting (or also in-meeting) requests from clients using JSON.
        """
        try:
            # Read the request data sent by the client
            data = await reader.read(BUFFER_SIZE)
            message = data.decode()
            addr = writer.get_extra_info('peername')

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

            action = request["action"]

            # Process the action field
            if action == "CREATE":
                self.handle_creat_conference()
                response = {"status": "success", "message": "Conference created"}
            elif action == "JOIN":
                if "conference_id" in request:
                    conference_id = request["conference_id"]
                    self.handle_join_conference(conference_id)
                    response = {"status": "success", "message": f"Joined conference {conference_id}"}
                else:
                    response = {"status": "error", "message": "Missing 'conference_id' field"}
            elif action == "QUIT":
                self.handle_quit_conference()
                response = {"status": "success", "message": "Quit conference"}
            elif action == "CANCEL":
                self.handle_cancel_conference()
                response = {"status": "success", "message": "Conference canceled"}
            else:
                print(f"[WARNING] Unrecognized action '{action}' from {addr}")
                response = {"status": "error", "message": f"Unrecognized action '{action}'"}

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

    async def run_main_server(self):
        server = await self.main_server
        async with server:
            print(f"[INFO] MainServer running at {self.server_ip}:{self.server_port}")
            await server.serve_forever()

    def start(self):
        """
        start MainServer
        """
        async def handle_client(reader, writer):
            # Pass reader and writer to the request_handler method for processing
            await self.request_handler(reader, writer)

        print(f"[INFO] Starting MainServer on {self.server_ip}:{self.server_port}...")

        try:
            async def main():
                # Assign the result of the awaited start_server coroutine
                self.main_server = asyncio.start_server(handle_client, self.server_ip, self.server_port)
                # Run the main server loop
                await self.run_main_server()

            # Run the asyncio event loop
            asyncio.run(main())

        except Exception as e:
            print(f"[ERROR] Failed to start server: {e}")
        raise


if __name__ == '__main__':
    server = MainServer(SERVER_IP_PUBLIC_HLC, MAIN_SERVER_PORT)
    server.start()
