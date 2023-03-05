import os
import uuid
import hashlib
import sqlite3
import datetime

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
    def __init__(self, path):
        self.path = path
        if os.path.isfile(self.path):
            self.connection = sqlite3.connect(self.path)
        else:
            self.connection = sqlite3.connect(self.path)
            self.init_db()
            self.add_user("user", "password")
        self.connection.row_factory = namedtuple_factory
    
    def get_cursor(self):
        return self.connection.cursor()

    def init_db(self):
        sqlite_init_db = """
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
            conn.executescript(sqlite_init_db)

    def add_user(self, user, password):
        if self.get_user(user) is None:
            sqlite_add_user = """
                INSERT INTO users (id, name, hash) VALUES ( ? , ? , ? );
            """
            with self.connection as conn:
                conn.execute(sqlite_add_user, (None, user, salt_and_hash(password)))

    def get_user(self, username):
        sqlite_get_user = """
            SELECT * FROM users WHERE name = ?;
        """
        with self.connection as conn:
            cur = conn.execute(sqlite_get_user, (username, ))
        row = cur.fetchone()
        cur.close()
        return row

    def add_session(self, username, blob):
        sqlite_insert_blob_query = """
            INSERT INTO sessions (id, user, timestamp, blob) VALUES (?, ?, ?, ?)
        """
        timestamp = datetime.datetime.now()
        with self.connection as conn:
            conn.execute(sqlite_insert_blob_query, (None, username, timestamp, sqlite3.Binary(blob)))
        
    def get_session(self):
        pass

    def report(self):
        pass

if __name__ == "__main__":
    db = Database(DB_PATH)

    db.add_user("test", "dummy")
    db.add_user("user", "password")

    print(db.get_user("test"))
    print(db.get_user("test1"))

    