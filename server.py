import socket
import os
import datetime
import signal
import sys
import selectors
from string import punctuation
import hashlib
import struct
import time

# Constant for our buffer size

BUFFER_SIZE = 1024
MAX_STRING_SIZE = 256

# Selector for helping us select incoming data and connections from multiple sources.

sel = selectors.DefaultSelector()

# Client list for mapping connected clients to their connections.

client_list = []


# boolean function to check if a packet is an acknowledgement
def isAck(data, size, r_seq,  seq):


    try:

        # check if the pack is an ACK, if its the one we want, return True.
        packet_data_check = data[:size].decode()
        if "ACK" in packet_data_check and seq == r_seq:
            return True
        else:
            return False
    except UnicodeDecodeError: # this means that this is an encoded file packet, so return false.
        return False




# sequence number variable for the sender function
sender_sequence_number = 0

# function to send data over an unreliable ntwrk
def rdt_3_0_send(sock, data, address):




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
    sock.sendto(UDP_packet, address)
    #print("Sending data")


    # start a 2 second timer
    sock.settimeout(2)


    # while the sequence number is correct
    while current_seq == sender_sequence_number:

        # try continually try receive an ACK until theres a timeout
        try:
            while 1:
                received_packet,addr = sock.recvfrom(296)
                #r_addr = addr
                if not received_packet: #if we dont receive anything, keep trying untile the timer runs out
                    continue
                else:
                    unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
                    UDP_packet = unpacker.unpack(received_packet)
                    break
        except socket.timeout:
            #print("timeout occurred in the clients sender, resending data...")
            rdt_3_0_send(sock=sock, data=data, address= address)
            return

        # Unpack the ack when received

        received_sequence = UDP_packet[0]
        received_size = UDP_packet[1]
        received_data = UDP_packet[2]
        received_checksum = UDP_packet[3]

        # Print out what we received.

        #print("Packet received from: (SEND FUNC)", address)
        #print("Packet data:", UDP_packet)

        values = (received_sequence, received_size, received_data)
        packer = struct.Struct(f'I I {MAX_STRING_SIZE}s')
        packed_data = packer.pack(*values)
        computed_checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")


        #  [ rdt_rcv(rcvpkt) && notcorrupt(rcvpkt) && isACK(rcvpkt,0 or 1) ]
        #if we recieved a packet, and its not corrupt and its the ack we want.

        if received_checksum == computed_checksum and isAck(received_data, received_size, received_sequence, sender_sequence_number):

            #print('Received and computed checksums match, so packet can be processed')
            received_text = received_data[:received_size].decode()

            #print(f'Message text was:  {received_text}\n')
            if current_seq == 0:
                sender_sequence_number = 1
            else:
                sender_sequence_number = 0

        else:

            # continue waiting [ rdt_rcv(rcvpkt) && ( corrupt(rcvpkt) || isACK(rcvpkt,1 or 0) ) ]
            break


# sequnce number for the receiver function
recv_sequence_number = 0

# function to receive data over an unreliable ntwrk
def rdt_3_0_recv(sock,size):
    global recv_sequence_number


    current_seq = recv_sequence_number
    #message = sock.recv(MAX_STRING_SIZE)

    while True:
      try:
          sock.setblocking(True)
          while 1:
              received_packet, addr = sock.recvfrom(size)
              if not received_packet:
                  continue
              else:
                  break
      except BlockingIOError:
          print("blocking err")
          continue

      sock.setblocking(False)


      unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
      UDP_packet = unpacker.unpack(received_packet)
      unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
      UDP_packet = unpacker.unpack(received_packet)

      received_sequence = UDP_packet[0]
      received_size = UDP_packet[1]
      received_data = UDP_packet[2]
      received_checksum = UDP_packet[3]

      # Print out what we received.

      #print("Packet received from: (RCV FUNC)", addr)
      #print("Packet data:", UDP_packet)

      values = (received_sequence, received_size, received_data)
      packer = struct.Struct(f'I I {MAX_STRING_SIZE}s')
      packed_data = packer.pack(*values)
      computed_checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")


      # RDT 2.2: rdt_rcv(rcvpkt) && (corrupt(rcvpkt) || has_seq1(rcvpkt))

      #dont resend ACKs for ACKs??
      if computed_checksum != received_checksum or received_sequence != current_seq and (not isAck(received_data, received_size, received_sequence, sender_sequence_number) ):

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

        # send the ack packet.
        sock.sendto(ack_UDP_packet, addr)
        #print("Sending corrupted or lost pack ACK: " + ack_data.decode())

        # code word to wait until something useful appears in the socket basicallt
        return "waiting29420989329409329", addr, "waiting29420989329409329"

         # wait for a non corrupted packed to come
      elif isAck(received_data, received_size, received_sequence, sender_sequence_number):

          # code word to wait until something useful appears in the socket basicallt
          return "waiting29420989329409329", addr, "waiting29420989329409329"

      else:

          if received_checksum == computed_checksum and received_sequence == current_seq and (isAck(received_data, received_size, received_sequence, sender_sequence_number) == False):

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
            sock.sendto(ack_UDP_packet,addr)
            #print("Sending  " + ack_data.decode())

            # update the seq number
            if recv_sequence_number == 0:
                recv_sequence_number = 1
            else:
                recv_sequence_number = 0

            #print('Received and computed checksums match, so packet can be processed')
            try:
                received_text = received_data[:received_size].decode()
            except(UnicodeDecodeError):
                received_text = 'file'
                pass

            #print(f'Message text was:  {received_text}')

            return received_text, addr, received_data[
                                        :received_size]

          #else:
            #print('Received and computed checksums do not match, so packet is corrupt and discarded')





