from util import *

frame, tot, ack = capture_camera()

img = frame[0]
# frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
img = cv2.imdecode(np.frombuffer(frame[0], np.uint8), cv2.IMREAD_COLOR)
cv2.imshow("frame", img)
cv2.waitKey(0)
