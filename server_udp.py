import socket
from cryptography.fernet import Fernet
import os

SERVER_IP = "0.0.0.0"
SERVER_PORT = 5001
BUFFER_SIZE = 2048

key = Fernet.generate_key()
cipher = Fernet(key)

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((SERVER_IP, SERVER_PORT))

print("UDP Secure Server started on port", SERVER_PORT)

while True:

    data, client_addr = server.recvfrom(BUFFER_SIZE)

    filename = data.decode()

    print("Client requested:", filename)

    server.sendto(key, client_addr)

    if not os.path.exists(filename):
        server.sendto(cipher.encrypt(b"ERROR: File not found"), client_addr)
        continue

    with open(filename, "rb") as f:

        while True:

            chunk = f.read(1000)

            if not chunk:
                break

            encrypted_data = cipher.encrypt(chunk)

            server.sendto(encrypted_data, client_addr)

    server.sendto(cipher.encrypt(b"END"), client_addr)