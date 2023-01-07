import socket
import os
import signal
import sys
import sys
import argparse
from urllib.parse import urlparse
import selectors
import struct
import time
import hashlib
from socket import AF_INET, SOCK_DGRAM

# define global variable for (host, port) tuple, the address of the server
address = ()
# Define a constant for our buffer size

BUFFER_SIZE = 1024
MAX_STRING_SIZE = 256

# Selector for helping us select incoming data from the server and messages typed in by the user.

sel = selectors.DefaultSelector()

# UDP Socket for sending messages.

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# User name for tagging sent messages.

user = ''


# function to check if a packet is an acknowledgement
def isAck(data, size, r_seq, seq):
    try:
        packet_data_check = data[:size].decode()
        if "ACK" in packet_data_check and seq == r_seq:
            return True
        else:
            return False
    except UnicodeDecodeError:  # this means that this is an encoded file packet, so return false.
        return False





# SEND AND RECEIVE FUNC MUST BE USING THE SAME SEQ NUM? or they have to coordinate.

# seq number tracker for the sender func
sender_sequence_number = 0

# function to send datagrams over an unreliable ntwrk
def rdt_3_0_send(sock, data):
    # TODO USE sendto() to a specific dest (host, port)

    global sender_sequence_number
    # preparing the packet.
    current_seq = sender_sequence_number
    send_data = data
    size = len(send_data)

    packet_tuple = (current_seq, size, send_data)
    packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s')
    packed_data = packet_structure.pack(*packet_tuple)
    checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")

    packet_tuple = (current_seq, size, send_data, checksum)
    UDP_packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
    UDP_packet = UDP_packet_structure.pack(*packet_tuple)

    # Send data over the unreliable network.
    sock.send(UDP_packet)
    #print("Sending data")

    # start a 2 second timer
    sock.settimeout(2)

    # try:
    global r_received_packet
    global r_addr

    # while the sequence number is correct
    while current_seq == sender_sequence_number:

        # try continually try receive an ACK until theres a timeout
        try:
            while 1:
                received_packet, addr = sock.recvfrom(296)
                r_received_packet = received_packet
                r_addr = addr
                if not received_packet:  # if we dont receive anything, keep trying untile the timer runs out
                    continue
                else:
                    unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
                    UDP_packet = unpacker.unpack(received_packet)
                    break
        except socket.timeout:
            #print("timeout sending DUPLICATE PACKET...")
            rdt_3_0_send(sock, data)
            break


        # Unpack the ack when received

        received_sequence = UDP_packet[0]
        received_size = UDP_packet[1]
        received_data = UDP_packet[2]
        received_checksum = UDP_packet[3]

        # Print out what we received.

        #print("Packet received from: (SEND FUNC) ", r_addr)
        #print("Packet data:", UDP_packet)

        values = (received_sequence, received_size, received_data)
        packer = struct.Struct(f'I I {MAX_STRING_SIZE}s')
        packed_data = packer.pack(*values)
        computed_checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")



        #  [ rdt_rcv(rcvpkt) && notcorrupt(rcvpkt) && isACK(rcvpkt,0 or 1) ]
        # if we recieved a packet, and its not corrupt and its the ack we want.

        if received_checksum == computed_checksum:

            if isAck(received_data, received_size, received_sequence, sender_sequence_number):

                #print('Received and computed checksums match, so packet can be processed')
                received_text = received_data[:received_size].decode()

                #print(f'Message text was:  {received_text}\n')
                if current_seq == 0:
                    sender_sequence_number = 1

                else:
                    sender_sequence_number = 0


            # CHECK TO SEE IF WE HAVE AN INVALID REG MESSG, if we do, print, quit.
            else:
                try:
                    received_data[:received_size].decode()
                    if '402' in received_data[:received_size].decode() or '400' in received_data[:received_size].decode() or '401 in' in received_data[:received_size].decode():
                        print(received_data[:received_size].decode() + " Exiting now...")
                        exit(0)

                    elif '200' in received_data[:received_size].decode():
                        rdt_3_0_recv(sock,296)
                        return

                except UnicodeDecodeError:
                    return

        elif received_checksum != computed_checksum:
            return
            # continue waiting [ rdt_rcv(rcvpkt) && ( corrupt(rcvpkt) || isACK(rcvpkt,1 or 0) ) ]



# seq number tracker for the recv func
recv_sequence_number = 0

