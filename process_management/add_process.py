#!/usr/bin/env python3

import os
import socket
from struct import pack
from time import sleep


def main():
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    while not os.path.exists('socket'):
        sleep(0.1)
    client.sendto(pack('ch', 'a'.encode('utf-8'), os.getppid()), 'socket')
    client.close()


if __name__ == '__main__':
    main()
