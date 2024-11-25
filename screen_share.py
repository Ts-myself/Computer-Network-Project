import socket
import threading
import time
import mss
import numpy as np
import cv2
import struct

SERVER_IP = "127.0.0.1"  # 本地调试
SERVER_SCREEN_PORT = 12345
BUFFER_SIZE = 1024  # UDP max size

class ScreenSharing:
    def __init__(self, role):
        self.on_meeting = True
        self.role = role  # "sender" 或 "receiver"

    def capture_screen(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            img = sct.grab(monitor)
            img_np = np.array(img)
            img_np = cv2.resize(img_np, (1280, 720))  # Resize for lower resolution
            _, img_encode = cv2.imencode(".jpg", img_np, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
            img_bytes = img_encode.tobytes()
            return img_bytes

    def send_screen(self):
        screen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        def send_frame():
            while self.on_meeting:
                frame_data = self.capture_screen()
                total_size = len(frame_data)
                print(f"Debug: {total_size}")
                num_chunks = (total_size // BUFFER_SIZE) + 1
                timestamp = int(time.time() * 1000)  # 毫秒级时间戳

                for i in range(num_chunks):
                    chunk_data = frame_data[i * BUFFER_SIZE: (i + 1) * BUFFER_SIZE]
                    header = struct.pack("!IIQ", i, num_chunks, timestamp)
                    screen_socket.sendto(header + chunk_data, (SERVER_IP, SERVER_SCREEN_PORT))

                time.sleep(1000000)  # 控制帧率为 ~15FPS


        print("[INFO] 开始屏幕共享...")
        send_frame()

    def receive_screen(self):
        screen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        screen_socket.bind((SERVER_IP, SERVER_SCREEN_PORT))
        received_frames = {}

        def reconstruct_frame():
            while self.on_meeting:
                if received_frames:
                    for timestamp, chunks in list(received_frames.items()):
                        if len(chunks) == chunks[0][1]:  # 全部分片到齐
                            frame_data = b"".join(chunk[2] for chunk in sorted(chunks.values()))
                            print(f"Debug: {len(frame_data)}")
                            buffer_array = np.frombuffer(frame_data, dtype=np.uint8)
                            print(f"[Debug] 数据类型: {buffer_array.dtype}, 数据长度: {len(buffer_array)}")
                            frame_img = cv2.imdecode(buffer_array, cv2.IMREAD_COLOR)    
                            del received_frames[timestamp]

        threading.Thread(target=reconstruct_frame).start()

        print("[INFO] 等待接收屏幕数据...")
        while self.on_meeting:
            try:
                data, addr = screen_socket.recvfrom(BUFFER_SIZE + 16)  # 正确解包
                header = data[:16]
                chunk_data = data[16:]

                # 正确解包头部
                sequence, total_chunks, timestamp = struct.unpack("!IIQ", header)
                print(f"[INFO] 接收到第 {sequence + 1}/{total_chunks} 片数据")
                print(f"[INFO] 时间戳: {timestamp}")
                if timestamp not in received_frames:
                    received_frames[timestamp] = {}
                received_frames[timestamp][sequence] = (sequence, total_chunks, chunk_data)
            except Exception as e:
                print(f"[Error] 接收失败: {str(e)}")
                break

        screen_socket.close()
        cv2.destroyAllWindows()


    def start(self):
        if self.role == "sender":
            self.send_screen()
        elif self.role == "receiver":
            self.receive_screen()
        else:
            print("[Error] 无效角色！请选择 'sender' 或 'receiver'")

if __name__ == "__main__":
    role = input("请选择角色（sender/receiver）：").strip().lower()
    sharing = ScreenSharing(role)
    sharing.start()