# function to recv datagrams over an unreliable ntwrk
def rdt_3_0_recv(sock, size):
    sock.settimeout(False)  # TODO
    global recv_sequence_number

    current_seq = recv_sequence_number
    # message = sock.recv(MAX_STRING_SIZE)
    global r_packet

    while True:
        try:
            sock.setblocking(True)
            while (1):
                received_packet, addr = sock.recvfrom(size)
                if not received_packet:
                    continue
                else:
                    break

        except BlockingIOError:
            print("blocking err")
            continue
        sock.setblocking(False)

        # ******************* chnages here ^

        unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
        UDP_packet = unpacker.unpack(received_packet)
        unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
        UDP_packet = unpacker.unpack(received_packet)

        received_sequence = UDP_packet[0]
        received_size = UDP_packet[1]
        received_data = UDP_packet[2]
        received_checksum = UDP_packet[3]

        # Print out what we received.

        #print("Packet received from: (RCV FUNC) ", addr)
       # print("Packet data:", UDP_packet)

        values = (received_sequence, received_size, received_data)
        packer = struct.Struct(f'I I {MAX_STRING_SIZE}s')
        packed_data = packer.pack(*values)
        computed_checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")

        # RDT 2.2: rdt_rcv(rcvpkt) && (corrupt(rcvpkt) || has_seq1(rcvpkt))
        global sender_sequence_number #INTRODUCE GLOBAL FOR  LINE 232

        if computed_checksum != received_checksum or received_sequence != current_seq and (
        not isAck(received_data, received_size, received_sequence, current_seq)): ###### WHY IS IT SENDER SEQ NUMBER AND WHY IS THAT WORKING?????

            # snd pkt = make_pkt (ACK,(opposite seq num),checksum)
            ack_seq = received_sequence

            ack_data = f'ACK{ack_seq}'.encode()
            ack_size = len(ack_data)

            ack_tuple = (ack_seq, ack_size, ack_data)
            ack_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s')
            packed_ack_data = ack_structure.pack(*ack_tuple)
            ack_checksum = bytes(hashlib.md5(packed_ack_data).hexdigest(), encoding="UTF-8")

            packet_tuple = (ack_seq, ack_size, ack_data, ack_checksum)
            ack_UDP_packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
            ack_UDP_packet = ack_UDP_packet_structure.pack(*packet_tuple)

            sock.send(ack_UDP_packet)

            #try:
               # register = received_data[:received_size].decode()
               # if '200' in register:
                  #  return register
           #except UnicodeDecodeError:
               # pass



            # send the ack packet.

            #print("Sending corrupted or lost pack ACK: " + ack_data.decode())

            return "waiting29420989329409329 holder"

       # wait for a non corrupted packed to come

        elif isAck(received_data, received_size, received_sequence, current_seq):
            return "waiting29420989329409329 holder"


        else:

            # if the packet is not corrupt and the ack is the sequence number in the packet is correct
            if received_checksum == computed_checksum and received_sequence == current_seq and (
                    not isAck(received_data, received_size, received_sequence, current_seq) ):

                # make an acknowledgement packet.
                ack_seq = received_sequence
                ack_data = f'ACK{ack_seq}'.encode()
                ack_size = len(ack_data)

                ack_tuple = (ack_seq, ack_size, ack_data)
                ack_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s')
                packed_ack_data = ack_structure.pack(*ack_tuple)
                ack_checksum = bytes(hashlib.md5(packed_ack_data).hexdigest(), encoding="UTF-8")

                packet_tuple = (ack_seq, ack_size, ack_data, ack_checksum)
                ack_UDP_packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
                ack_UDP_packet = ack_UDP_packet_structure.pack(*packet_tuple)

                # send the ack packet.
                sock.send(ack_UDP_packet)
               # print("Sending  " + ack_data.decode())

                # update the seq number
                if received_sequence == 0:
                    recv_sequence_number = 1
                else:
                    recv_sequence_number = 0

               # print('Received and computed checksums match, so packet can be processed')
                try:
                    received_text = received_data[:received_size].decode()
                except(UnicodeDecodeError):
                    received_text = 'file'
                    pass

                #print(f'Message text was:  {received_text}')

                return received_text

            #else:
                #print('Received and computed checksums do not match, so packet is corrupt and discarded')


# Signal handler for graceful exiting.  Let the server know when we're gone.

def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message = f'DISCONNECT {user} CHAT/1.0\n'
    # client_socket.RDT.rdt_3_0_send()(message.encode())

    rdt_3_0_send(client_socket, message.encode())
    sys.exit(0)


# Simple function for setting up a prompt for the user.

def do_prompt(skip_line=False):
    if (skip_line):
        print("")
    print("> ", end='', flush=True)


# Read a single line (ending with \n) from a socket and return it.
# We will strip out the \r and the \n in the process.

def get_line_from_socket(sock):
    # We're Sending packets now, so we dont need to read chunk by chunk, packets are a constant length of 296

    line = rdt_3_0_recv(sock, 296)

    return line


# Function to handle incoming messages from server.  Also look for disconnect messages to shutdown and messages for sending and receiving files.

