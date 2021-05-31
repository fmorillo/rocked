#!/usr/bin/env python3

import os
import signal
import socketserver
from struct import unpack
from threading import Thread


class ProcessServer(socketserver.UnixDatagramServer):

    def server_activate(self):
        self.pids = list()

    def relay_term(self, _signo, _stack_frame):
        for pid in self.pids:
            os.kill(pid, signal.SIGTERM)

    def relay_kill(self, _signo, _stack_frame):
        for pid in self.pids:
            os.kill(pid, signal.SIGKILL)

    # def initiate_shutdown(self, _signo, _stack_frame):
        # Thread(target=self.shutdown).start()


class ProcessHandler(socketserver.BaseRequestHandler):

    def handle(self):
        datagram = self.request[0]
        op, pid = unpack('ch', datagram)

        if op == b'a':
            if pid not in self.server.pids:
                self.server.pids.append(pid)
            print('add', pid, self.server.pids)
        elif op == b'r':
            if pid in self.server.pids:
                self.server.pids.remove(pid)
            print('del', pid, self.server.pids)

            if len(self.server.pids) == 0:
                Thread(target=self.server.shutdown).start()


def main():
    print('Wait for processes...')
    if os.path.isfile('socket'):
        os.remove('socket')

    with ProcessServer('socket', ProcessHandler) as server:
        # signal.signal(signal.SIGTERM, server.initiate_shutdown)
        signal.signal(signal.SIGTERM, server.relay_term)
        # signal.signal(signal.SIGKILL, server.relay_kill)
        server.serve_forever()

    os.remove('socket')
    print('All processes closed!')


if __name__ == '__main__':
    main()
