import socket
import sys


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



def get_server_url():
    ip = _get_ip_address()
    url = f'http://{ip}:8000/'

    return url