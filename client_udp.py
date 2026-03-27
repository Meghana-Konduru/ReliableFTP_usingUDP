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

retry_count = 0
max_retries = 2

while True:

    file = None        # file not created yet
    success = True

    while True:

        encrypted_data, _ = client.recvfrom(BUFFER_SIZE)

        try:
            data = cipher.decrypt(encrypted_data)
        except:
            success = False
            break

        # check error BEFORE creating file
        if b"ERROR" in data:
            print(data.decode())
            success = False
            break

        # create file only when first real data comes
        if file is None:
            file = open("received_" + filename, "wb")

        if data == b"END":
            break

        file.write(data)

    # close file only if created
    if file:
        file.close()

    if success:
        client.sendto(b"SUCCESS", (SERVER_IP, SERVER_PORT))
        print("Secure file received successfully")
        break

    else:
        retry_count += 1

        if retry_count <= max_retries:
            print("Retrying transfer...")
            client.sendto(b"RETRY", (SERVER_IP, SERVER_PORT))
        else:
            client.sendto(b"FAILED", (SERVER_IP, SERVER_PORT))
            print("File transfer failed")
            break
