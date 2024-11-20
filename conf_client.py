from util import *
import json
import socket
import requests
import datetime


class ConferenceClient:
    def __init__(
        self,
    ):
        # sync client
        self.is_working = True
        self.server_addr = "http://10.20.147.91:8888"
        self.on_meeting = False  # status
        self.conns = (
            None  # you may need to maintain multiple conns for a single conference
        )
        self.support_data_types = []  # for some types of data
        self.share_data = {}
        self.conference_id = None

        self.conference_info = (
            None  # you may need to save and update some conference_info regularly
        )

        self.recv_data = None  # you may need to save received streamd data from other clients in conference

    def create_conference(self):
        """
        create a conference: send create-conference request to server and obtain necessary data to
        """
        try:
            response = requests.post(f"{self.server_addr}/create_conference")
            if response.status_code == 200:
                data = response.json()
                self.conference_id = data["conference_id"]
                print(f"[Success] Created conference with ID: {self.conference_id}")
                self.join_conference(self.conference_id)
            else:
                print("[Error] Failed to create conference")
        except Exception as e:
            print(f"[Error] {str(e)}")

    def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data to
        """
        # try:
        #     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #     sock.connect(self.server_addr)

        #     request = {"action": "JOIN", "conference_id": conference_id}
        #     sock.sendall(json.dumps(request).encode())

        #     response = json.loads(sock.recv(1024).decode())
        #     if response["status"] == "success":
        #         self.conference_info = response["conference_info"]
        #         self.on_meeting = True
        #         print(f"[Success] Joined conference {self.conference_id}")
        #         self.start_conference()
        #     else:
        #         print(f"[Error] Failed to create conference: {response['message']}")

        #     sock.close()

        # except Exception as e:
        #     print(f"[Error] Failed to join conference: {str(e)}")
        try:
            response = requests.post(
                f"{self.server_addr}/join_conference/{conference_id}"
            )
            if response.status_code == 200:
                self.conference_id = conference_id
                self.on_meeting = True
                print(f"[Success] Joined conference {conference_id}")
                self.start_conference()
            else:
                print("[Error] Failed to join conference")
        except Exception as e:
            print(f"[Error] {str(e)}")

    def quit_conference(self):
        """
        quit your on-going conference
        """
        if not self.on_meeting:
            print("[Warn] Not in a conference")
            return

        try:
            response = requests.post(
                f"{self.server_addr}/quit_conference/{self.conference_id}"
            )
            if response.status_code == 200:
                self.close_conference()
                print("[Success] Quit conference")
            else:
                print("[Error] Failed to quit conference")
        except Exception as e:
            print(f"[Error] {str(e)}")

    def cancel_conference(self):
        """
        cancel your on-going conference (when you are the conference manager): ask server to close all clients
        """
        if not self.on_meeting:
            print("[Warn] Not in a conference")
            return

        try:
            response = requests.post(
                f"{self.server_addr}/cancel_conference/{self.conference_id}"
            )
            if response.status_code == 200:
                self.close_conference()
                print("[Success] Cancelled conference")
            else:
                print("[Error] Failed to cancel conference")
        except Exception as e:
            print(f"[Error] {str(e)}")

    def keep_share(
        self, data_type, send_conn, capture_function, compress=None, fps_or_frequency=30
    ):
        """
        running task: keep sharing (capture and send) certain type of data from server or clients (P2P)
        you can create different functions for sharing various kinds of data
        """
        pass

    def share_switch(self, data_type):
        """
        switch for sharing certain type of data (screen, camera, audio, etc.)
        """
        pass

    def keep_recv(self, recv_conn, data_type, decompress=None):
        """
        running task: keep receiving certain type of data (save or output)
        you can create other functions for receiving various kinds of data
        """

    def output_data(self):
        """
        running task: output received stream data
        """

    def start_conference(self):
        """
        init conns when create or join a conference with necessary conference_info
        and
        start necessary running task for conference
        """
        try:
            pass

        except Exception as e:
            print(f"[Error] Failed to start conference: {str(e)}")
            self.on_meeting = False

    def close_conference(self):
        """
        close all conns to servers or other clients and cancel the running tasks
        pay attention to the exception handling
        """
        self.on_meeting = False
        print(f"[Success] Closed conference {self.conference_id}")

    def start(self):
        """
        execute functions based on the command line input
        """
        while True:
            if not self.on_meeting:
                status = "Free"
            else:
                status = f"OnMeeting-{self.conference_id}"

            recognized = True
            cmd_input = (
                input(f'({status}) Please enter a operation (enter "?" to help): ')
                .strip()
                .lower()
            )
            fields = cmd_input.split(maxsplit=1)
            if len(fields) == 1:
                if cmd_input in ("?", "？"):
                    print(HELP)
                elif cmd_input == "create":
                    self.create_conference()
                elif cmd_input == "quit":
                    self.quit_conference()
                elif cmd_input == "cancel":
                    self.cancel_conference()
                else:
                    recognized = False
            elif len(fields) == 2:
                if fields[0] == "join":
                    input_conf_id = fields[1]
                    if input_conf_id.isdigit():
                        self.join_conference(input_conf_id)
                    else:
                        print("[Warn]: Input conference ID must be in digital form")
                elif fields[0] == "switch":
                    data_type = fields[1]
                    if data_type in self.share_data.keys():
                        self.share_switch(data_type)
                else:
                    recognized = False
            else:
                recognized = False

            if not recognized:
                print(f"[Warn]: Unrecognized cmd_input {cmd_input}")


if __name__ == "__main__":
    client1 = ConferenceClient()
    client1.start()
