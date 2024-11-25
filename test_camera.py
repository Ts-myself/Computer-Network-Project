import cv2
import numpy as np
import tempfile
import os
import time

def capture_camera_frames(camera_index=0, frame_count=100, resolution=(1280, 720), fps=24):
    """
    从摄像头捕获指定数量的帧并保存为视频字节流。

    Args:
        camera_index (int): 摄像头索引，默认是0（主摄像头）。
        frame_count (int): 捕获的帧数量。
        resolution (tuple): 视频分辨率 (宽, 高)。
        fps (int): 帧率。

    Returns:
        video_data (bytes): 视频字节流。
        total_time (float): 捕获和保存视频所需的总时间。
    """
    # 打开摄像头
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    cap.set(cv2.CAP_PROP_FPS, fps)

    if not cap.isOpened():
        raise Exception(f"无法打开摄像头（索引 {camera_index}）。请检查设备。")

    frames = []
    print(f"开始捕获摄像头帧，目标帧数: {frame_count}")
    tot_time = 0
    for i in range(frame_count):
        st = time.time()
        ret, frame = cap.read()
        if not ret:
            print(f"帧 {i+1}/{frame_count} 捕获失败。")
            break

        # 调整分辨率
        frame = cv2.resize(frame, resolution)
        # 压缩为JPEG格式以节省存储空间
        _, frame_encode = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
        frames.append(frame_encode.tobytes())
        en = time.time()
        tot_time += en-st
        print(f"捕获帧 {i+1}/{frame_count}，大小: {len(frames[-1])} bytes")
        print(f"耗时: {en-st:.4f}s")

    cap.release()
    print(f"成功捕获 {len(frames)} 帧。")
    print(f"总耗时: {tot_time:.4f}s")

    # 将帧写入视频
    st = time.time()

    # 检查系统支持的编码器
    try:
        fourcc = cv2.VideoWriter_fourcc(*'H264')  # 尝试使用 H.264
    except:
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # 如果失败，切换到 MJPG

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
        temp_file_path = temp_file.name

    video = cv2.VideoWriter(temp_file_path, fourcc, fps, resolution)

    for frame_bytes in frames:
        frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
        video.write(frame)

    video.release()

    # 读取临时文件为字节流
    with open(temp_file_path, "rb") as f:
        video_data = f.read()

    # 在当前文件夹下保存这个视频
    with open("camera.mp4", "wb") as f:
        f.write(video_data)

    # 删除临时文件
    os.remove(temp_file_path)

    en = time.time()
    total_time = en - st

    print(f"总耗时: {total_time:.4f}s")
    print(f"视频字节流大小: {len(video_data)} bytes")

    return video_data, total_time

if __name__ == "__main__":
    frame_count = 100
    resolution = (1280, 720)
    fps = 24
    try:
        video_data, total_time = capture_camera_frames(frame_count=frame_count, resolution=resolution, fps=fps)
        print(f"成功捕获 {frame_count} 帧并保存为视频字节流。")
    except Exception as e:
        print(f"捕获失败: {e}")
