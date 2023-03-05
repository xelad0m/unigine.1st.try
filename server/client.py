import time
import random
import socket

from threading import Thread

HOST, PORT = "localhost", 10227

ACCEPTED    = 200
KEEP_ALIVE  = 100;


def data_stream(num, per_second):
    count = 0
    while count < num:
        count += 1
        time.sleep(1 / per_second * random.random())
        ts = int(time.time() * 1000)
        yield f"{ts};{random.randint(0,100)};{random.randint(0,100)}\n"


class Client:
    def __init__(self, ip, port, user, password, num=30, per_second=1, timeout=1, missed=-3, quite=True):
        self.sock       = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip         = ip
        self.port       = port
        self.user       = user
        self.password   = password
        self.timeout    = timeout
        self.missed     = missed
        self.timestamp  = 0
        self.quite      = quite
        self.data_stream_params = {"num":num, "per_second":per_second}

        self.finished = False

    def recv_keep_alive(self):
        while not self.finished or self.missed < 0:
            response = self.sock.recv(1024)
            if str(response, 'ascii').strip() == str(KEEP_ALIVE):
                if not self.quite: print(f"KA <-")
                self.missed -=1
                self.timestamp = time.time()
        self.sock.close()
    
    def send_keep_alive(self):
        while not self.finished or self.missed < 0:
            if time.time() - self.timestamp > self.timeout:
                self.missed += 1
                self.timestamp = time.time()
                self.sock.sendall(bytes((str(KEEP_ALIVE) + '\n'), 'ascii'))
                if not self.quite: print(f"KA ->")
        self.sock.close()

    def send_data(self):
        with self.sock as sock:
            try:
                sock.connect((self.ip, self.port))
            except ConnectionRefusedError:
                print("Server is offline")
                return

            sock.sendall(bytes(f"{self.user}:{self.password}\n", 'ascii'))
            
            response = str(sock.recv(1024), 'ascii').strip()
            if not self.quite: print("Recieved: ", response)

            if response == str(ACCEPTED):
                if not self.quite: print("ACCEPTED")

                self.t1.start()
                self.t2.start()

                for data in data_stream(**self.data_stream_params):
                    sock.sendall(bytes(data, 'ascii'))
                    if not self.quite: print("Sent: ", bytes(data, 'ascii'))

                    if self.missed == 0:
                        if not self.quite: print("Connection lost")
                        sock.close()
            else:
                sock.close()
        
        self.finished = True
    
    def connect(self):
        self.t1 = Thread(target=self.recv_keep_alive, daemon =True)
        self.t2 = Thread(target=self.send_keep_alive, daemon =True)

        self.send_data()


if __name__ == "__main__":

    client = Client(HOST, PORT, "user", "password", quite=False)
    client.connect()