# Signal handler for graceful exiting.  We let clients know in the process so they can disconnect too.

def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message = 'DISCONNECT CHAT/1.0\n'
    for reg in client_list:
        pass
        # rdt_3_0_send(address=reg[1], message =message.encode(), soc )
        # reg[1].send(message.encode()) ####

    sys.exit(0)


# Read a single line (ending with \n) from a socket and return it.
# We will strip out the \r and the \n in the process.


def get_line_from_socket(sock):

    unpacked_packet = rdt_3_0_recv(sock=sock, size=296)


    done = False
    line = unpacked_packet[0]
    if line == "\n":
        line = ""

    return line, unpacked_packet[1]


# Search the client list for a particular user.

def client_search(user):
    for reg in client_list:
        if reg[0] == user:
            return reg[1]
    return None


# Search the client list for a particular user by their socket.

# NEED TO CHANGE THIS TO ADDRESS
def client_search_by_addr(addr):
    for reg in client_list:
        if reg[1] == addr:
            return reg[0]
    return None


# Add a user to the client list.

# INSTEAD OF CONN MAKE IT ADDRESS
def client_add(user, addr, follow_terms):
    registration = (user, addr, follow_terms)
    client_list.append(registration)


# Remove a client when disconnected.

def client_remove(user):
    for reg in client_list:
        if reg[0] == user:
            client_list.remove(reg)
            break


# Function to list clients.

def list_clients():
    first = True
    list = ''
    for reg in client_list:
        if first:
            list = reg[0]
            first = False
        else:
            list = f'{list}, {reg[0]}'
    return list


# Function to return list of followed topics of a user.

def client_follows(user):
    for reg in client_list:
        if reg[0] == user:
            first = True
            list = ''
            for topic in reg[2]:
                if first:
                    list = topic
                    first = False
                else:
                    list = f'{list}, {topic}'
            return list
    return None


# Function to add to list of followed topics of a user, returning True if added or False if topic already there.

def client_add_follow(user, topic):
    for reg in client_list:
        if reg[0] == user:
            if topic in reg[2]:
                return False
            else:
                reg[2].append(topic)
                return True
    return None


# Function to remove from list of followed topics of a user, returning True if removed or False if topic was not already there.

def client_remove_follow(user, topic):
    for reg in client_list:
        if reg[0] == user:
            if topic in reg[2]:
                reg[2].remove(topic)
                return True
            else:
                return False
    return None


# Function to read messages from clients.

