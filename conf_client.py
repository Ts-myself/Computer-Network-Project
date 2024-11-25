from util import *
import json
import socket
import requests
import threading
from flask import Flask, request, jsonify, render_template, redirect, Response
import time
import sys
import argparse
import cv2
import base64
from threading import Lock

SERVER_IP = "127.0.0.1"
SERVER_PORT = 8888
SERVER_MSG_PORT = 8890
SERVER_AUDIO_PORT = 8891
SERVER_SCREEN_PORT = 8892
SERVER_CAMERA_PORT = 8893

FRONT_PORT = 9000


class ConferenceClient:
    def __init__(
        self,
    ):
        # sync client
        self.is_working = True
        self.server_addr = f"http://{SERVER_IP}:{SERVER_PORT}"
        self.server_ip = SERVER_IP
        self.client_ip = socket.gethostbyname(socket.gethostname())
        self.username = "User"
        self.on_meeting = False  # status
        self.conns = (
            None  # you may need to maintain multiple conns for a single conference
        )
        self.support_data_types = []  # for some types of data
        self.share_data = {}
        self.conference_id = None
        self.participant_num = 1

        self.conference_info = (
            None  # you may need to save and update some conference_info regularly
        )

        self.recv_data = None  # you may need to save received streamd data from other clients in conference

        ### Audio Streaming
        self.audio = pyaudio.PyAudio()
        self.server_audio_port = SERVER_AUDIO_PORT
        self.client_audio_port = 8989
        self.microphone_on = True

        self.recv_msgs = []
        self.new_msgs = []

        self.sock_msg = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # 添加视频相关的属性
        self.video_path = "test_video.mp4"
        self.video_capture = None
        self.frame_lock = Lock()
        self.current_frame = None
        self.video_thread = None
        self.is_streaming = False

        # connect to frontend
        self.app = Flask(__name__)
        self.setup_routes()

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
                print(f"[INFO] Connecting to message server (attempt {attempt + 1}/{max_retries})...")
                # Create TCP socket for messaging
                msg_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                msg_socket.connect((SERVER_IP, SERVER_MSG_PORT))
                print("[Success] Connected to message server")

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
                    print(recv_audio) # test
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
            # Start message thread
            threading.Thread(target=self.send_msg).start()
            
            # Start audio thread
            threading.Thread(target=self.start_audio).start()

            # 自动开启视频流
            self.is_streaming = True
            self.video_thread = threading.Thread(target=self.process_video)
            self.video_thread.start()

        except Exception as e:
            print(f"[Error] Failed to start conference: {str(e)}")
            self.on_meeting = False

        finally:
            pass
            # Terminate PyAudio when the conference ends
            # self.audio.terminate()

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
                pass
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

        @self.app.route("/api/video_feed/<stream_type>")
        def video_feed(stream_type):
            """获取视频流（camera或screen）"""

            def generate():
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

            time.sleep(1 / 30)  # 控制帧率

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
    parser.add_argument(
        "-r", "--remote", type=bool, default=False, help="It's remote client"
    )
    args = parser.parse_args()

    FRONT_PORT = args.port
    client1 = ConferenceClient()
    client1.start(remote=args.remote)
