import socket
from cryptography.fernet import Fernet

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5001
BUFFER_SIZE = 2048

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

filename = input("Enter filename to download: ")

client.sendto(filename.encode(), (SERVER_IP, SERVER_PORT))

# receive encryption key
key, _ = client.recvfrom(BUFFER_SIZE)

cipher = Fernet(key)

file = open("received_" + filename, "wb")

while True:

    encrypted_data, _ = client.recvfrom(BUFFER_SIZE)

    data = cipher.decrypt(encrypted_data)

    if data == b"END":
        break

    if b"ERROR" in data:
        print(data.decode())
        break

    file.write(data)

file.close()

print("Secure file received successfully")