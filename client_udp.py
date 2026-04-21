import socket
from cryptography.fernet import Fernet
import json
import os
import hashlib
import time

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
SERVER_IP   = "127.0.0.1"
SERVER_PORT = 5001
BUFFER_SIZE = 65535
TIMEOUT     = 10
MAX_RETRIES = 2

SERVER_ADDR = (SERVER_IP, SERVER_PORT)

# ─────────────────────────────────────────────
#  METRICS STORE
# ─────────────────────────────────────────────
metrics = {
    "rtt_samples":      [],   # per-chunk RTT in seconds
    "transfer_start":   0.0,  # time when first data chunk sent
    "transfer_end":     0.0,  # time when END sentinel ACKed
    "session_start":    0.0,  # time of very first packet (filename send)
    "session_end":      0.0,  # time after SUCCESS/FAILED sent
    "bytes_received":   0,
}

# ─────────────────────────────────────────────
#  RECEIVE FILE (one attempt)
# ─────────────────────────────────────────────
def receive_file_attempt(sock, cipher, filename: str, file_size: int, attempt: int):
    output_path    = "received_" + filename
    bytes_written  = 0
    expected_seq   = 0
    decrypt_errors = 0
    sock.settimeout(TIMEOUT)

    rtt_samples = []

    print(f"\n  [Attempt {attempt}/{MAX_RETRIES}] Receiving...")

    # Record start of actual data transfer
    transfer_start = time.time()

    with open(output_path, "wb") as f:
        while True:
            try:
                # Measure RTT: time from sending ACK for previous chunk
                # to receiving the next chunk from server.
                t_recv_start = time.time()
                packet, _    = sock.recvfrom(BUFFER_SIZE)
                t_recv_end   = time.time()
            except socket.timeout:
                print(f"\n  Timeout waiting for chunk (expected seq {expected_seq})...")
                continue

            if len(packet) < 4:
                continue

            seq_bytes = packet[:4]
            payload   = packet[4:]
            seq_num   = int.from_bytes(seq_bytes, "big")

            # END sentinel
            if seq_num == 0xFFFFFFFF:
                transfer_end = time.time()
                metrics["transfer_start"] = transfer_start
                metrics["transfer_end"]   = transfer_end
                try:
                    data = cipher.decrypt(payload)
                    if data == b"END":
                        sock.sendto(b"ACK_END", SERVER_ADDR)
                        break
                except Exception:
                    sock.sendto(b"ACK_END", SERVER_ADDR)
                    break
                continue

            # Duplicate — resend ACK silently
            if seq_num < expected_seq:
                sock.sendto(b"ACK" + seq_bytes, SERVER_ADDR)
                continue

            # Decrypt
            try:
                data = cipher.decrypt(payload)
            except Exception:
                decrypt_errors += 1
                print(f"\n  Decryption failed on seq {seq_num} (error #{decrypt_errors}), waiting for resend...")
                continue

            f.write(data)
            bytes_written += len(data)

            # RTT = time from previous ACK send to receiving this chunk
            # (approximation: inter-packet gap ≈ one round trip for stop-and-wait)
            rtt = t_recv_end - t_recv_start
            rtt_samples.append(rtt)

            t_ack_send = time.time()
            sock.sendto(b"ACK" + seq_bytes, SERVER_ADDR)
            expected_seq = seq_num + 1

            # Progress
            if file_size > 0:
                pct = min(100, int(bytes_written * 100 / file_size))
                bar = "#" * (pct // 2) + "-" * (50 - pct // 2)
                print(f"\r  [{bar}] {pct}%  ({bytes_written}/{file_size} bytes)", end="", flush=True)

    sock.settimeout(None)
    print()

    metrics["rtt_samples"]    += rtt_samples
    metrics["bytes_received"]  = bytes_written

    success = (bytes_written == file_size)
    return success, bytes_written

# ─────────────────────────────────────────────
#  PRINT METRICS
# ─────────────────────────────────────────────
def print_metrics(file_size: int, final_success: bool):
    rtt_samples   = metrics["rtt_samples"]
    transfer_time = metrics["transfer_end"] - metrics["transfer_start"]   # seconds
    session_time  = metrics["session_end"]  - metrics["session_start"]    # seconds

    avg_rtt   = sum(rtt_samples) / len(rtt_samples) if rtt_samples else 0
    min_rtt   = min(rtt_samples) if rtt_samples else 0
    max_rtt   = max(rtt_samples) if rtt_samples else 0

    # Latency (one-way) estimated as RTT / 2
    latency   = avg_rtt / 2

    # Throughput = total bytes received / transfer duration
    throughput_bps  = (file_size / transfer_time) if transfer_time > 0 else 0
    throughput_kbps = throughput_bps / 1024
    throughput_mbps = throughput_bps / (1024 * 1024)

    # End-to-end delay = time from first byte sent to last byte received
    e2e_delay = transfer_time

    print("\n" + "=" * 60)
    print("  NETWORK PERFORMANCE METRICS")
    print("=" * 60)
    print(f"  File size             : {file_size:,} bytes  ({file_size/1024:.2f} KB)")
    print(f"  Bytes received        : {metrics['bytes_received']:,} bytes")
    print()
    print(f"  ── Timing ──────────────────────────────────")
    print(f"  Transfer duration     : {transfer_time:.4f} s")
    print(f"  Total session time    : {session_time:.4f} s  (incl. auth + handshake)")
    print()
    print(f"  ── Throughput ──────────────────────────────")
    print(f"  Throughput            : {throughput_kbps:.2f} KB/s")
   # print(f"                        : {throughput_mbps:.4f} MB/s")
    #print(f"                        : {throughput_bps*8/1000:.2f} Kbps")
    print()
    print(f"  ── Latency & RTT ───────────────────────────")
    print(f"  Avg RTT               : {avg_rtt*1000:.3f} ms")
    #print(f"  Min RTT               : {min_rtt*1000:.3f} ms")
    #print(f"  Max RTT               : {max_rtt*1000:.3f} ms")
    print(f"  Estimated latency     : {latency*1000:.3f} ms  (RTT / 2)")
    print()
    print(f"  ── End-to-End Delay ────────────────────────")
    print(f"  End-to-End delay      : {e2e_delay*1000:.3f} ms")
    print(f"                        : {e2e_delay:.4f} s")
    print()
    print(f"  ── RTT Samples ─────────────────────────────")
    print(f"  Total chunks received : {len(rtt_samples)}")
    if rtt_samples:
        variance = sum((r - avg_rtt)**2 for r in rtt_samples) / len(rtt_samples)
        jitter   = variance ** 0.5
        #print(f"  Jitter (RTT std dev)  : {jitter*1000:.3f} ms")
    print("=" * 60)

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65535)
client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65535)

