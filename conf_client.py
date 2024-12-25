from util import *
import json
import socket
import requests
import threading
from flask import Flask, request, jsonify, render_template, redirect, Response, stream_with_context
import time
import sys
import argparse
import cv2
import base64
import struct
from threading import Lock
import numpy as np
import queue
import struct
import time
import uuid


SERVER_IP = SERVER_IP_LOCAL
SERVER_PORT = 8888
SERVER_CONTROL_PORT = 8889
SERVER_MSG_PORT = 8890
SERVER_AUDIO_PORT = 8891
SERVER_SCREEN_PORT = 8892
SERVER_CAMERA_PORT = 8893
SERVER_COMMAND_PORT = 9001

FRONT_PORT = 9000




class ConferenceClient:
    def __init__(
        self,
    ):
        # sync client
        self.unique_id = uuid.uuid4().bytes 
        self.is_working = True
        self.server_addr = f"http://{SERVER_IP}:{SERVER_PORT}"
        self.server_ip = SERVER_IP
        self.client_ip = socket.gethostbyname(socket.gethostname())
        self.username = "User"
        self.on_meeting = False  # status
        self.conns = None  # you may need to maintain multiple conns for a single conference
        self.support_data_types = []  # for some types of data
        self.share_data = {}
        self.conference_id = None
        self.participant_num = 1

        self.conference_info = None  # you may need to save and update some conference_info regularly

        self.recv_data = None  # you may need to save received streamd data from other clients in conference
        
        self.recv_msgs = []
        self.new_msgs = []

        self.sock_msg = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        ### Audio Streaming ###
        self.audio = pyaudio.PyAudio()
        self.client_audio_port = 8989
        self.microphone_on = True
        self.speaker_on = True

        self.audio_buffers = {}
        self.mixed_audio = queue.Queue(maxsize=10)
        
        # self.audio_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # self.audio_udp_socket.bind((self.client_ip, self.client_audio_port))
        # self.audio_udp_socket.setblocking(False)  # 设置非阻塞模式

        self.sock_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 

        self.output_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
        )

        # 添加视频相关的属性
        self.video_path = "test_video.mp4"
        self.video_capture = None
        self.frame_lock = Lock()
        self.current_frame = None
        self.video_thread = None
        self.is_streaming = False
        
        # control
        self.sock_control = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.last_control_screen_time = time.time()
        self.last_control_camera_time = time.time()
        self.screen_sleep_time = 0
        self.camera_sleep_time = 0

        # camera and screen
        self.sock_camera = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.sock_audio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # connect to frontend
        self.app = Flask(__name__)
        self.setup_routes()

        self.send_data = False
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
            response = requests.post(f"{self.server_addr}/join_conference/{conference_id}")
            # print(f"response: {response}")
            if response.status_code == 200:
                self.conference_id = conference_id
                self.on_meeting = True
                data = response.json()
                print(data["client_ip"])
                # print("----------------------------------------------")
                if (data["mode"] == "Client-Server"):
                    self.server_ip = SERVER_IP
                elif (data["mode"] == "P2P"):
                    self.server_ip = data["client_ip"]
                    print(f"[INFO] P2P mode, server ip: {self.server_ip}")
                else :
                    self.server_ip = SERVER_IP
                print(f"[Success] Joined conference {conference_id}")
                if self.server_ip :
                    # print("----------------------------------------------")
                    # print(f"server ip: {self.server_ip}")
                    # print("----------------------------------------------")
                    self.start_conference()
                else:
                    self.start_conference_one()
                # self.start_conference()
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
            response = requests.post(f"{self.server_addr}/quit_conference/{self.conference_id}")
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
            response = requests.post(f"{self.server_addr}/cancel_conference/{self.conference_id}")
            if response.status_code == 200:
                self.close_conference()
                print("[Success] Cancelled conference")
            else:
                print("[Error] Failed to cancel conference")
        except Exception as e:
            print(f"[Error] {str(e)}")

    def recv_msg(self):
        print("[INFO] Starting message receiving...")
        try:
            counter = 0
            while self.on_meeting:
                data = self.sock_msg.recv(BUFFER_SIZE)
                counter += 1
                # print(f"message count: {counter}")
                if data:
                    # Parse the received JSON message
                    msg_data = json.loads(data.decode())
                    print(f"[INFO] Received message: {msg_data}")
                    self.new_msgs.append(msg_data)  # Store the parsed JSON object
        except Exception as e:
            print(f"[Error] Failed to receive message: {str(e)}")

    def send_control(self, message, time_stamp):
        self.last_control_screen_time = time_stamp
        control_message = message
        control_message = struct.pack(">I", control_message)
        control_message += struct.pack(">d", time_stamp)
        self.sock_control.send(control_message)
                    
    def recv_control(self):
        print("[INFO] Starting control receiving...")
        try:
            while self.on_meeting:
                control_message = self.sock_control.recv(12)
                message = struct.unpack(">I", control_message[:4])[0]
                time_stamp = struct.unpack(">d", control_message[4:])[0]
                print(f"Received control message: {message}")
                if message == 1:
                    self.screen_sleep_time += SCREEN_SLEEP_INCREASE
                    print(f"Screen sleep time: {self.screen_sleep_time}")
                elif message == 2:
                    self.camera_sleep_time += CAMERA_SLEEP_INCREASE
                    print(f"Camera sleep time: {self.camera_sleep_time}")
                else:
                    pass
        except Exception as e:
            print(f"[Error] Failed to receive control message: {str(e)}")    

    def send_screen(self):
        print("[INFO] Starting screen streaming...")
        try:
            if not self.on_meeting:
                print("[Warn] Not in a conference")
                return
            while self.on_meeting:
                if self.is_screen_streaming:
                    with mss.mss() as sct:
                        monitor = sct.monitors[1]
                        img = sct.grab(monitor)
                        img_np = np.array(img)
                        img_np = cv2.resize(img_np, (1280, 720))
                        _, img_encode = cv2.imencode(".jpg", img_np, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
                        img_bytes = img_encode.tobytes()
                        img_length = len(img_bytes)
                        header = struct.pack(">I", img_length)
                        time_stamp = time.time()
                        header += struct.pack(">d", time_stamp)
                        self.sock_screen.send(header)
                        self.sock_screen.send(img_bytes)
                        time.sleep(self.screen_sleep_time)
                        self.screen_sleep_time -= SCREEN_SLEEP_DECREASE
                        if self.screen_sleep_time < 0:
                            self.screen_sleep_time = 0
        except Exception as e:
            print(f"[Error] Failed to send screen data: {str(e)}")
    
    def recv_screen(self):
        print("[INFO] Starting screen receiving...")
        try:
            while self.on_meeting:
                # header = self.sock_screen.recv(12)
                header = b""
                while len(header) < 12:
                    packet = b""
                    packet += self.sock_screen.recv(12 - len(header))
                    if not packet:
                        print("Connection closed")
                        break
                    header += packet
                if not header:
                    break
                frame_length = struct.unpack(">I", header[:4])[0]
                frame_time = struct.unpack(">d", header[4:])[0]
                # print('Successfully receive header')
                # print(f"frame length: {frame_length}")
                now_time = time.time()
                time_gap = now_time - frame_time
                # print(f"frame time gap: {time_gap}")
                if time_gap > SCREEN_TIME_MAX_GAP and now_time - self.last_control_screen_time > 1:
                    # 1 slow screen send
                    self.send_control(1, now_time)
                data = b""
                while len(data) < frame_length:
                    packet = b""
                    packet = self.sock_screen.recv(frame_length - len(data))
                    if not packet:
                        print("Connection closed")
                        break
                    data += packet
                # data = self.sock_screen.recv(frame_length)
                # print('Successfully receive camera data')
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                _, buffer = cv2.imencode(".jpg", frame)
                frame_base64 = base64.b64encode(buffer).decode("utf-8")
                self.current_frame = frame_base64
                

        except Exception as e:
            print(f"[Error] Failed to receive screen data: {str(e)}")
    
    def send_camera(self):
        print("[INFO] Starting camera streaming...")
        try:
            if not self.on_meeting:
                print("[Warn] Not in a conference")
                return
            cap = initialize_camera()
            while self.on_meeting:
                if self.is_camera_streaming:
                    ret, frame = cap.read()
                    if not ret:
                        print(f"帧捕获失败。")
                        break
                    _, frame_encode = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
                    frame_length = len(frame_encode)
                    header = struct.pack(">I", frame_length)
                    self.sock_camera.send(header)
                    self.sock_camera.send(frame_encode)
        except Exception as e:
            print(f"[Error] Failed to send camera data: {str(e)}")
            

    def recv_camera(self):
        print("[INFO] Starting camera receiving...")
        try:
            counter = 0
            while self.on_meeting:
                # header = self.sock_camera.recv(4)
                header = b""
                while len(header) < 12:
                    packet = b""
                    packet += self.sock_camera.recv(12 - len(header))
                    if not packet:
                        print("Connection closed")
                        break
                    header += packet
                if not header:
                    break
                frame_length = struct.unpack(">I", header[:4])[0]
                frame_time = struct.unpack(">d", header[4:])[0]
                # print('Successfully receive header')
                # print(f"frame length: {frame_length}")
                now_time = time.time()
                time_gap = now_time - frame_time
                # print(f"frame time gap: {time_gap}")
                if time_gap > CAMERA_TIME_MAX_GAP and now_time - self.last_control_camera_time > 1:
                    # 2 slow camera send
                    self.send_control(2, now_time)
                data = b""
                while len(data) < frame_length:
                    packet = b""
                    packet = self.sock_camera.recv(frame_length - len(data))
                    if not packet:
                        print("Connection closed")
                        break
                    data += packet
                # print('Successfully receive camera data')
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                # frame = cv2.resize(frame, (640, 480))
                _, buffer = cv2.imencode(".jpg", frame)
                frame_base64 = base64.b64encode(buffer).decode("utf-8")
                # with self.frame_lock:
                self.current_frame = frame_base64
                # time.sleep(1 / 30)  # 控制帧率
                

        except Exception as e:
            print(f"[Error] Failed to receive camera data: {str(e)}")

    def start_audio(self):
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.bind((self.client_ip, self.client_audio_port))
            udp_socket.setblocking(False)  # 设置非阻塞模式

            input_stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                frames_per_buffer=CHUNK,
                input=True,
            )
            output_stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                frames_per_buffer=CHUNK,
                output=True,
            )

            while self.on_meeting:
                if self.microphone_on:
                    sent_audio = input_stream.read(CHUNK)
                    udp_socket.sendto(sent_audio, (self.server_ip, self.server_audio_port))

                try:
                    recv_audio, _ = udp_socket.recvfrom(65535)
                    # output_stream.write(recv_audio)
                    print(recv_audio)  # test
                except BlockingIOError:
                    pass

        except Exception as e:
            print(f"[Error] Audio streaming failed: {str(e)}")

        finally:
            input_stream.stop_stream()
            input_stream.close()
            output_stream.stop_stream()
            output_stream.close()
            udp_socket.close()
            print("[Audio] Stopped audio transmission and reception.")

            print("[Audio] Stopped audio capture and transmission.")
        pass

    def recv_aud(self):
        """
        Receive audio data
        """
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.bind((self.client_ip, self.audio_port))

            # Open audio output stream
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                frames_per_buffer=CHUNK,
                output=True,
            )

            print("[Audio] Starting audio reception and playback...")
            while self.on_meeting:
                # Receive audio data from the server
                audio_data, _ = udp_socket.recvfrom(CHUNK)
                stream.write(audio_data)

        except Exception as e:
            print(f"[Error] Audio reception failed: {str(e)}")

        finally:
            stream.stop_stream()
            stream.close()
            udp_socket.close()
            print("[Audio] Stopped audio reception and playback.")

    def keep_share(self, data_type, send_conn, capture_function, compress=None, fps_or_frequency=30):
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
            self.sock_msg.connect((self.server_ip, SERVER_MSG_PORT))
            self.sock_camera.connect((self.server_ip, SERVER_CAMERA_PORT))
            self.sock_screen.connect((self.server_ip, SERVER_SCREEN_PORT))
            # Start message receiving thread
            threading.Thread(target=self.recv_msg).start()

            # Start camera and screen sending thread
            threading.Thread(target=self.send_camera).start()
            threading.Thread(target=self.recv_camera).start()
            # Start screen thread
            threading.Thread(target=self.send_screen).start()
            threading.Thread(target=self.recv_screen).start()
            # 自动开启视频流
            self.is_streaming = True
            # self.video_thread = threading.Thread(target=self.process_video)
            # self.video_thread.start()

        except Exception as e:
            print(f"[Error] Failed to start conference: {str(e)}")
            self.on_meeting = False

        finally:
            pass
            # Terminate PyAudio when the conference ends
            # self.audio.terminate()
    def start_conference_one(self):
        try:
            self.send_data = False
            threading.Thread(target=self.send_camera).start()
            threading.Thread(target=self.send_screen).start()
            # threading.Thread(target=self.send_audio).start()
            # 自动开启视频流
            self.is_streaming = True

        except Exception as e:
            print(f"[Error] Failed to start conference: {str(e)}")
            self.on_meeting = False

        finally:
            pass

    def close_conference(self):
        """
        close all conns to servers or other clients and cancel the running tasks
        pay attention to the exception handling
        """
        self.on_meeting = False
        print(f"[Success] Closed conference {self.conference_id}")

    def setup_routes(self):
        @self.app.route("/")
        def index():
            return redirect("/dashboard")

        @self.app.route("/conference")
        def conference():
            if self.on_meeting:
                return render_template("/frontend/conference.html")
            else:
                return redirect("/dashboard")

        @self.app.route("/dashboard")
        def dashboard():
            return render_template("/frontend/dashboard.html")

        @self.app.route("/api/client_info", methods=["POST"])
        def post_client_info():
            data = request.json
            self.username = data["username"]
            return jsonify({"status": "success"})

        @self.app.route("/api/client_info", methods=["GET"])
        def get_client_info():
            return jsonify(
                {
                    "client_ip": self.client_ip,
                    "username": self.username,
                    "on_meeting": self.on_meeting,
                    "conference_id": self.conference_id,
                    "participant_num": self.participant_num,
                    "share_data": self.share_data,
                }
            )

        @self.app.route("/api/button/<action>", methods=["POST"])
        def button_action(action):
            if action == "create_conference":
                self.create_conference()
            elif action == "join_conference":
                data = request.json
                self.conference_id = data["conference_id"]
                self.join_conference(self.conference_id)
            elif action == "toggle_camera":
                pass
            elif action == "toggle_screen":
                pass
            elif action == "toggle_mic":
                self.microphone_on = not self.microphone_on
                print(f"[INFO] Microphone status: {self.microphone_on}")
            elif action == "toggle_speaker":
                self.speaker_on = not self.speaker_on
                print(f"[INFO] Speaker status: {self.speaker_on}")
            elif action == "switch_meeting":
                data = request.json
                self.conference_id = data["conference_id"]
                self.join_conference(self.conference_id)
            elif action == "exit_meeting":
                self.quit_conference()

            print(f"[INFO] Button action: {action}")

            return jsonify({"status": "success"})

        @self.app.route("/api/recv_msg", methods=["GET"])
        def recv_messages():
            def generate():
                while True:
                    if self.new_msgs:
                        # Send each message individually as JSON
                        msg = self.new_msgs.pop(0)  # Get and remove first message
                        yield f"data: {json.dumps(msg)}\n\n"
                    time.sleep(0.1)

            return Response(generate(), mimetype="text/event-stream")

        @self.app.route("/api/send_msg", methods=["POST"])
        def send_message():
            try:
                data = request.json
                msg = data["message"]
                msg_json = {
                    "msg": msg,
                    "ip": self.client_ip,
                    "username": self.username,
                    "timestamp": getCurrentTime(),
                }
                self.sock_msg.send(json.dumps(msg_json).encode())
                print(f"[INFO] Send message: {msg}")
                return jsonify({"status": "success"})
            except Exception as e:
                print(f"[Error] Failed to send message: {str(e)}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/api/audio_feed")
        def audio_feed():
            def generate_audio():
                
                pass
                
                # send wav header
                # yield generate_wav_header(
                #     sample_rate=RATE,
                #     bits_per_sample=BYTES_PER_SAMPLE * 8,
                #     channels=CHANNELS
                # )
                
                # while self.on_meeting and self.speaker_on:
                #     print(self.mixed_audio.qsize())
                #     try:
                #         mixed_audio = self.mixed_audio.get(block=True, timeout=0.1)
                #     except queue.Empty:
                #         mixed_audio = b'\x00' * CHUNK

                #     yield mixed_audio

            return Response(generate_audio(), mimetype="audio/wav")
            
        @self.app.route("/api/video_feed/<stream_type>")
        def video_feed(stream_type):
            """获取视频流（camera或screen）"""

            def generate():
                # print("-------------------------------------")
                # print(f"is_streaming: {self.is_streaming}")
                # print(f"on_meeting: {self.on_meeting}")
                # print("-------------------------------------")
                while self.is_streaming and self.on_meeting:
                    with self.frame_lock:
                        if self.current_frame:
                            # 构建包含用户信息的帧数据
                            frame_data = {
                                "frame": self.current_frame,
                                "username": self.username,
                                "client_ip": self.client_ip,
                                "stream_type": stream_type,
                            }
                            yield f"data: {json.dumps(frame_data)}\n\n"
                    time.sleep(1 / 30)

            return Response(generate(), mimetype="text/event-stream")

        @self.app.route("/api/toggle_video", methods=["POST"])
        def toggle_video():
            """切换视频流的开启/关闭状态"""
            data = request.json
            action = data.get("action")

            if action == "start" and not self.is_streaming:
                self.is_streaming = True
                self.video_thread = threading.Thread(target=self.process_video)
                self.video_thread.start()
            elif action == "stop" and self.is_streaming:
                self.is_streaming = False
                if self.video_thread:
                    self.video_thread.join()

            return jsonify({"status": "success"})
    def get_command_server(self):
        get_command_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        get_command_server.bind((self.client_ip, SERVER_COMMAND_PORT))
        get_command_server.listen(5)
        while True:
            # print("eeeeeeeeeeeeeeeeeeeeeeeeeee")
            print("Waiting for connection...")
            conn, addr = get_command_server.accept()
            print(f"Connected by {addr}")
            data = conn.recv(1024)
            if not data:
                break
            print(f"Received data: {data}")
        get_command_server.close()


    def start(self, remote=False):
        """
        execute functions based on the command line input
        """
        self.app.run(
            host="localhost" if not remote else SERVER_IP_PUBLIC_TJL,
            port=FRONT_PORT,
            debug=False,
            threaded=True,
        )
        # self.get_command_server()
        while True:
            if not self.on_meeting:
                status = "Free"
            else:
                status = f"OnMeeting-{self.conference_id}"

            recognized = True
            cmd_input = input(f'({status}) Please enter a operation (enter "?" to help): ').strip().lower()
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

    def process_video(self):
        """处理视频流并保持当前帧的更新"""
        self.video_capture = cv2.VideoCapture(self.video_path)
        while self.is_streaming and self.on_meeting:
            ret, frame = self.video_capture.read()
            if not ret:
                # 视频结束时重新开始
                self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # 调整帧大小
            frame = cv2.resize(frame, (640, 480))

            # 将帧转换为base64格式
            _, buffer = cv2.imencode(".jpg", frame)
            frame_base64 = base64.b64encode(buffer).decode("utf-8")

            with self.frame_lock:
                self.current_frame = frame_base64

            time.sleep(CHUNK / RATE)  # 控制帧率

        if self.video_capture:
            self.video_capture.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Conference Client")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=9000,
        help="Port to run the frontend on (default: 9000)",
    )
    parser.add_argument("-r", "--remote", type=bool, default=False, help="It's remote client")
    args = parser.parse_args()

    FRONT_PORT = args.port
    client1 = ConferenceClient()
    # client1.get_command_server()
    threading.Thread(target=client1.get_command_server).start()
    client1.start(remote=args.remote)