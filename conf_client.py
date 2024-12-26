from util import *
import json
import socket
import requests
import threading
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    Response,
    stream_with_context,
)
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
import ipaddress
import netifaces as n

SERVER_INFO_PORT = 8887
# SERVER_IP = SERVER_IP_PUBLIC_TJL
SERVER_IP = SERVER_IP_PUBLIC_WGX
SERVER_PORT = 8888
SERVER_CONTROL_PORT = 8889
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
        self.unique_id = uuid.uuid4().bytes
        self.server_addr = f"http://{SERVER_IP}:{SERVER_PORT}"
        self.server_ip = SERVER_IP

        # get client ip
        self.sock_temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_temp.connect(("8.8.8.8", 80))
        self.client_ip = self.sock_temp.getsockname()[0]
        self.sock_temp.close()

        self.username = "User"
        self.on_meeting = False  # status
        self.conference_id = None
        self.participant_num = 1
        self.mode = "p2p"
        # struct pack uuid and ip
        self.id = struct.pack(">16s", self.unique_id)
        self.ip = struct.pack(">4s", socket.inet_aton(self.client_ip))

        self.client_info = {}

        # audio
        self.audio = pyaudio.PyAudio()
        self.microphone_on = True
        self.speaker_on = True

        self.audio_buffers = {}
        self.mixed_audio = queue.Queue(maxsize=10)

        self.output_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
        )

        # message
        self.new_msgs = []

        # 添加视频相关的属性
        self.current_camera_frame = None
        self.current_camera_data = {"client_ip": None, "id": None}
        self.current_screen_frame = None
        self.current_screen_data = {"client_ip": None, "id": None}

        # control
        self.last_control_screen_time = time.time()
        self.last_control_camera_time = time.time()
        self.screen_sleep_time = 0
        self.camera_sleep_time = 0

        # camera and screen
        self.is_camera_streaming = True
        self.is_screen_streaming = True

        # connect to frontend
        self.app = Flask(__name__)
        self.setup_routes()

    def create_conference(self):
        """
        create a conference: send create-conference request to server and obtain necessary data to
        """
        try:
            data = {
                "username": self.username,
                "client_ip": self.client_ip,
                "id": str(uuid.UUID(bytes=self.unique_id)),
            }
            response = requests.post(f"{self.server_addr}/create_conference", json=data)
            if response.status_code == 200:
                data = response.json()
                self.conference_id = data["conference_id"]
                print(f"[Success] Created conference with ID: {self.conference_id}")
                self.on_meeting = True
                threading.Thread(target=self.create_conference_conn).start()
            else:
                print("[Error] Failed to create conference")
        except Exception as e:
            print(f"[Error] {str(e)}")

    def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data to
        """
        try:
            data = {
                "username": self.username,
                "client_ip": self.client_ip,
                "id": str(uuid.UUID(bytes=self.unique_id)),
            }
            response = requests.post(
                f"{self.server_addr}/join_conference/{conference_id}", json=data
            )
            if response.status_code == 200:
                data = response.json()
                if data['mode'] == "cs":
                    self.conference_id = conference_id
                    self.on_meeting = True
                    self.server_ip = SERVER_IP
                    self.mode = "cs"
                    print(f"[Success] Joined conference {conference_id}")
                    self.start_conference()
                elif data['mode'] == "p2p":
                    self.mode = "p2p"
                    self.conference_id = conference_id
                    self.on_meeting = True
                    print(f"[Success] Joined conference {conference_id}")
                    self.server_ip = data["clients"]
                    self.start_conference()
                elif data['mode'] == "p2p2cs":
                    self.mode = "cs"
                    self.conference_id = conference_id
                    self.on_meeting = True
                    self.server_ip = SERVER_IP
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

        self.on_meeting = False

        try:
            data = {"id": str(uuid.UUID(bytes=self.unique_id))}
            response = requests.post(
                f"{self.server_addr}/quit_conference/{self.conference_id}", json=data
            )
            if response.status_code == 200:

                self.sock_info.close()
                self.sock_control.close()
                self.sock_msg.close()
                self.sock_audio.close()
                self.sock_camera.close()
                self.sock_screen.close()

                print("[Success] Quit conference")
            else:
                print("[Error] Failed to quit conference")
        except Exception as e:
            print(f"[Error] {str(e)}")

    def recv_info(self):
        print("[INFO] Starting info receiving...")
        try:
            while self.on_meeting:
                data = self.sock_info.recv(BUFFER_SIZE)
                if data:
                    info_data = json.loads(data.decode())
                    mode = info_data['mode']
                    if mode == "p2p2cs":
                        self.server_ip = SERVER_IP
                        self.mode = "cs"
                        self.reconnect()
                    elif mode == "cs2p2p":
                        rest_ip1 = info_data['clients'].keys()[0]
                        rest_ip2 = info_data['clients'].keys()[1]
                        if rest_ip1 == self.client_ip :
                            self.mode = "p2p"
                            threading.Thread(target=self.p2p_quit()).start()
                        elif rest_ip2 == self.client_ip:
                            self.mode = "p2p"
                            self.server_ip = info_data['clients'].values()[0]
                            self.reconnect()
                    elif mode == "p2pquit":
                        # self.server_ip = SERVER_IP
                        rest_ip = info_data['clients'].keys()[0]
                        if rest_ip == self.client_ip:
                            threading.Thread(target=self.p2p_quit()).start()
                    print(f"[INFO] Received info: {info_data}")
                    del info_data['mode']
                    self.client_info = info_data
        except Exception as e:
            print(f"[Error] Failed to receive info: {str(e)}")

    def recv_msg(self):
        print("[INFO] Starting message receiving...")
        try:
            while self.on_meeting:
                data = self.sock_msg.recv(BUFFER_SIZE)
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

    def send_object(self, object, connection):
        try:
            object_length = len(object)
            object_time = time.time()
            header = struct.pack(">I", object_length)
            header += struct.pack(">d", object_time)
            header += self.id
            header += self.ip
            connection.send(header)
            connection.send(object)
            # print(f"send object to {connection}")
        except Exception as e:
            print(f"Error sending object: {e}")

    def receive_object(self, connection, length):
        try:
            object = b""
            while len(object) < length:
                packet = b""
                packet += connection.recv(length - len(object))
                if not packet:
                    print("Connection closed")
                    break
                object += packet
            return object
        except Exception as e:
            print(f"Error receiving object: {e}")
            return None

    def unpack_object(self, data):
        object_length = struct.unpack(">I", data[:4])[0]
        object_time = struct.unpack(">d", data[4:12])[0]
        object_id = struct.unpack(">16s", data[12:28])[0]
        object_ip = struct.unpack(">4s", data[28:32])[0]
        return object_length, object_time, object_id, object_ip

    def send_screen(self):
        print("[INFO] Starting screen streaming...")
        try:
            if not self.on_meeting:
                print("[Warn] Not in a conference")
                return
            while self.on_meeting:
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    img = sct.grab(monitor)
                    img_np = np.array(img)
                    img_np = cv2.resize(img_np, (640, 480))
                    _, img_encode = cv2.imencode(
                        ".jpg", img_np, [int(cv2.IMWRITE_JPEG_QUALITY), 30]
                    )
                    img_bytes = img_encode.tobytes()
                    self.send_object(img_bytes, self.sock_screen)
                    print(f"Sent screen data: {len(img_bytes)}")
                    if self.is_screen_streaming:
                        screen_data = img_bytes
                        if screen_data is None:
                            continue
                        frame = cv2.imdecode(
                            np.frombuffer(screen_data, np.uint8), cv2.IMREAD_COLOR
                        )
                        if frame is None:
                            continue
                        _, buffer = cv2.imencode(".jpg", frame)
                        frame_base64 = base64.b64encode(buffer).decode("utf-8")
                        self.current_screen_frame = frame_base64
                        self.current_screen_data["client_ip"] = struct.unpack(">4s", self.ip)[0]
                        self.current_screen_data["id"] = struct.unpack(">16s", self.id)[0]
        except Exception as e:
            print(f"[Error] Failed to send screen data: {str(e)}")

    def recv_screen(self):
        print("[INFO] Starting screen receiving...")
        try:
            while self.on_meeting:
                header = self.receive_object(self.sock_screen, HEADER_LENGTH)
                if not header:
                    break
                screen_length, screen_time, screen_id, screen_ip = self.unpack_object(
                    header
                )
                print(
                    f"Received screen data: {screen_length}, {screen_time}, {screen_id}, {screen_ip}"
                )

                
                screen_data = self.receive_object(self.sock_screen, screen_length)
                print(f"Received screen data: {len(screen_data)}")  
                if screen_data is None:
                    continue
                frame = cv2.imdecode(
                    np.frombuffer(screen_data, np.uint8), cv2.IMREAD_COLOR
                )
                if frame is None:
                    continue
                _, buffer = cv2.imencode(".jpg", frame)
                frame_base64 = base64.b64encode(buffer).decode("utf-8")
                if self.is_screen_streaming:
                    self.current_screen_frame = frame_base64
                    self.current_screen_data["client_ip"] = screen_ip
                    self.current_screen_data["id"] = screen_id

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
                ret, frame = cap.read()
                frame = cv2.resize(frame, (640, 480))
                _, frame_encode = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30]
                )
                frame_bytes = frame_encode.tobytes()
                self.send_object(frame_bytes, self.sock_camera)
                print(f"Sent camera data: {len(frame_bytes)}")
                if self.is_camera_streaming:
                    camera_data = frame_bytes
                    if camera_data is None:
                        continue
                    frame = cv2.imdecode(
                        np.frombuffer(camera_data, np.uint8), cv2.IMREAD_COLOR
                    )
                    if frame is None:
                        continue
                    _, buffer = cv2.imencode(".jpg", frame)
                    frame_base64 = base64.b64encode(buffer).decode("utf-8")
                    self.current_camera_frame = frame_base64
                    self.current_camera_data["client_ip"] = struct.unpack(">4s", self.ip)[0]
                    self.current_camera_data["id"] = struct.unpack(">16s", self.id)[0]
                
        except Exception as e:
            print(f"[Error] Failed to send camera data: {str(e)}")

    def recv_camera(self):
        print("[INFO] Starting camera receiving...")
        try:
            while self.on_meeting:
                header = self.receive_object(self.sock_camera, HEADER_LENGTH)
                # print("Successfully receive camera header")
                if not header:
                    break
                camera_length, camera_time, camera_id, camera_ip = self.unpack_object(
                    header
                )
                print(
                    f"Received camera data: {camera_length}, {camera_time}, {camera_id}, {camera_ip}"
                )
                camera_data = self.receive_object(self.sock_camera, camera_length)
                print(f"Received camera data: {len(camera_data)}")
                if camera_data is None:
                    continue
                frame = cv2.imdecode(
                    np.frombuffer(camera_data, np.uint8), cv2.IMREAD_COLOR
                )
                if frame is None:
                    continue
                _, buffer = cv2.imencode(".jpg", frame)
                frame_base64 = base64.b64encode(buffer).decode("utf-8")
                if self.is_camera_streaming:
                    self.current_camera_frame = frame_base64
                    self.current_camera_data["client_ip"] = camera_ip
                    self.current_camera_data["id"] = camera_id

        except Exception as e:
            print(f"[Error] Failed to receive camera data: {str(e)}")


    def send_audio(self):
        print("[INFO] Starting audio streaming...")
        input_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            frames_per_buffer=CHUNK,
            input=True,
        )
        try:
            while self.on_meeting:
                sent_audio = input_stream.read(CHUNK, exception_on_overflow=False)
                if self.microphone_on:
                    self.send_object(sent_audio, self.sock_audio)

        except Exception as e:
            print(f"[Error] Failed to send audio data: {str(e)}")

    def recv_audio(self):

        while self.on_meeting:
            header = self.receive_object(self.sock_audio, HEADER_LENGTH)
            # print("Successfully receive audio header")
            audio_length, audio_time, audio_id, audio_ip = self.unpack_object(header)
            audio_data = self.receive_object(self.sock_audio, audio_length)
            # print("Successfully receive audio data")
            now_time = time.time()
            delay = now_time - audio_time
            if delay > 0.5:  # 丢弃延迟超过 500ms 的音频
                continue

            if audio_id not in self.audio_buffers:
                self.audio_buffers[audio_id] = queue.Queue(maxsize=10)

            user_queue = self.audio_buffers[audio_id]
            try:
                user_queue.put(audio_data, block=False)
            except queue.Full:
                user_queue.get()
                user_queue.put(audio_data)

            except Exception as e:
                print(f"Error receiving audio: {e}")

    def audio_mixer(self):
        while self.on_meeting:
            mixed_audio_array = None

            # 遍历用户音频队列
            for ip, user_queue in list(self.audio_buffers.items()):
                try:
                    # 获取音频数据
                    recv_audio = user_queue.get(block=False)
                    user_audio_array = np.frombuffer(recv_audio, dtype=np.int16)
                    # self.output_stream.write(user_audio_array.tobytes())
                except queue.Empty:
                    # 填充静音
                    user_audio_array = np.zeros(CHUNK, dtype=np.int16)

                if mixed_audio_array is None:
                    mixed_audio_array = np.zeros_like(user_audio_array, dtype=np.int32)

                # 混音叠加
                mixed_audio_array += user_audio_array

            # 如果没有任何音频数据，填充静音
            if mixed_audio_array is None:
                mixed_audio_array = np.zeros(CHUNK, dtype=np.int16)
            else:
                # 剪裁混音数据
                mixed_audio_array = np.clip(mixed_audio_array, -32768, 32767).astype(
                    np.int16
                )

            if self.speaker_on:
                self.output_stream.write(mixed_audio_array.tobytes())

            # to flask web

            # try:
            #     # print(self.mixed_audio.qsize())
            #     self.mixed_audio.put_nowait(mixed_audio_array.tobytes())

            # except queue.Full:
            #     # print('shit')
            #     # self.mixed_audio.get()
            #     # self.mixed_audio.put(mixed_audio_array.tobytes())
            #     pass

            # finally:
            #     time.sleep(CHUNK / RATE)

    def create_conference_conn(self):
        self.sock_control = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_info = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_msg = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_camera = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host = self.client_ip
        print(f"{host}")

        self.sock_control.bind((host, SERVER_CONTROL_PORT))
        self.sock_control.listen(5)

        self.sock_msg.bind((host, SERVER_MSG_PORT))
        self.sock_msg.listen(5)

        self.sock_camera.bind((host, SERVER_CAMERA_PORT))
        self.sock_camera.listen(5)

        self.sock_screen.bind((host, SERVER_SCREEN_PORT))
        self.sock_screen.listen(5)
        
        self.sock_audio.bind((host, SERVER_AUDIO_PORT))
        self.sock_audio.listen(5)


        try:
            self.sock_info.connect((SERVER_IP, SERVER_INFO_PORT))
            threading.Thread(target=self.recv_info).start()
        except Exception as e:
            print(f"111[Error] Failed to start conference: {str(e)}")
            self.on_meeting = False
        finally:
            pass
        conn,addr = self.sock_control.accept()
        self.sock_control = conn
        conn,addr = self.sock_msg.accept()
        self.sock_msg = conn
        conn,addr = self.sock_camera.accept()
        self.sock_camera = conn
        conn,addr = self.sock_screen.accept()
        self.sock_screen = conn
        conn,addr = self.sock_audio.accept()
        self.sock_audio = conn

        threading.Thread(target=self.recv_info).start()
            # Start message receiving thread
        threading.Thread(target=self.recv_msg).start()
            # Strat camera thread
        threading.Thread(target=self.send_camera).start()
        threading.Thread(target=self.recv_camera).start()
        threading.Thread(target=self.send_screen).start()
        threading.Thread(target=self.recv_screen).start()
        # Start audio thread
        threading.Thread(target=self.send_audio).start()
        threading.Thread(target=self.recv_audio).start()
        threading.Thread(target=self.audio_mixer).start()

        self.is_streaming = True
    def p2p_quit(self):
        self.on_meeting = False
        self.sock_control.close()
        self.sock_control = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_msg.close()
        self.sock_msg = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_camera.close()
        self.sock_camera = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_screen.close()
        self.sock_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_audio.close()
        self.sock_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.on_meeting = True

        threading.Thread(target=self.recv_info).start()

        host = self.client_ip
        print(f"{host}")

        self.sock_control.bind((host, SERVER_CONTROL_PORT))
        self.sock_control.listen(5)

        self.sock_msg.bind((host, SERVER_MSG_PORT))
        self.sock_msg.listen(5)

        self.sock_camera.bind((host, SERVER_CAMERA_PORT))
        self.sock_camera.listen(5)

        self.sock_screen.bind((host, SERVER_SCREEN_PORT))
        self.sock_screen.listen(5)
        
        self.sock_audio.bind((host, SERVER_AUDIO_PORT))
        self.sock_audio.listen(5)

        conn,addr = self.sock_control.accept()
        self.sock_control = conn
        conn,addr = self.sock_msg.accept()
        self.sock_msg = conn
        conn,addr = self.sock_camera.accept()
        self.sock_camera = conn
        conn,addr = self.sock_screen.accept()
        self.sock_screen = conn
        conn,addr = self.sock_audio.accept()
        self.sock_audio = conn

        threading.Thread(target=self.recv_info).start()
            # Start message receiving thread
        threading.Thread(target=self.recv_msg).start()
            # Strat camera thread
        threading.Thread(target=self.send_camera).start()
        threading.Thread(target=self.recv_camera).start()
        threading.Thread(target=self.send_screen).start()
        threading.Thread(target=self.recv_screen).start()
        # Start audio thread
        threading.Thread(target=self.send_audio).start()
        threading.Thread(target=self.recv_audio).start()
        threading.Thread(target=self.audio_mixer).start()
        

        self.is_streaming = True
    
        def reconnect(self):
            self.on_meeting = False
        self.sock_control.close()
        self.sock_control = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_msg.close()
        self.sock_msg = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_camera.close()
        self.sock_camera = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_screen.close()
        self.sock_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_audio.close()
        self.sock_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.on_meeting = True
        print("try to connect-------------------------------------------")
        try:
            self.sock_control.connect((self.server_ip, SERVER_CONTROL_PORT))
            self.sock_msg.connect((self.server_ip, SERVER_MSG_PORT))
            self.sock_camera.connect((self.server_ip, SERVER_CAMERA_PORT))
            self.sock_screen.connect((self.server_ip, SERVER_SCREEN_PORT))
            self.sock_audio.connect((self.server_ip, SERVER_AUDIO_PORT))

            # Start info thread
            threading.Thread(target=self.recv_info).start()

            # Start message receiving thread
            threading.Thread(target=self.recv_msg).start()

            # Strat camera thread
            threading.Thread(target=self.send_camera).start()
            threading.Thread(target=self.recv_camera).start()
            threading.Thread(target=self.send_screen).start()
            threading.Thread(target=self.recv_screen).start()

            # Start audio thread
            threading.Thread(target=self.send_audio).start()
            threading.Thread(target=self.recv_audio).start()
            threading.Thread(target=self.audio_mixer).start()
        except Exception as e:
            print(f"222[Error] Failed to start conference: {str(e)}")
            self.on_meeting = False
        finally:
            pass
    def start_conference(self):

        self.sock_control = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_info = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_msg = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_camera = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.sock_control.connect((self.server_ip, SERVER_CONTROL_PORT))
            self.sock_info.connect((SERVER_IP, SERVER_INFO_PORT))
            self.sock_msg.connect((self.server_ip, SERVER_MSG_PORT))
            self.sock_camera.connect((self.server_ip, SERVER_CAMERA_PORT))
            self.sock_screen.connect((self.server_ip, SERVER_SCREEN_PORT))
            self.sock_audio.connect((self.server_ip, SERVER_AUDIO_PORT))

            # Start control thread
            threading.Thread(target=self.recv_control).start()

            # Start info thread
            threading.Thread(target=self.recv_info).start()

            # Start message receiving thread
            threading.Thread(target=self.recv_msg).start()

            # Strat camera thread
            threading.Thread(target=self.send_camera).start()
            threading.Thread(target=self.recv_camera).start()
            threading.Thread(target=self.send_screen).start()
            threading.Thread(target=self.recv_screen).start()

            # Start audio thread
            threading.Thread(target=self.send_audio).start()
            threading.Thread(target=self.recv_audio).start()
            threading.Thread(target=self.audio_mixer).start()

        except Exception as e:
            print(f"[Error] Failed to start conference: {str(e)}")
            self.on_meeting = False

        finally:
            pass
            # Terminate PyAudio when the conference ends
            # self.audio.terminate()

    def setup_routes(self):
        @self.app.route("/")
        def index():
            return redirect("/dashboard")

        @self.app.route("/conference")
        def conference():
            print(f"if on_meeting: {self.on_meeting}")
            if self.on_meeting:
                return render_template("/frontend/conference.html")
            else:
                return redirect("/dashboard")

        @self.app.route("/dashboard")
        def dashboard():
            return render_template("/frontend/dashboard.html")

        @self.app.route("/api/client_info", methods=["POST", "GET"])
        def post_client_info():
            if request.method == "POST":
                data = request.json
                self.username = data["username"]
                return jsonify({"status": "success"})
            else:  # GET request
                return jsonify(
                    {"username": self.username, "conference-id": self.conference_id}
                )

        @self.app.route("/api/update_client_info")
        def update_client_info():
            def generate():
                while True:
                    infos = {
                        "client_ip": self.client_ip,
                        "id": str(uuid.UUID(bytes=self.unique_id)),
                        "username": self.username,
                        "on_meeting": self.on_meeting,
                        "conference_id": self.conference_id,
                        "participant_num": self.participant_num,
                        "client_info": self.client_info,
                    }
                    yield f"data: {json.dumps(infos)}\n\n"
                    time.sleep(3)

            return Response(generate(), mimetype="text/event-stream")

        @self.app.route("/api/button/<action>", methods=["POST"])
        def button_action(action):
            if action == "create_conference":
                self.create_conference()
            elif action == "join_conference":
                data = request.json
                self.conference_id = data["conference_id"]
                self.join_conference(self.conference_id)
            elif action == "toggle_camera":
                self.is_camera_streaming = not self.is_camera_streaming
                print(f"[INFO] Camera streaming: {self.is_camera_streaming}")
            elif action == "toggle_screen":
                self.is_screen_streaming = not self.is_screen_streaming
                print(f"[INFO] Screen streaming: {self.is_screen_streaming}")
            elif action == "toggle_mic":
                self.microphone_on = not self.microphone_on
                print(f"[INFO] Microphone status: {self.microphone_on}")
            elif action == "toggle_speaker":
                self.speaker_on = not self.speaker_on
                print(f"[INFO] Microphone on: {self.microphone_on}")
            elif action == "exit_meeting":
                self.quit_conference()
                print("[INFO] Quit meeting")

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
                    "id": str(uuid.UUID(bytes=self.unique_id)),
                    "username": self.username,
                    "timestamp": getCurrentTime(),
                }
                if self.mode == "p2p":
                    self.new_msgs.append(msg_json)
                self.sock_msg.send(json.dumps(msg_json).encode())
                print(f"[INFO] Send message: {msg}")
                return jsonify({"status": "success"})
            except Exception as e:
                print(f"[Error] Failed to send message: {str(e)}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/api/video_streams")
        def video_streams():
            def generate():
                while self.on_meeting:
                    if self.current_camera_data["id"] is not None:
                        camera_id = uuid.UUID(bytes=self.current_camera_data["id"])
                        camera_id = str(camera_id)
                        camera_ip = socket.inet_ntoa(
                            self.current_camera_data["client_ip"]
                        )
                    else:
                        camera_id = None
                        camera_ip = None

                    if self.current_screen_data["id"] is not None:
                        screen_id = uuid.UUID(bytes=self.current_screen_data["id"])
                        screen_id = str(screen_id)
                        screen_ip = socket.inet_ntoa(
                            self.current_screen_data["client_ip"]
                        )
                    else:
                        screen_id = None
                        screen_ip = None
                    streams_data = {
                        "camera": {
                            "frame": (
                                self.current_camera_frame
                                if self.is_camera_streaming
                                else None
                            ),
                            "client_ip": camera_ip,
                            "id": camera_id,
                        },
                        "screen": {
                            "frame": (
                                self.current_screen_frame
                                if self.is_screen_streaming
                                else None
                            ),
                            "client_ip": screen_ip,
                            "id": screen_id,
                        },
                    }
                    yield f"data: {json.dumps(streams_data)}\n\n"
                

            return Response(generate(), mimetype="text/event-stream")

    def start(self, remote=False):
        """
        execute functions based on the command line input
        """
        self.app.run(
            host="localhost" if not remote else SERVER_IP,
            port=FRONT_PORT,
            debug=False,
            threaded=True,
        )


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