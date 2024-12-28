import socket
import sys
from random import randint


def _get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError as e:
        print("You Should first connect to a network for sharing your file through Mizban!")
        print("Connect to your local area network and than run Mizban again.")
        sys.exit(1)



def get_server_url(port: int):
    ip = _get_ip_address()
    url = f'http://{ip}:{port}/'

    return url

def is_port_busy(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def choose_port() -> int:
    while True:
        port = randint(10000, 65500)
        if not is_port_busy(port):
            return port