def read_message(sock, mask):

    tuple = get_line_from_socket(sock)  # the message

    message = tuple[0]
    address = tuple[1]

    # if we are registering a client
    if message.split(" ")[0] == 'REGISTER' and message.split(" ")[2] == 'CHAT/1.0\n' :
        accept_client(sock, message, address)

    else:
        pass


    if message == '':
        print('Closing connection')
        #sel.unregister(sock)
        #sock.close()

    # Receive the message.

    # code word to wait until something useful appears in the socket basicallt
    if message =='waiting29420989329409329':
        pass # do nothing


    else:
        user = client_search_by_addr(address)
        print(f'Received message from user {user}:  ' + message)
        words = message.split(' ')

        # Check for client disconnections.

        if words[0] == 'DISCONNECT':
            print('Disconnecting user ' + user)
            client_remove(user)


        # Check for specific commands.

        elif ((len(words) == 2) and ((words[1].rstrip("\n") == '!list') or (words[1].rstrip("\n") == '!exit') or (
                words[1].rstrip("\n") == '!follow?'))):
            if words[1].rstrip("\n") == '!list':
                response = list_clients() + '\n'
                rdt_3_0_send(sock=sock, data=response.encode(), address=address)
                # sock.RDT.rdt_3_0_send(response.encode())
            elif words[1].rstrip("\n") == '!exit':
                print('Disconnecting user ' + user)
                response = 'DISCONNECT CHAT/1.0\n'
                rdt_3_0_send(sock=sock, data=response.encode(), address=address)
                # sock.RDT.rdt_3_0_send(response.encode())
                client_remove(user)
                #sel.unregister(sock)
                #sock.close()
            elif words[1].rstrip("\n") == '!follow?':
                response = client_follows(user) + '\n'
                rdt_3_0_send(sock=sock, data=response.encode(), address=address)
                # sock.RDT.rdt_3_0_send(response.encode())

        # Check for specific commands with a parameter.

        elif ((len(words) == 3) and ((words[1].rstrip("\n") == '!follow') or (words[1].rstrip("\n") == '!unfollow'))):
            if words[1].rstrip("\n") == '!follow':
                topic = words[2]
                if client_add_follow(user, topic):
                    response = f'Now following {topic}\n'
                else:
                    response = f'Error:  Was already following {topic}\n'

                # sock.RDT.rdt_3_0_send(response.encode())

                rdt_3_0_send(sock=sock, data=response.encode(), address=address)
            elif words[1].rstrip("\n") == '!unfollow':
                topic = words[2]
                if topic == '@all':
                    response = 'Error:  All users must follow @all\n'
                elif topic == '@' + user:
                    response = 'Error:  Cannot unfollow yourself\n'
                elif client_remove_follow(user, topic):
                    response = f'No longer following {topic}\n'
                else:
                    response = f'Error:  Was not following {topic}\n'
                # sock.RDT.rdt_3_0_send(response.encode())
                rdt_3_0_send(sock=sock, data=response.encode(), address=address)

        # Check for user trying to upload/attach a file.  We strip the message to keep the user and any other text to help forward the file.  Will
        # send it to interested users like regular messages.

        elif ((len(words) >= 3) and (words[1] == '!attach')):
            sock.setblocking(True)
            filename = words[2]
            words.remove('!attach')
            words.remove(filename)
            filename = filename.rstrip("\n")
            response = f'ATTACH {filename} CHAT/1.0\n'
            # sock.RDT.rdt_3_0_send(response.encode())
            rdt_3_0_send(sock=sock, data=response.encode(), address=address)
            header = get_line_from_socket(sock)[0]
            header_words = header.split(' ')
            if (len(header_words) != 2) or (header_words[0] != 'Content-Length:'):
                response = f'Error:  Invalid attachment header\n'
            elif header_words[1] == '-1':
                response = f'Error:  Attached file {filename} could not be sent\n'
            else:
                interested_clients = []
                attach_size = header_words[1]
                attach_notice = f'ATTACHMENT {filename} CHAT/1.0\nOrigin: {user}\nContent-Length: {attach_size}\n'
                for reg in client_list:
                    if reg[0] == user:
                        continue
                    forwarded = False
                    for term in reg[2]:
                        for word in words:
                            if ((term == word.rstrip(punctuation)) and not forwarded):
                                interested_clients.append(reg[1])
                                # reg[1].RDT.rdt_3_0_send(attach_notice.encode())
                                rdt_3_0_send(reg[1], attach_notice.encode())
                                forwarded = True

                #  Made file get written to the server instead of other clients, since we do not have other clienrs anymore.
                bytes_read = 0
                bytes_to_read = int(attach_size)
                with open(filename, 'wb') as file_to_write:
                    while (bytes_read < bytes_to_read):
                        # chunk = sock.RDT.rdt_1_0_receive(BUFFER_SIZE)

                        chunk = rdt_3_0_recv(sock, BUFFER_SIZE)[2]

                        # code word to wait until something useful appears in the socket basicallt
                        if chunk == "waiting29420989329409329":
                            print(chunk)
                            continue
                        bytes_read += len(chunk)
                        file_to_write.write(chunk)

                response = f'Attachment {filename} attached and distributed\n'
            # sock.RDT.rdt_3_0_send(response.encode())
            rdt_3_0_send(data=response.encode(), sock=sock, address=address)
            sock.setblocking(False)

        # Look for follow terms and dispatch message to interested users.  Send at most only once, and don't send to yourself.  Trailing punctuation is stripped.
        # Need to re-add stripped newlines here.

        else:
            for reg in client_list:
                if reg[0] == user:
                    continue
                forwarded = False
                for term in reg[2]:
                    for word in words:
                        if ((term == word.rstrip(punctuation)) and not forwarded):
                            client_addr = reg[1]
                            forwarded_message = f'{message}\n'
                            # client_sock.RDT.rdt_3_0_send(forwarded_message.encode())
                            rdt_3_0_send(data=forwarded_message.encode(), sock=sock, address=client_addr)
                            forwarded = True


