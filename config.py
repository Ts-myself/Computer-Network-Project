HELP = (
    "Create         : create an conference\n"
    "Join [conf_id ]: join a conference with conference ID\n"
    "Quit           : quit an on-going conference\n"
    "Cancel         : cancel your on-going conference (only the manager)\n\n"
)

### Server Configuration

SERVER_IP_LOCAL = "127.0.0.1"
SERVER_IP_PUBLIC_HLC = "10.26.52.144"
SERVER_IP_PUBLIC_TJL = "10.20.147.91"
SERVER_IP_PUBLIC_WYT = "10.12.160.247"
SERVER_IP_PUBLIC_WGX = "10.28.61.176"
MAIN_SERVER_PORT = 8888

TIMEOUT_SERVER = 5
# DGRAM_SIZE = 1500  # UDP
LOG_INTERVAL = 2

BUFFER_SIZE = 1024
BIG_BUFFER_SIZE = 65535
CONF_SERVE_PORTS = {
    'control': 8889,
    'msg': 8890,
    'audio': 8891,
    'screen': 8892,
    'camera': 8893
}

SCREEN_TIME_MAX_GAP = 0.3
CAMERA_TIME_MAX_GAP = 0.3
AUDIO_TIME_MAX_GAP = 0.3

SCREEN_SLEEP_INCREASE = 0.01
CAMERA_SLEEP_INCREASE = 0.01

SCREEN_SLEEP_DECREASE = 0.0001
CAMERA_SLEEP_DECREASE = 0.0001

