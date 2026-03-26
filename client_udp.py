import socket
from cryptography.fernet import Fernet

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5001
BUFFER_SIZE = 2048

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

filename = input("Enter filename to download: ")

client.sendto(filename.encode(), (SERVER_IP, SERVER_PORT))

key, _ = client.recvfrom(BUFFER_SIZE)

cipher = Fernet(key)

success = True
file = None   # file will open only if data is valid

while True:

    encrypted_data, _ = client.recvfrom(BUFFER_SIZE)

    data = cipher.decrypt(encrypted_data)

    # check error first
    if b"ERROR" in data:
        print(data.decode())
        success = False
        break

    # end of file
    if data == b"END":
        break

    # open file only when actual data arrives
    if file is None:
        file = open("received_" + filename, "wb")

    file.write(data)

# close file if opened
if file:
    file.close()

if success:
    print("Secure file received successfully")
else:
    print("File transfer failed")
