from util import *
import json
import socket
import requests
import datetime
import threading
import time
import cv2
import numpy as np
import pyautogui
import mss
import struct

# SERVER_IP = "10.20.147.91"
SERVER_IP = '127.0.0.1'
SERVER_PORT = 8888
SERVER_MSG_PORT = 8890
SERVER_AUDIO_PORT = 8891
SERVER_SCREEN_PORT = 8892
SERVER_CAMERA_PORT = 8893


class ConferenceClient:
    def __init__(
        self,
    ):
        # sync client
        self.is_working = True
        self.server_addr = f"http://{SERVER_IP}:{SERVER_PORT}"
        self.client_ip = socket.gethostbyname(socket.gethostname())
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
        self.frames_lock = threading.Lock()
    

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

    def send_msg(self):
        """
        Send messages in a conference using TCP socket connection
        """
        if not self.on_meeting:
            print("[Warn] Not in a conference")
            return

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                print(
                    f"[INFO] Connecting to message server (attempt {attempt + 1}/{max_retries})..."
                )

                # Create TCP socket for messaging
                msg_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                msg_socket.connect((SERVER_IP, SERVER_MSG_PORT))
                print("[Success] Connected to message server")

                # Start receive thread
                def receive_messages():
                    while self.on_meeting:
                        try:
                            data = msg_socket.recv(BUFFER_SIZE).decode()
                            if data:
                                msg_data = json.loads(data)
                                print(
                                    f"[{msg_data['timestamp']}] {msg_data['ip']}: {msg_data['msg']}"
                                )
                        except:
                            break
                    msg_socket.close()

                # Start receive thread
                threading.Thread(target=receive_messages).start()

                # Send messages until conference ends
                print("Start messaging (type 'quit_msg' to stop):")
                while self.on_meeting:
                    message = input()
                    if message.lower() == "quit_msg":  # TODO: use botton to quit
                        break
                    msg_json = {
                        "msg": message,
                        "ip": self.client_ip,
                        "timestamp": getCurrentTime(),
                    }
                    msg_socket.send(json.dumps(msg_json).encode())

                break  # 如果成功连接，跳出重试循环

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[Warn] Connection attempt failed: {str(e)}")
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print(
                        f"[Error] Messaging error after {max_retries} attempts: {str(e)}"
                    )
                    return

    global img_show

    def send_screen(self):
        if not self.on_meeting:
            print("[Warn] Not in a conference")
            return

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                print(f"[INFO] Connecting to screen server (attempt {attempt + 1}/{max_retries})...")

                # 创建发送和接收的独立 socket
                send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                # 接收 socket 绑定到本地的任意可用端口
                recv_socket.bind((SERVER_IP, SERVER_SCREEN_PORT))
                print("[Success] Sockets created for sending and receiving")

                received_frames = {}

                # 接收屏幕数据线程
                def receive_screen():
                    def reconstruct_frame():
                        while self.on_meeting:
                            with self.frames_lock:  # 加锁保护对 received_frames 的访问
                                if received_frames:
                                    for timestamp, chunks in list(received_frames.items()):
                                        if len(chunks) == chunks[0][1]:  # 判断是否收齐所有分片
                                            frame_data = b"".join(chunk[2] for chunk in sorted(chunks.values()))
                                            img = cv2.imdecode(np.frombuffer(frame_data, np.uint8), cv2.IMREAD_COLOR)
                                            with open(f"received_{timestamp}.jpg", "wb") as f:
                                                f.write(frame_data)
                                            del received_frames[timestamp]  # 删除已处理的帧

                    threading.Thread(target=reconstruct_frame).start()

                    print("[INFO] 等待接收屏幕数据...")
                    while self.on_meeting:
                        try:
                            print('try to receive')
                            packet, _ = recv_socket.recvfrom(BUFFER_SIZE + 16)
                            print('receive success')

                            header = packet[:16]
                            chunk_data = packet[16:]

                            sequence, total_chunks, timestamp = struct.unpack("!IIQ", header)
                            print(f"[INFO] 接收到第 {sequence + 1}/{total_chunks} 片数据，时间戳: {timestamp}")

                            with self.frames_lock:  # 加锁保护对 received_frames 的访问
                                if timestamp not in received_frames:
                                    received_frames[timestamp] = {}
                                received_frames[timestamp][sequence] = (sequence, total_chunks, chunk_data)
                        except Exception as e:
                            print(f"[Error] 接收失败: {str(e)}")

                    recv_socket.close()

                threading.Thread(target=receive_screen).start()

                print("Start screen sharing:")
                hwnd, screenshotDC, mfcDC, saveDC, saveBitMap = init_capture_resources()
                while self.on_meeting:
                    frame_data = capture_screen(hwnd,screenshotDC, mfcDC, saveDC, saveBitMap)
                    total_size = len(frame_data)
                    num_chunks = (total_size // BUFFER_SIZE) + 1
                    timestamp = int(time.time() * 1000)

                    for i in range(num_chunks):
                        chunk_data = frame_data[i * BUFFER_SIZE: (i + 1) * BUFFER_SIZE]
                        chunk_header = struct.pack("!IIQ", i, num_chunks, timestamp)
                        chunk_data = chunk_header + chunk_data
                        print(f"[INFO] 发送第 {i + 1}/{num_chunks} 片数据")
                        send_socket.sendto(chunk_data, (SERVER_IP, SERVER_SCREEN_PORT))

                release_capture_resources(hwnd, screenshotDC, mfcDC, saveDC, saveBitMap)
                send_socket.close()
                recv_socket.close()
                break

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[Warn] Connection attempt failed: {str(e)}")
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print(f"[Error] Screen sharing error after {max_retries} attempts: {str(e)}")
                    return

                
                
        
            
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
            # Start messaging thread
            # threading.Thread(target=self.send_msg).start()
            threading.Thread(target=self.send_screen).start()

            # Keep conference running
            while self.on_meeting:
                time.sleep(1)
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
