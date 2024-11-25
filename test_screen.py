from util import *


if __name__ == "__main__":
    screen_shots, tot, period = capture_screen(quality=30, width=1280, height=720, period = 2)
    video_bytes, time_cost = bytes_to_video(screen_shots, tot, period)
    print(f"Video bytes: {len(video_bytes)}")
    print(f"Time cost: {time_cost}")

