"""
Simple util implementation for video conference
Including data capture, image compression and image overlap
Note that you can use your own implementation as well :)
"""

from io import BytesIO
import pyaudio
import cv2
import pyautogui
import numpy as np
from PIL import Image, ImageGrab
from config import *
from datetime import datetime
import mss
import time
import math

# audio setting
FORMAT = pyaudio.paInt16
audio = pyaudio.PyAudio()
streamin = audio.open(
    format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
)
streamout = audio.open(
    format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK
)

# print warning if no available camera
cap = cv2.VideoCapture(0)
if cap.isOpened():
    can_capture_camera = True
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
else:
    can_capture_camera = False

my_screen_size = pyautogui.size()


def getCurrentTime():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def resize_image_to_fit_screen(image, my_screen_size):
    screen_width, screen_height = my_screen_size

    original_width, original_height = image.size

    aspect_ratio = original_width / original_height

    if screen_width / screen_height > aspect_ratio:
        # resize according to height
        new_height = screen_height
        new_width = int(new_height * aspect_ratio)
    else:
        # resize according to width
        new_width = screen_width
        new_height = int(new_width / aspect_ratio)

    # resize the image
    resized_image = image.resize((new_width, new_height), Image.LANCZOS)

    return resized_image


def overlay_camera_images(screen_image, camera_images):
    """
    screen_image: PIL.Image
    camera_images: list[PIL.Image]
    """
    if screen_image is None and camera_images is None:
        print("[Warn]: cannot display when screen and camera are both None")
        return None
    if screen_image is not None:
        screen_image = resize_image_to_fit_screen(screen_image, my_screen_size)

    if camera_images is not None:
        # make sure same camera images
        if not all(img.size == camera_images[0].size for img in camera_images):
            raise ValueError("All camera images must have the same size")

        screen_width, screen_height = (
            my_screen_size if screen_image is None else screen_image.size
        )
        camera_width, camera_height = camera_images[0].size

        # calculate num_cameras_per_row
        num_cameras_per_row = screen_width // camera_width

        # adjust camera_imgs
        if len(camera_images) > num_cameras_per_row:
            adjusted_camera_width = screen_width // len(camera_images)
            adjusted_camera_height = (
                adjusted_camera_width * camera_height
            ) // camera_width
            camera_images = [
                img.resize(
                    (adjusted_camera_width, adjusted_camera_height), Image.LANCZOS
                )
                for img in camera_images
            ]
            camera_width, camera_height = adjusted_camera_width, adjusted_camera_height
            num_cameras_per_row = len(camera_images)

        # if no screen_img, create a container
        if screen_image is None:
            display_image = Image.fromarray(
                np.zeros((camera_width, my_screen_size[1], 3), dtype=np.uint8)
            )
        else:
            display_image = screen_image
        # cover screen_img using camera_images
        for i, camera_image in enumerate(camera_images):
            row = i // num_cameras_per_row
            col = i % num_cameras_per_row
            x = col * camera_width
            y = row * camera_height
            display_image.paste(camera_image, (x, y))

        return display_image
    else:
        return screen_image


def capture_screen(quality=30, width=1280, height=720, period = 2):
    """
    Args:
        quality (int, optional): _description_. Defaults to 30.
        width (int, optional): _description_. Defaults to 1280.
        height (int, optional): _description_. Defaults to 720.

    Returns:
        img_bytes: bytes of the captured image
    """
    constant = 0.03
    st = time.time()
    tot = 0
    screen_shots = []
    while True:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            img = sct.grab(monitor)
            img_np = np.array(img)
            img_np = cv2.resize(img_np, (width, height))  
            _, img_encode = cv2.imencode(".jpg", img_np, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            img_bytes = img_encode.tobytes()
            screen_shots.append(img_bytes)
            tot += 1
        if time.time() - st > period - constant:
            size = 0
            for frame in screen_shots:
                size += len(frame)
            print(f"Total size of {tot} frames: {size} bytes")
            return screen_shots, tot, period
        
def bytes_to_video(screen_shots ,tot, period):
    """
    Args:
        screen_shots (list): list of bytes of captured images
        tot (int): total number of captured images
        period (float): period of capturing images

    Returns:
        video_bytes: bytes of the captured video
        time_cost: time cost of converting bytes to video
    """
    st = time.time()
    fps = tot / period
    fps = math.floor(fps)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    now = datetime.now()
    video_name = f"{now.strftime('%Y-%m-%d_%H-%M-%S')}.mp4"
    video = cv2.VideoWriter(video_name, fourcc, fps, (1280, 720))
    for img in screen_shots:
        img = cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_COLOR)
        video.write(img)
    video.release()
    # video to bytes
    with open(video_name, "rb") as f:
        video_bytes = f.read()
    en = time.time()
    print(f"Convert time: {en - st}")
    return video_bytes, en-st

def capture_camera(camera_index=0, period = 2, resolution=(1280, 720), fps=30, quality=30):
    """
    Args:   
        camera_index (int, optional): index of camera. Defaults to 0.
        period (float, optional): period of capturing images. Defaults to 2.
        resolution (tuple, optional): resolution of camera. Defaults to (1280, 720).
        fps (int, optional): frames per second. Defaults to 30.
        quality (int, optional): quality of captured images. Defaults to 30.

    Returns:
        frames (list): list of bytes of captured images
        tot (int): total number of captured images
        period (float): period of capturing images
    """
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    cap.set(cv2.CAP_PROP_FPS, fps)

    if not cap.isOpened():
        raise Exception(f"无法打开摄像头（索引 {camera_index}）。请检查设备。")

    constant = 0.03
    print(f"开始捕获摄像头帧，目标时间: {period}")
    frames = []
    tot = 0
    st = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"帧捕获失败。")
            break
        frame = cv2.resize(frame, resolution)
        _, frame_encode = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        frames.append(frame_encode.tobytes())
        tot += 1
        if time.time() - st > period - constant:
            size = 0
            for frame in frames:
                size += len(frame)
            print(f"Total size of {tot} frames: {size} bytes")
            cap.release()
            return frames, tot, period
    


def capture_voice():
    return streamin.read(CHUNK)