def handle_message_from_server(sock, mask):
    message = get_line_from_socket(sock)
    words = message.split(' ')
    print()


    if words[0] == 'waiting29420989329409329':
        #print("im here")
        do_prompt()
        return

    # Handle server disconnection.
    elif words[0] == 'DISCONNECT':
        print('Disconnected from server ... exiting!')
        sys.exit(0)

    # Handle file attachment request.
    elif words[0] == 'ATTACH':
        sock.setblocking(True)
        filename = words[1].rstrip("\n")
        if (os.path.exists(filename)):
            filesize = os.path.getsize(filename)
            header = f'Content-Length: {filesize}\n'
            # sock.RDT.rdt_3_0_send(header.encode())
            rdt_3_0_send(sock, header.encode())
            with open(filename, 'rb') as file_to_send:
                while True:
                    chunk = file_to_send.read(
                        256)  # most likely going to need to make buffer size = to 256, (data in packet size)
                    if chunk:
                        # sock.RDT.rdt_3_0_send(chunk)
                        rdt_3_0_send(sock, chunk)

                    else:
                        print("File Transferred.")
                        do_prompt()
                        break
        else:
            header = f'Content-Length: -1\n'
            # sock.RDT.rdt_3_0_send()(header.encode())
            rdt_3_0_send(sock, header.encode())
        sock.setblocking(False)

    # Handle file attachment request.

    elif words[0] == 'ATTACHMENT':
        filename = words[1]
        sock.setblocking(True)
        print(f'Incoming file: {filename}')
        origin = get_line_from_socket(sock)
        print(origin)
        contentlength = get_line_from_socket(sock)
        print(contentlength)
        length_words = contentlength.split(' ')
        if (len(length_words) != 2) or (length_words[0] != 'Content-Length:'):
            print('Error:  Invalid attachment header')
        else:
            bytes_read = 0
            bytes_to_read = int(length_words[1])
            with open(filename, 'wb') as file_to_write:
                while (bytes_read < bytes_to_read):
                    # chunk = sock.RDT.rdt_1_0_receive(BUFFER_SIZE)
                    chunk = rdt_3_0_recv(sock, BUFFER_SIZE)
                    bytes_read += len(chunk)
                    file_to_write.write(chunk)
        sock.setblocking(False)
        do_prompt()

    # Handle regular messages.

    else:
        print(message)
        do_prompt()


# Function to handle incoming messages from server.

def handle_keyboard_input(file, mask):
    line = sys.stdin.readline()
    message = f'@{user}: {line}'
    # client_socket.RDT.rdt_3_0_send(message.encode())

    rdt_3_0_send(client_socket, message.encode())
    do_prompt()


# Our main function.

def main():
    global user
    global client_socket

    # Register our signal handler for shutting down.

    signal.signal(signal.SIGINT, signal_handler)

    # Check command line arguments to retrieve a URL.

    parser = argparse.ArgumentParser()
    parser.add_argument("user", help="user name for this user on the chat service")
    parser.add_argument("server", help="URL indicating server location in form of chat://host:port")
    parser.add_argument('-f', '--follow', nargs=1, default=[], help="comma separated list of users/topics to follow")
    args = parser.parse_args()

    # Check the URL passed in and make sure it's valid.  If so, keep track of
    # things for later.

    try:
        server_address = urlparse(args.server)
        if ((server_address.scheme != 'chat') or (server_address.port == None) or (server_address.hostname == None)):
            raise ValueError
        host = server_address.hostname
        port = server_address.port

        global address
        address = (host, port)

    except ValueError:
        print('Error:  Invalid server.  Enter a URL of the form:  chat://host:port')
        sys.exit(1)
    user = args.user
    follow = args.follow

    # Now we try to make a connection to the server.

    print('Connecting to server ...')
    try:
        client_socket.connect((host, port))
    except ConnectionRefusedError:
        print('Error:  That host or port is not accepting connections.')
        sys.exit(1)

    # The connection was successful, so we can prep and send a registration message.

    print('Connection to server established. Sending intro message...\n')
    message = f'REGISTER {user} CHAT/1.0\n'
    # client_socket.rdt_3_0_send(message.encode())

    rdt_3_0_send(client_socket, message.encode())

    # If we have terms to follow, we send them now.  Otherwise, we send an empty line to indicate we're done with registration.

    if follow != []:
        message = f'Follow: {follow[0]}\n\n'
    else:
        message = '\n'
    # client_socket.RDT.rdt_3_0_send(message.encode())
    rdt_3_0_send(client_socket, message.encode())

    # Receive the response from the server and start taking a look at it

    response_line = get_line_from_socket(client_socket)
    response_list = response_line.split(' ')

    # If an error is returned from the server, we dump everything sent and
    # exit right away.

    # if we received garbage, wait until we receive non garbage
    if response_line == "waiting29420989329409329 holder":

        while response_line ==  "waiting29420989329409329 holder":
            print("im waiting here")
            response_line = get_line_from_socket(client_socket)
            print(response_line)


    if response_list[0] != '200':
        print('Error:  An error response was received from the server.  Details:\n')
        print(response_line)
        print('Exiting now ...')
        sys.exit(1)
    else:
        print('Registration successful.  Ready for messaging!')

    # Set up our selector.

    client_socket.setblocking(False)
    sel.register(client_socket, selectors.EVENT_READ, handle_message_from_server)
    sel.register(sys.stdin, selectors.EVENT_READ, handle_keyboard_input)

    # Prompt the user before beginning.

    do_prompt()

    # Now do the selection.

    while (True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)


if __name__ == '__main__':
    main()
