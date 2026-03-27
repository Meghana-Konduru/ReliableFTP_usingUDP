Title: Reliable File Transfer protocol using UDP
Team : Architha Sidharth Panicker , Ashmitha Sri Anand , Konduru Meghana

---------1️. Abstract---------

Problem Statement:
UDP is a fast transport protocol but does not provide reliability. 
It does not guarantee:
-Packet delivery
-Correct packet order
-Error detection and recovery
-Protection against packet loss

Because of these limitations, file transfer over UDP may result in corrupted or incomplete files.

This project focuses on the design and implementation of a custom Reliable File Transfer Protocol over UDP using Python, ensuring accurate, ordered, resumable, and integrity-verified file transmission while maintaining high performance.
Scope

This project focuses on:
-> Implementing reliable file transfer over UDP
-> Chunk-based file transmission
-> Sequence numbering and acknowledgment mechanism
-> Timeout and retransmission handling
-> Checksum-based error detection
-> Resume functionality after interruption
-> Multi-client support using Python threading
-> Performance evaluation under varying network conditions


---------2️. Architecture Design---------

Chosen Architecture : Client–Server : Multi-Client

A central Server manages file storage and handles client requests.
Multiple Clients can upload or download files simultaneously.
Communication occurs using UDP sockets.
Reliability mechanisms such as sequence numbering, acknowledgments, checksum verification, timeout, and retransmission are implemented at the application layer.
Python’s threading or multiprocessing modules will be used to handle multiple clients concurrently.


---------3️. Architectural Workflow---------- 

Step 1: Client sends file request to server
Step 2: Server responds with file metadata
Step 3: File is divided into fixed-size chunks
Step 4: Each chunk is sent with:
Sequence number
Checksum
Packet type
Step 5: Client verifies checksum and sends ACK
Step 6: If ACK not received within timeout → retransmission
Step 7: Transfer continues until completion
Step 8: Resume transfer if interrupted using last acknowledged sequence number


---------4️. Relevance of Architecture Choice---------

The Client–Server model is chosen because:
-Centralized file management
-Easier synchronization
-Scalable to multiple users
-Reflects real-world FTP systems

UDP is chosen to:
-Reduce protocol overhead
-Achieve higher throughput compared to TCP
-Allow implementation of custom reliability mechanisms


Python is chosen because:
-Simple and readable syntax for faster development
-Strong networking support using the socket module
-Built-in concurrency support using threading and multiprocessing
-Availability of libraries like hashlib for checksum generation
-Cross-platform compatibility


-------5️. Objectives--------

-To design a reliable data transfer mechanism over UDP.
-To implement packet sequencing and acknowledgment system.
-To ensure file integrity using checksum validation.
-To support multi-client concurrent file transfers.


-------6️. Functional Requirements-------

The system shall include:
-UDP-based client-server communication
-File chunking mechanism
-Custom packet format
-Sequence numbering
-ACK mechanism
-Timeout and retransmission logic
-Checksum verification
-Resume transfer functionality

--------7️. Software Requirements--------

Programming Language: Python
Platform: Windows/Linux/macOS
Compiler: Python Interpreter
Networking libraries: Python Standard Library


--------8️. Hardware Requirements---------

RAM: 4GB (Minimum)
Processor: Dual Core 2.0 GHz or Greater
Operating System Architecture: 64 bit x64
Network Interface: Ethernet/WiFi Adapter


-------9️. Performance Evaluation Parameters-------

The system performance will be evaluated using:
Throughput (MB/s)
Packet loss rate
End-to-end delay
Retransmission count
Total file transfer time
CPU and memory usage


--------10. Expected Outcome--------

The system is expected to:

Successfully transfer files reliably over UDP
Detect and retransmit lost packets
Maintain correct packet order
Resume interrupted transfers
Ensure final file integrity - hash match with original file
Handle multiple clients concurrently

The project demonstrates implementation of transport-layer reliability mechanisms at the application layer.


===== Setup Steps ======

* Install Python 3.8+
* Install dependency: `pip install cryptography`
* Keep server.py and client.py in same folder
* Place the file to send in server folder
* Update server IP in client.py
* Run server: `python server.py`
* Run client (new terminal): `python client.py`
* Enter filename to download
* Received file saved as `received_filename`


====== Usage Instructions ======

* Start the server: Run `python server.py`
* Run the client on another terminal/system: Run `python client.py`
* Enter the filename when prompted
* Server encrypts and sends the file using UDP
* Client decrypts and saves the file
* Downloaded file will be saved as: `received_filename`
* If packet loss or error occurs, the client automatically retries (max 2 times)
* If the file does not exist, an error message is displayed


