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
import struct

# audio setting
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
BYTES_PER_SAMPLE = 2


def generate_wav_header(sample_rate, bits_per_sample, channels):
    """生成 WAV 格式头部"""
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8

    wav_header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',             # ChunkID
        36 + CHUNK,          # ChunkSize
        b'WAVE',             # Format
        b'fmt ',             # Subchunk1ID
        16,                  # Subchunk1Size
        1,                   # AudioFormat (PCM)
        channels,            # NumChannels
        sample_rate,         # SampleRate
        byte_rate,           # ByteRate
        block_align,         # BlockAlign
        bits_per_sample,     # BitsPerSample
        b'data',             # Subchunk2ID
        0                    # Subchunk2Size
    )
    return wav_header



# my_screen_size = pyautogui.size()

# # 初始化摄像头
# cap = cv2.VideoCapture(0)
# cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # 设置摄像头宽度
# cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # 设置摄像头高度

# # 获取屏幕尺寸
# screen_width, screen_height = pyautogui.size()

# while True:
#     # --- 捕获屏幕录像 ---
#     screen = ImageGrab.grab()  # 获取屏幕截图 (PIL Image)
#     screen_np = np.array(screen)  # 转换为 NumPy 数组
#     screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)  # 转换为 BGR 格式供 OpenCV 显示

#     # --- 捕获摄像头画面 ---
#     ret, camera_frame = cap.read()
#     if not ret:
#         print("摄像头捕获失败")
#         break

#     # 调整屏幕录像大小以便拼接
#     screen_resized = cv2.resize(screen_bgr, (640, 480))

#     # --- 拼接屏幕录像和摄像头画面 ---
#     combined_frame = np.hstack((screen_resized, camera_frame))  # 水平拼接
#     # 如果需要垂直拼接，使用 np.vstack()

#     # --- 显示拼接画面 ---
#     cv2.imshow("Screen and Camera", combined_frame)

#     # 按下 'q' 键退出
#     if cv2.waitKey(1) & 0xFF == ord("q"):
#         break

# # 释放资源
# cap.release()
# cv2.destroyAllWindows()


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


def capture_screen():
    # capture screen with the resolution of display
    # img = pyautogui.screenshot()
    img = ImageGrab.grab()
    return img


def capture_camera():
    # capture frame of camera
    ret, frame = cap.read()
    if not ret:
        raise Exception("Fail to capture frame from camera")
    return Image.fromarray(frame)


def capture_voice():
    return streamin.read(CHUNK)


def compress_image(image, format="JPEG", quality=85):
    """
    compress image and output Bytes

    :param image: PIL.Image, input image
    :param format: str, output format ('JPEG', 'PNG', 'WEBP', ...)
    :param quality: int, compress quality (0-100), 85 default
    :return: bytes, compressed image data
    """
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format=format, quality=quality)
    img_byte_arr = img_byte_arr.getvalue()

    return img_byte_arr


def decompress_image(image_bytes):
    """
    decompress bytes to PIL.Image
    :param image_bytes: bytes, compressed data
    :return: PIL.Image
    """
    img_byte_arr = BytesIO(image_bytes)
    image = Image.open(img_byte_arr)

    return image
