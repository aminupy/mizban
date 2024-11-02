import socket


def _get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def get_server_url():
    ip = _get_ip_address()
    url = f'http://{ip}:8000/'

    return url