import os
import uuid
import hashlib
import sqlite3
import argparse

import socketserver

import logging

logging.basicConfig(filename='./server.log', level=logging.DEBUG, 
                    format='%(threadName)s  %(asctime)s : %(levelname)s : %(message)s')

from database.db import Database

DB_PATH = os.path.abspath("./database/telemetry.db")

HOST        = "localhost"
PORT        = 10227

ACCEPTED    = 200
KEEP_ALIVE  = 100

def salt_and_hash(password):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt
    
def check_password(hashed_password, user_password):
    password, salt = hashed_password.split(':')
    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()



class ThreadedTCPRequestHandler(socketserver.StreamRequestHandler):

    def handle(self):
        self.username = None
        self.auth = False
        self.counter = 0
        self.db = Database(self.server.db_path)
        self.blob = bytes()

        greeting = self.rfile.readline().strip()
        greeting = greeting.decode("ascii")

        if self._auth(greeting):
            self.wfile.write((str(ACCEPTED)+"\n").encode("ascii"))
            while True:
                data = self.rfile.readline()
                if data:
                    self._process_data(data)
                else:
                    break

            self.server.users_online.remove(self.username)

    def _auth(self, data):
        if not self.server.quiet: print(f"Auth user: {data}")
        if len(data.split(":")) != 2:
            logging.error(f"Invalid auth data format from {self.client_address[0]}")
            return False

        self.username, user_password = data.split(":")
        if self.username in self.server.users_online:
            logging.error(f"{self.username}: allready logged in")
            self.wfile.write(f"Such user allready logged in\n".encode("ascii"))
            return False

        user_row = self.db.get_user(self.username)
        if user_row:
            check = check_password(user_row.hash, user_password) 
            if check:
                self.auth = True
                self.server.users_online.add(self.username)
                logging.info(f"{self.username} {self.client_address[0]}: authorized")
                return True
            else:
                logging.error(f"{self.username}: invalid username or password")
                return False
        else:
            logging.error(f"{self.username}: invalid username or password")
            return False

    def _process_data(self, data):
        if data.decode("ascii").strip() == str(KEEP_ALIVE):
            self.wfile.write((str(KEEP_ALIVE)+"\n").encode("ascii"))
        else:
            self.counter += 1
            self.blob += data

    def finish(self):
        if self.auth:
            if self.counter:
                self.db.add_session(self.username, self.blob)
            logging.info(f"{self.username}: session  finished, {self.counter} events dumped to DB")
        elif self.username:
            logging.info(f"{self.username} auth failed")
        else:
            logging.info(f"Bad connection from {self.client_address[0]}")



class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def __init__(self, *args, db_path=None, quiet=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.users_online = set()
        self.db_path = db_path
        self.quiet = quiet


def report(conn):
    sql = "select user as username, count(blob) as sessions from sessions group by user order by sessions desc;"
    with conn:
        print("User\tNum of sessions")
        
        cur = conn.execute(sql)
        for i, (user, num) in enumerate(cur.fetchall()):
            print(f"{user}\t{num}")
            if i == 9: break

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Telemetry server. If DB file not found it will be created with test user "user:password"')
    parser.add_argument('-a', '--addr', type=str, default=HOST, help=f"Server host (dafault {HOST})")
    parser.add_argument('-p', '--port', type=int, default=PORT, help=f"Server port (dafault {PORT})")
    parser.add_argument('-d', '--db', type=str, help=f'Path to sqlite3 database (default: ./database/telemetry.db)')
    parser.add_argument('-r', '--report', action='store_true', help=f"Print number of sessions by users in DB")
    args = parser.parse_args()
    
    HOST = args.addr
    PORT = args.port
    DB_PATH = DB_PATH if args.db is None else args.db

    if args.report:
        conn = sqlite3.connect(DB_PATH)
        report(conn)

    af_inet_addr    = (HOST, PORT)
    quiet           = False
    
    server = ThreadedTCPServer(af_inet_addr, ThreadedTCPRequestHandler, quiet = quiet, db_path=DB_PATH)

    print(f"Database at '{DB_PATH}'")
    print(f"Telemetry server up on '{HOST}:{PORT}', use <Ctrl-C> to stop")
    server.serve_forever()