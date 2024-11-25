from util import *


if __name__ == "__main__":
    camera_index=0
    period = 2
    resolution=(1280, 720)
    fps=30
    quality=30
    frames, tot, period = capture_camera(camera_index=camera_index, period=period, resolution=resolution, fps=fps, quality=quality)
    video_bytes, time_cost = bytes_to_video(frames, tot, period)
    print(f"Video bytes: {len(video_bytes)}")
    print(f"Time cost: {time_cost}")
    
