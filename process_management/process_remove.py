#!/usr/bin/env python3

import os
import socket
from struct import pack


def main():
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    client.sendto(pack('ch', 'r'.encode('utf-8'), os.getppid()), 'socket')
    client.close()


if __name__ == '__main__':
    main()