print("=" * 60)
print("   Secure UDP File Transfer Client")
print("=" * 60)
username = input("Username : ").strip()
password = input("Password : ").strip()
filename = input("Filename : ").strip()
print()

# ── Session start ────────────────────────────
metrics["session_start"] = time.time()

# STEP 1: send filename
client.sendto(filename.encode(), SERVER_ADDR)
print(f"Requested '{filename}' from {SERVER_IP}:{SERVER_PORT}")

# STEP 2: send credentials
creds = json.dumps({"username": username, "password": password})
client.sendto(creds.encode(), SERVER_ADDR)

# STEP 3: auth response
client.settimeout(10)
try:
    auth_resp, _ = client.recvfrom(BUFFER_SIZE)
except socket.timeout:
    print("No response from server. Is the server running?")
    client.close()
    exit(1)
client.settimeout(None)

if auth_resp == b"AUTH_FAIL":
    print("Authentication failed. Wrong username or password.")
    client.close()
    exit(1)
if auth_resp != b"AUTH_OK":
    print(auth_resp.decode())
    client.close()
    exit(1)
print("Authentication successful ✓")

# STEP 4: receive encryption key
client.settimeout(10)
try:
    key, _ = client.recvfrom(BUFFER_SIZE)
except socket.timeout:
    print("Timed out waiting for encryption key.")
    client.close()
    exit(1)
client.settimeout(None)

if key.startswith(b"ERROR"):
    print(key.decode())
    client.close()
    exit(1)

cipher = Fernet(key)
print("Encryption key received ✓")

# STEP 5: ACK key
client.sendto(b"KEY_OK", SERVER_ADDR)

# STEP 6: receive file size
client.settimeout(10)
try:
    size_data, _ = client.recvfrom(BUFFER_SIZE)
except socket.timeout:
    print("Timed out waiting for file size.")
    client.close()
    exit(1)
client.settimeout(None)

file_size = int(size_data.decode())
print(f"File size : {file_size:,} bytes  ({file_size/1024:.1f} KB)")

# STEP 7: ACK file size
client.sendto(b"SIZE_OK", SERVER_ADDR)
print("Starting transfer...")
print("=" * 60)

# ─────────────────────────────────────────────
#  TRANSFER LOOP
# ─────────────────────────────────────────────
final_success = False

for attempt in range(1, MAX_RETRIES + 1):

    success, bytes_written = receive_file_attempt(client, cipher, filename, file_size, attempt)

    # ── ACK Status Report ─────────────────────
    print(f"\n  {'─'*54}")
    print(f"  Attempt {attempt}/{MAX_RETRIES} ACK Status")
    print(f"  {'─'*54}")
    print(f"    Bytes expected  : {file_size:,}")
    print(f"    Bytes received  : {bytes_written:,}")

    if success:
        print(f"    Integrity check : PASSED ✓")
        print(f"    ACK Sent        : SUCCESS")
        print(f"  {'─'*54}")
        client.sendto(b"SUCCESS", SERVER_ADDR)
        final_success = True
        break
    else:
        missing = file_size - bytes_written
        print(f"    Integrity check : FAILED ✗  (missing {missing:,} bytes)")

        if attempt < MAX_RETRIES:
            print(f"    ACK Sent        : RETRY  → attempt {attempt+1} incoming")
            print(f"  {'─'*54}")
            client.sendto(b"RETRY", SERVER_ADDR)
            print(f"\n  Waiting for retransmission from server...")
        else:
            print(f"    ACK Sent        : FAILED  (max retries reached)")
            print(f"  {'─'*54}")
            client.sendto(b"FAILED", SERVER_ADDR)

# ── Session end ──────────────────────────────
metrics["session_end"] = time.time()

# ─────────────────────────────────────────────
#  FINAL RESULT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
if final_success:
    output_path = "received_" + filename
    print(f"  FINAL RESULT : SUCCESS ✓")
    print(f"  File saved as '{output_path}'")
else:
    print(f"  FINAL RESULT : FAILED ✗")
    print(f"  Transfer failed after {MAX_RETRIES} attempts.")
print("=" * 60)

# ─────────────────────────────────────────────
#  PRINT METRICS
# ─────────────────────────────────────────────
print_metrics(file_size, final_success)

client.close()
