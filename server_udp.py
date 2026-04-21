import socket
from cryptography.fernet import Fernet
import os
import json
import hashlib
import threading
import queue

SERVER_IP   = "0.0.0.0"
SERVER_PORT = 5001
BUFFER_SIZE = 65535
CHUNK_SIZE  = 8192
TIMEOUT     = 10
MAX_RETRIES = 2

USERS = {
    "alice":    hashlib.sha256(b"alice123").hexdigest(),
    "bob":      hashlib.sha256(b"bob123").hexdigest(),
    "architha": hashlib.sha256(b"architha").hexdigest(),
    "meghana":  hashlib.sha256(b"meghana").hexdigest(),
}

print_lock  = threading.Lock()
client_queues  = {}
client_threads = {}
client_count   = 0
client_lock    = threading.Lock()

def log(client_id, msg):
    with print_lock:
        print(f"[Client {client_id}] {msg}")

def authenticate(server_sock, addr, client_id) -> bool:
    try:
        raw = client_queues[addr].get(timeout=10)
        creds = json.loads(raw.decode())
        uname = creds.get("username", "")
        phash = hashlib.sha256(creds.get("password", "").encode()).hexdigest()
        if USERS.get(uname) == phash:
            server_sock.sendto(b"AUTH_OK", addr)
            log(client_id, f"Auth SUCCESS for user '{uname}'")
            return True
        else:
            server_sock.sendto(b"AUTH_FAIL", addr)
            log(client_id, f"Auth FAILED for user '{uname}'")
            return False
    except Exception as e:
        server_sock.sendto(b"AUTH_FAIL", addr)
        log(client_id, f"Auth error: {e}")
        return False

def send_file_reliably(server_sock, cipher, filename, addr, client_id, attempt) -> bool:
    file_size  = os.path.getsize(filename)
    bytes_sent = 0
    seq        = 0

    log(client_id, f"[Attempt {attempt}/{MAX_RETRIES}] Starting transfer ({file_size/1024:.1f} KB)")

    with open(filename, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            payload = cipher.encrypt(chunk)
            packet  = seq.to_bytes(4, "big") + payload
            retries = 0
            acked   = False

            while retries < 10:
                server_sock.sendto(packet, addr)
                try:
                    ack = client_queues[addr].get(timeout=TIMEOUT)
                    if ack == b"ACK" + seq.to_bytes(4, "big"):
                        acked = True
                        break
                except Exception:
                    retries += 1
                    log(client_id, f"Timeout on seq {seq}, retry {retries}/10")

            if not acked:
                log(client_id, f"Chunk {seq} failed after 10 retries. Aborting.")
                return False

            bytes_sent += len(chunk)
            pct = int(bytes_sent * 100 / file_size)
            with print_lock:
                print(f"\r  [Client {client_id}] Sending... {pct}%  ({bytes_sent}/{file_size} bytes)", end="", flush=True)
            seq += 1

    with print_lock:
        print()

    end_packet = (0xFFFFFFFF).to_bytes(4, "big") + cipher.encrypt(b"END")
    for _ in range(10):
        server_sock.sendto(end_packet, addr)
        try:
            ack = client_queues[addr].get(timeout=TIMEOUT)
            if ack == b"ACK_END":
                return True
        except Exception:
            log(client_id, "Timeout on END sentinel, resending...")

    return False

def handle_client(server_sock, client_addr, filename, client_id):
    log(client_id, f"{client_addr} -> requested '{filename}'")

    if not authenticate(server_sock, client_addr, client_id):
        del client_queues[client_addr]
        return

    if not os.path.exists(filename):
        server_sock.sendto(f"ERROR: File '{filename}' not found".encode(), client_addr)
        log(client_id, "FAILED - file not found")
        del client_queues[client_addr]
        return

    file_size = os.path.getsize(filename)
    log(client_id, f"File found: {file_size/1024:.1f} KB")

    key    = Fernet.generate_key()
    cipher = Fernet(key)
    server_sock.sendto(key, client_addr)

    ack = client_queues[client_addr].get(timeout=10)
    if ack != b"KEY_OK":
        log(client_id, "No KEY_OK, aborting")
        del client_queues[client_addr]
        return

    server_sock.sendto(str(file_size).encode(), client_addr)

    ack = client_queues[client_addr].get(timeout=10)
    if ack != b"SIZE_OK":
        log(client_id, "No SIZE_OK, aborting")
        del client_queues[client_addr]
        return

    transfer_success = False

    for attempt in range(1, MAX_RETRIES + 1):
        ok = send_file_reliably(server_sock, cipher, filename, client_addr, client_id, attempt)

        if ok:
            try:
                verdict = client_queues[client_addr].get(timeout=15).decode()
            except Exception:
                verdict = "TIMEOUT"

            log(client_id, f"--- Attempt {attempt} ACK Status: {verdict} ---")

            if verdict == "SUCCESS":
                transfer_success = True
                break
            elif verdict == "RETRY" and attempt < MAX_RETRIES:
                log(client_id, f"Client requested retry. Retransmitting (attempt {attempt+1}/{MAX_RETRIES})...")
            else:
                log(client_id, f"Client reported failure on attempt {attempt}.")
                if attempt == MAX_RETRIES:
                    break
        else:
            log(client_id, f"Transfer aborted on attempt {attempt} (too many timeouts).")
            server_sock.sendto(b"TRANSFER_FAILED", client_addr)

    if transfer_success:
        log(client_id, "✓ FINAL STATUS: File transfer SUCCESSFUL\n")
    else:
        log(client_id, f"✗ FINAL STATUS: File transfer FAILED after {MAX_RETRIES} attempts\n")

    if client_addr in client_queues:
        del client_queues[client_addr]

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65535)
server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65535)
server.bind((SERVER_IP, SERVER_PORT))

print(f"UDP Secure Multi-Client Server listening on port {SERVER_PORT} ...")
print(f"Max retransmissions : {MAX_RETRIES}")
print(f"Authorised users    : {', '.join(USERS.keys())}\n")

while True:
    data, addr = server.recvfrom(BUFFER_SIZE)

    with client_lock:
        if addr not in client_queues:
            client_count += 1
            cid = client_count
            q   = queue.Queue()
            client_queues[addr] = q

            t = threading.Thread(
                target=handle_client,
                args=(server, addr, data.decode().strip(), cid),
                daemon=True
            )
            client_threads[addr] = t
            t.start()
        else:
            client_queues[addr].put(data)