# Function to accept and set up clients.

def accept_client(sock, message, addr):
    global flag # dangrous, for checking if user is already registered


    print('Accepted connection from client address:', addr)
    message_parts = message.split()

    # Check format of request.
    if ((len(message_parts) != 3) or (message_parts[0] != 'REGISTER') or (message_parts[2] != 'CHAT/1.0')):
        print('Error:  Invalid registration message.')
        print('Received: ' + message)
        print('Connection closing ...')
        response = '400 Invalid registration\n'
        # conn.RDT.rdt_3_0_send(response.encode())
        rdt_3_0_send(sock=sock, data=response.encode(),
                     address=addr)  # TODO need to make send function compatible with .sendto(blah (host port))

    # If request is properly formatted and user not already listed, go ahead with registration.

    else:
        user = message_parts[1]
        if user == 'all':
            print('Error:  Client cannot use reserved user name \'all\'.')
            print('Connection closing ...')

            response = '402 Forbidden user name\n'


            rdt_3_0_send(data=response.encode(), sock=sock, address=addr)


        elif (client_search(user) == None):

            # Check for following terms or an issue with the request.

            follow_terms = []
            follow_message = get_line_from_socket(sock)[0]  # ********** fixed

            # if we're stil waiting on a correct packet, try to get the packet again.
            if follow_message == 'waiting29420989329409329':
                follow_message = get_line_from_socket(sock)[0]

            if follow_message != "":
                if follow_message.startswith('Follow: '):
                    follow_terms = follow_message[len('Follow: '):].split(',')
                    blank_line = get_line_from_socket(addr)
                    if blank_line != "":
                        print('Error:  Invalid registration message.  Issue in follow list.')
                        print('Received: ' + message)
                        print('Connection closing ...')
                        response = '400 Invalid registration\n'
                        # conn.RDT.rdt_3_0_send(response.encode())
                        rdt_3_0_send(sock=sock, address=addr, data=response.encode())
                        # conn.close()
                        return
                else:
                    print('Error:  Invalid registration message.  Issue in follow list.')
                    print('Received: ' + message)
                    print('Connection closing ...')
                    response = '400 Invalid registration\n'
                    rdt_3_0_send(sock=sock, address=addr, data=response.encode())
                    # conn.RDT.rdt_3_0_send(response.encode())
                    # conn.close()
                    return

            # Add the user to their follow list, so @user finds them.  We'll also do @all as well for broadcast messages.

            follow_terms.append(f'@{user}')
            follow_terms.append('@all')

            # Finally add the user.

            client_add(user, addr, follow_terms)  # *************

            print(f'Connection to client established, waiting to receive messages from user \'{user}\'...')
            response = '200 Registration succesful\n'

            # conn.RDT.rdt_3_0_send(response.encode())
            rdt_3_0_send(data= response.encode(), sock=sock, address=addr)
            # conn.setblocking(False)



        # If user already in list, return a registration error.

        else:
            print('Error:  Client already registered.')
            print('Connection closing ...')
            response = '401 Client already registered\n'
            # conn.RDT.rdt_3_0_send(response.encode())
            rdt_3_0_send(sock=sock, address=addr, data=response.encode())

        # conn.close()


# Our main function.

def main():
    # Register our signal handler for shutting down.

    # signal.signal(signal.SIGINT, signal_handler)

    # Create the socket.  We will ask this to work on any interface and to pick
    # a free port at random.  We'll print this out for clients to use.

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('', 0))
    print('Will wait for client connections at port ' + str(server_socket.getsockname()[1]))
    print('Waiting for incoming client connections ...')
    # server_socket.listen(100)

    sel.register(server_socket, selectors.EVENT_READ, read_message)
    server_socket.setblocking(False)


    # Keep the server running forever, waiting for connections or messages.

    while (True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)


if __name__ == '__main__':
    main()
