#!/usr/bin/env python3

import os
import psutil
import signal
import socketserver
from struct import unpack
from threading import Thread
from time import sleep


class ProcessServer(socketserver.UnixDatagramServer):

    def server_activate(self):
        self.pids = list()

    def initiate_shutdown(self, _signo, _stack_frame):
        self.__relay_signal(signal.SIGTERM)
        Thread(target=self.__wait_and_sigkill).start()

    def __wait_and_sigkill(self):
        for i in range(500):
            sleep(0.1)
            if len(self.pids) == 0:
                self.shutdown()
                return
        self.__relay_signal(signal.SIGKILL)

    def __relay_signal(self, ipc_signal):
        print('Relay ' + ' '.join(str(ipc_signal).split('s.')) + ' to ' + str(self.pids) + '.')
        for pid in self.pids:
            try:
                parent = psutil.Process(pid)
            except psutil.NoSuchProcess:
                return
            children = parent.children()
            for child in children:
                child.send_signal(ipc_signal)


class ProcessHandler(socketserver.BaseRequestHandler):

    def handle(self):
        datagram = self.request[0]
        op, pid = unpack('ch', datagram)

        if op == b'a':
            if pid not in self.server.pids:
                self.server.pids.append(pid)
            print('Add process: ' + str(pid) + '. New process list:' + str(self.server.pids))
        elif op == b'd':
            if pid in self.server.pids:
                self.server.pids.remove(pid)
            print('Delete process: ' + str(pid) + '. New process list: ' + str(self.server.pids))

            if len(self.server.pids) == 0:
                Thread(target=self.server.shutdown).start()


def main():
    print('Wait for processes...')
    if os.path.exists('socket'):
        os.remove('socket')

    with ProcessServer('socket', ProcessHandler) as server:
        signal.signal(signal.SIGTERM, server.initiate_shutdown)
        server.serve_forever()

    os.remove('socket')
    print('All processes closed!')


if __name__ == '__main__':
    main()
