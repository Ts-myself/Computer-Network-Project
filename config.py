HELP = (
    "Create         : create an conference\n"
    "Join [conf_id ]: join a conference with conference ID\n"
    "Quit           : quit an on-going conference\n"
    "Cancel         : cancel your on-going conference (only the manager)\n\n"
)

### Server Configuration

SERVER_IP_LOCAL = "127.0.0.1"
SERVER_IP_PUBLIC_HLC = "10.13.132.35"
SERVER_IP_PUBLIC_TJL = "10.20.147.91"
MAIN_SERVER_PORT = 8888
TIMEOUT_SERVER = 5
# DGRAM_SIZE = 1500  # UDP
LOG_INTERVAL = 2

BUFFER_SIZE = 1024
BIG_BUFFER_SIZE = 65535
# CONF_SERVE_PORTS = [8890, 8891, 8892, 8893]
CONF_SERVE_PORTS = {
    'msg': 8890,
    'audio': 8891,
    'screen': 8892,
    'camera': 8893
}
