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
import time 
import mss
import win32
import win32con
"""
ImageGrab.grab() 0.3s
mss              0.03s for mac  / 0.05 for windows
pyautogui        0.27s
win32            与截屏的大小有关，1280x720很快 0.024 但是全屏的话 0.08 
"""
def capture_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)
        img_np = np.array(img)
        img_np = cv2.resize(img_np, (1280, 720))        
        _, img_encode = cv2.imencode(".jpg", img_np, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
        img_bytes = img_encode.tobytes()
        print(f"Image size: {len(img_bytes)} bytes")
        return img_bytes
    
it = 100
tot = 0
screen_shots = []
time_list = []
for i in range(it):
    print(f"Test {i+1}/{it}")
    st = time.time()
    # temp = capture_screen(hwnd, screenshotDC, mfcDC, saveDC, saveBitMap)
    temp = capture_screen()
    screen_shots.append(temp)
    en = time.time()
    time_list.append(en)
    tot += en - st
    print(f"Time: {en-st:.4f}s")


print(f"Average time: {tot/it:.4f}s")


# 计算第一张和最后一张之间差了多少秒
time_gap = time_list[-1] - time_list[0]
print(f"Time gap: {time_gap:.4f}s")
print(f"平均一秒多少帧: {it/time_gap:.2f}帧")



import cv2
import numpy as np
import time
import datetime
import tempfile
import os

st = time.time()
fps = 24

# 检查系统支持的编码器，H.264 或 MJPG
try:
    fourcc = cv2.VideoWriter_fourcc(*'H264')  # 尝试使用 H.264
except:
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # 如果失败，切换到 MJPG

# 使用临时文件存储视频
with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
    temp_file_path = temp_file.name

video = cv2.VideoWriter(temp_file_path, fourcc, fps, (1280, 720))

# 遍历每一帧并写入视频
for img in screen_shots:
    if isinstance(img, bytes):
        img = cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_COLOR)
    video.write(img)

# 释放VideoWriter资源
video.release()

# 读取临时文件为字节流
with open(temp_file_path, "rb") as f:
    video_data = f.read()

# 删除临时文件
os.remove(temp_file_path)

en = time.time()
print(f"Total time: {en-st:.4f}s")
print(f"Video data size: {len(video_data)} bytes")






