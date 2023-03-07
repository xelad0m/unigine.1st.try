import os
import sys
import uuid
import hashlib
import sqlite3
import datetime
import argparse

from collections import namedtuple


DB_PATH = "./telemetry.db"


def namedtuple_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    cls = namedtuple("Row", fields)
    return cls._make(row)

def salt_and_hash(password):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt


class Database:
    """Класс для хранения соединения с БД и необходимых методов по чтению и 
    добавлению данных, а также сохранению данных сессий в отдельные файлы"""

    def __init__(self, path):
        self.path = path
        if os.path.isfile(self.path):
            self.connection = sqlite3.connect(self.path)
        else:
            self.connection = sqlite3.connect(self.path)
            self.init_db()
            self.add_user("user", "password")
            self.add_user("test", "dummy")
        self.connection.row_factory = namedtuple_factory
    
    def get_cursor(self):
        return self.connection.cursor()

    def init_db(self):
        sql_init_db = """
            DROP TABLE IF EXISTS users;
            CREATE TABLE users (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                hash TEXT
            );
            DROP TABLE IF EXISTS sessions;
            CREATE TABLE sessions (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                timestamp TIMESTAMP,
                blob BLOB,
                FOREIGN KEY (user)
                    REFERENCES users (user) 
                        ON UPDATE RESTRICT
                        ON DELETE RESTRICT
            );
        """
        with self.connection as conn:
            conn.executescript(sql_init_db)

    def add_user(self, user, password):
        if self.get_user(user) is None:
            sql_add_user = """
                INSERT INTO users (id, name, hash) VALUES ( ? , ? , ? );
            """
            with self.connection as conn:
                conn.execute(sql_add_user, (None, user, salt_and_hash(password)))

    def get_user(self, username):
        sql_get_user = """
            SELECT * FROM users WHERE name = ?;
        """
        with self.connection as conn:
            cur = conn.execute(sql_get_user, (username, ))
        row = cur.fetchone()
        cur.close()
        return row


    def add_session(self, username, blob):
        sql_insert_blob_query = """
            INSERT INTO sessions (id, user, timestamp, blob) VALUES (?, ?, ?, ?);
        """
        timestamp = datetime.datetime.now()
        with self.connection as conn:
            conn.execute(sql_insert_blob_query, (None, username, timestamp, sqlite3.Binary(blob)))
        

    def save_session(self, session_id):
        sql_fetch_blob_query = """
            SELECT * FROM sessions WHERE id = ? ;
        """
        with self.connection as conn:
            cur = conn.execute(sql_fetch_blob_query, (session_id,))
        row = cur.fetchone()
        cur.close()

        filename = f"./session{session_id}.txt"
        with open(filename, 'wb') as file:
            file.write(row.blob)

    def get_user_sessions(self, username):
        sql_select_user_sessions = """
            SELECT user AS user, id AS id FROM sessions WHERE user = ? ;
        """
        with self.connection as conn:         
            rows = conn.execute(sql_select_user_sessions, (username, )).fetchall()
        
        print(f"{username} sessions:", *[r.id for r in rows])

    def report(self):
        sql = """
            SELECT user AS username, COUNT(blob) as sessions FROM sessions GROUP BY user ORDER BY sessions DESC;
        """
        with self.connection as conn:
            print("User\tNum of sessions")
            
            cur = conn.execute(sql)
            for i, (user, num) in enumerate(cur.fetchall()):
                print(f"{user}\t{num}")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Telemetry DB helper.')
    parser.add_argument('-d', "--db", type=str, default=DB_PATH, help=f"Use/create database by path")
    parser.add_argument('-u', "--userpass", type=str, help=f"Add user ('user:password' template)")
    parser.add_argument('-s', "--session", type=int, help=f"Save session blob by ID")
    parser.add_argument('-l', "--list", type=str, help=f"Get list of sessions of 'username'")
    parser.add_argument('-r', "--report", action='store_true', help=f"Get list of users'")
    args = parser.parse_args()


    DB_PATH = DB_PATH if args.db is None else args.db


    db = Database(DB_PATH)


    userpass = args.userpass
    session_id = args.session
    list_user = args.list

    print(f"Using {DB_PATH} database")
    if userpass is not None:
        if len(userpass.split(":")) != 2:
            print("Use 'user:password' template to add user")
            sys.exit(0)
        else:
            db.add_user(*userpass.split(":"))
            print("User added")


    if session_id is not None:
        db.save_session(session_id)
        print('Session saved to current dir')


    if list_user is not None:
        db.get_user_sessions(list_user)

    if args.report:
        db.report()



    