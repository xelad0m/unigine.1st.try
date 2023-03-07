"""Реализация, аналогичная server.py за исключением того, что для сохранения данных в БД 
создается очередь, в которую обработчики соединений помещают данные, а отдельный поток 
разбирает эту очередь"""

import os, sys
import uuid
import hashlib
import argparse

import socketserver

import threading
import queue

import logging
logging.basicConfig(filename='./serverq.log', level=logging.DEBUG, 
                    format='%(threadName)s  %(asctime)s : %(levelname)s : %(message)s')

from db import Database

DB_PATH = os.path.abspath("telemetryq.db")

HOST        = "localhost"
PORT        = 10227

ACCEPTED    = 200
KEEP_ALIVE  = 100
FINISHED    = 500


def salt_and_hash(password):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt
    
def check_password(hashed_password, user_password):
    password, salt = hashed_password.split(':')
    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()


class ThreadedTCPRequestHandler(socketserver.StreamRequestHandler):
    """Класс обработчика запросов к серверу, работает в отдельном потоке"""

    def handle(self):
        """Основной обработчик, принимает приветствие от клиента, если авторизация 
        успешная, начинает прием данных"""
        
        self.username = None
        self.auth = False
        self.counter = 0
        self.db_reader = Database(self.server.db_path)
        self.blob = bytes()
        self.finished = False

        greeting = self.rfile.readline().strip()
        greeting = greeting.decode("ascii")

        if self._auth(greeting):
            self.wfile.write((str(ACCEPTED)+"\n").encode("ascii"))
            while not self.finished:

                try:
                    data = self.rfile.readline()
                except ConnectionResetError:
                    print(f"[Handler] {self.username}: ConnectionResetError")

                if data:
                    self._process_data(data)
                else:
                    break

            self.server.users_online.remove(self.username)

    def _auth(self, data):
        """Процедура авторизации"""

        if len(data.split(":")) != 2:
            logging.error(f"[Handler] Invalid auth data format from {self.client_address[0]}")
            return False

        self.username, user_password = data.split(":")
        if self.username in self.server.users_online:
            logging.error(f"{self.username}: allready logged in")
            self.wfile.write(f"[Handler] Such user allready logged in\n".encode("ascii"))
            return False

        user_row = self.db_reader.get_user(self.username)
        if user_row:
            if check_password(user_row.hash, user_password) :
                if not self.server.quiet: print(f"[Handler] Login: {self.username}")
                self.auth = True
                self.server.users_online.add(self.username)
                logging.info(f"[Handler] {self.username} {self.client_address[0]}: authorized")
                return True
            else:
                logging.error(f"[Handler] {self.username}: invalid username or password")
                return False
        else:
            logging.error(f"[Handler] {self.username}: invalid username or password")
            return False

    def _process_data(self, data):
        """Обрабатывает входящие данные и сообщение FINISHED, отвечает на KEEP_ALIVE,
        отбрасывает данные, несоответсвующе формату телеметрии (timestamp;code;value)"""

        if data.decode("ascii").strip() == str(KEEP_ALIVE):

            try:
                self.wfile.write((str(KEEP_ALIVE)+"\n").encode("ascii"))
            except BrokenPipeError:        # SIGPIPE, клиент уже закрыл сокет
                print(f"[Handler] {self.username}: BrokenPipeError")
        elif data.decode("ascii").strip() == str(FINISHED):
            self.finished = True
        else:
            self.counter += 1
            if len(data.decode("ascii").split(";")) == 3:
                self.blob += data

    def finish(self):
        """ Запускается после завершения работы обработчика, если получены данные, 
        помещает их в очередь для сохранения их в БД"""
        
        if self.auth:
            if not self.server.quiet: print(f"[Handler] Logout: {self.username}")
            if self.counter:
                task = (self.username, self.counter, self.blob)
                self.server.db_write_queue.put_nowait(task)
            logging.info(f"[Handler] {self.username}: session  finished")
        elif self.username:
            logging.info(f"[Handler] {self.username}: auth failed")
        else:
            logging.info(f"[Handler] Bad connection from {self.client_address[0]}")



class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def __init__(self, *args, db_path=None, quiet=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.quiet = quiet
        self.db_path = db_path
        self.db_write_queue = queue.Queue(maxsize=0)

        self.users_online = set()

        threading.Thread(target=self.db_writer).start()
        
    def db_writer(self):
        while True:
            
            db = Database(self.db_path)
            try:
                username, counter, blob = self.db_write_queue.get_nowait()
            except queue.Empty:
                continue

            db.add_session(username, blob)
            if not self.quiet: print(f'[Server] Saved {username} session. {counter} events blob added to DB')
            self.db_write_queue.task_done()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Telemetry server. If DB file not found it will be created with test user "user:password"')
    parser.add_argument('-a', '--addr', type=str, default=HOST, help=f"Server host (dafault: {HOST})")
    parser.add_argument('-p', '--port', type=int, default=PORT, help=f"Server port (dafault: {PORT})")
    parser.add_argument('-d', '--db', type=str, help=f'Path to sqlite3 database (default: ./telemetry.db)')
    parser.add_argument('-r', '--report', action='store_true', help=f"Print number of sessions by users in DB")
    args = parser.parse_args()
    
    HOST = args.addr
    PORT = args.port
    DB_PATH = DB_PATH if args.db is None else args.db

    if args.report:
        Database(DB_PATH).report()

    af_inet_addr    = (HOST, PORT)
    quiet           = False
    
    try:
        server = ThreadedTCPServer(af_inet_addr, ThreadedTCPRequestHandler, quiet = args.quiet, db_path=DB_PATH)
    except OSError:
        print("Address already in use")
        sys.exit(1)

    print(f"Database at '{DB_PATH}'")
    print(f"Telemetry server up on '{HOST}:{PORT}', use <Ctrl-C> to stop")

    server.serve_forever()

