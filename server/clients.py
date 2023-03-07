import time
import random
import socket
import argparse

from threading import Thread, Event

from db import Database

HOST, PORT = "localhost", 10227

DB_PATH = "./telemetry.db"

ACCEPTED    = 200
KEEP_ALIVE  = 100
FINISHED    = 500


def datastream(num):
    """Имитация потока данных от клиента:
    num - количество событий, которые генерируеются в рамках сессии"""
    for _ in range(num):
        ts = int(time.time() * 1000)
        yield f"{ts};{random.randint(0,11)};{random.randint(0,100) if random.random() < 0.5 else random.random()}\n" # nosec


class Client:
    """Класс, представляющий клиента:
    user, password, ip, port    - понятно
    datastream - поток событий, который генерирует клиент
    timeout, missed - таймаут и количество пропущенных KEEP_ALIVE пакетов для закрытия соединения
    """
    def __init__(self, user, password, datastream, ip, port, timeout=1, missed=-3, quiet=True):
        self.sock       = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip         = ip
        self.port       = port
        self.user       = user
        self.password   = password
        self.timeout    = timeout
        self.missed     = missed
        self.timestamp  = 0
        self.quiet      = quiet
        self.datastream = datastream

        self.finished = False

    def recv_keep_alive(self):
        """Поток, обрабатывающий прием KEEP_ALIVE пакетов"""
        while not self.finished or self.missed < 0:

            try:
                response = self.sock.recv(1024)
            except OSError: # Bad file descriptor - parent thread closed socket allready
                break

            if str(response, 'ascii').strip() == str(KEEP_ALIVE):
                if not self.quiet: print(f"KA <-")
                self.missed -=1
                self.timestamp = time.time()
        self.sock.close()
    
    def send_keep_alive(self):
        """Поток, обрабатывающий отправку KEEP_ALIVE пакетов"""
        while not self.finished or self.missed < 0:
            if time.time() - self.timestamp > self.timeout:
                self.missed += 1
                self.timestamp = time.time()

                try:
                    self.sock.sendall(bytes((str(KEEP_ALIVE) + '\n'), 'ascii'))
                except OSError: # Bad file descriptor - parent thread closed socket allready
                    break

                if not self.quiet: print(f"KA ->")
        self.sock.close()

    def send_data(self):
        """Отправка данных авторизации и стриминг основных данных"""
        with self.sock as sock:
            try:
                sock.connect((self.ip, self.port))
            except ConnectionRefusedError:
                print(f"[{self.user}] Connection refused")
                return

            sock.sendall(bytes(f"{self.user}:{self.password}\n", 'ascii'))
            
            response = str(sock.recv(1024), 'ascii').strip()
            if not self.quiet: print("Recieved: ", response)

            if response == str(ACCEPTED):
                if not self.quiet: print("ACCEPTED")
                if not self.quiet: print(f"[{self.user}] Authorized")

                self.t1.start()                                             # если авторизованы, начинаем 
                self.t2.start()                                             # принимать / отправлять KEEP_ALIVE 

                for data in self.datastream:
                    try:
                        sock.sendall(bytes(data, 'ascii'))
                    except OSError: # ????????
                        print(f"[{self.user}] OSError ???")
                        self.finished = True
                        break

                    if not self.quiet: print("Sent: ", bytes(data, 'ascii'))

                    if self.missed == 0:                                    # если сервер не ответил на N KEEP_ALIVE запросов
                        if not self.quiet: print("Connection lost")
                        sock.close()
                        self.finished = True
                        break

                if not self.finished:
                    try:
                        self.sock.sendall(bytes((str(FINISHED) + '\n'), 'ascii'))
                    except OSError: # Bad file descriptor - closed socket allready
                        pass

            else:
                sock.close()
        
        self.finished = True
    
    def connect(self):
        self.t1 = Thread(target=self.recv_keep_alive, daemon=True)
        self.t2 = Thread(target=self.send_keep_alive, daemon=True)

        self.send_data()
        if not self.quiet: print(f"[{self.user}] Finished")


starter = Event()

def session(user, password, host, port, Nevents, quiet):
    """Запуск сессии клиента, стартует после срабатывания события starter"""
    starter.wait()
    start = time.time()
    Client(user, password, datastream(Nevents), host, port, quiet=quiet).connect()
    if not quiet: print(f"[{user}] duration: {(time.time() - start) :.02f} sec")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Testing clients.')
    parser.add_argument('-a', '--addr', type=str, default=HOST, help=f"Server host (dafault: {HOST})")
    parser.add_argument('-p', '--port', type=int, default=PORT, help=f"Server port (dafault: {PORT})")
    parser.add_argument('-n', type=int, default=5, help=f"Number of client threads to launch (dafault: 5)")
    parser.add_argument('-e', type=int, default=2000, help=f"Average number of events to send (dafault: 2000+randint(-1000,1000))")
    parser.add_argument('-q', '--quiet', action='store_true', help=f"Quiet mode")
    args = parser.parse_args()

    HOST = args.addr if args.addr is not None else HOST
    db = Database(DB_PATH)

    N_clients = args.n
    Nevents = args.e

    thread_pool = []

    for i in range(N_clients):
        user, password = f"user{i}", "password"
        db.add_user(user, password)
        thread_pool.append(Thread(target=session, 
                                  args=(user, password, HOST, PORT, Nevents + random.randint(-Nevents//2, Nevents//2), args.quiet))) #nosec

    starter.clear()

    for t in thread_pool:
        t.start()
    
    starter.set()

    for t in thread_pool:   # ждем завершения обработки всех запущенных клиентов
        t.join()        