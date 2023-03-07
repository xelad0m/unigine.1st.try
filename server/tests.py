import os
import time
import unittest
import subprocess

from threading import Thread

from db import Database
from clients import session, starter

SERVER = "server.py"
TEST_DB = "./tests/test.db"

class TestDB(unittest.TestCase):
    
    db = None
    user = "user"
    session = "1678134985526;8;1\n1678134985539;1;0\n1678134985560;2;1\n".encode('ascii')

    @classmethod
    def setUpClass(self):
        if not os.path.isdir("./tests"):
            os.mkdir("./tests")
        TestDB.db = Database(TEST_DB)
 
    @classmethod
    def tearDownClass(cls):
        if os.path.isfile(TEST_DB):
            os.remove(TEST_DB)
        if os.path.isfile("./session1.txt"):
            os.remove("./session1.txt")

    def test_init_db(self):
        self.assertTrue(os.path.isfile(TEST_DB), "Should be created db file")
        
    def test_get_user(self):
        user_row = TestDB.db.get_user("user") 
        self.assertTrue(user_row is not None, "Should get user row from db")
        self.assertTrue(hasattr(user_row, 'hash'), "Should have 'hash' attr")
        user_row = TestDB.db.get_user("noname") 
        self.assertFalse(user_row is not None, "Should not get non-exist user row from db")

    def test_save_session(self):
        TestDB.db.add_session(TestDB.user, TestDB.session)
        TestDB.db.save_session(1)
        self.assertTrue(os.path.isfile("./session1.txt"))
        with open("./session1.txt", "rb") as f:
            session = f.read()
        self.assertTrue(TestDB.session == session, "Stored data should be equal to dumped data")


class TestServer(unittest.TestCase):
    
    server = None
    clients = None
    N_clients = 5
    HOST = "localhost"
    PORT = 10229

    @classmethod
    def setUpClass(self):
        if os.path.isfile(TEST_DB):
            os.remove(TEST_DB)

        for i in range(1, TestServer.N_clients + 1):
            if os.path.isfile(f"./session{i}.txt"):
                os.remove(f"./session{i}.txt")

        cmd = f"python3 {SERVER} -d {os.path.abspath(TEST_DB)} -a {TestServer.HOST} -p {TestServer.PORT}"
        TestServer.server = subprocess.run(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


    @classmethod
    def tearDownClass(cls):       
        if os.path.isfile(TEST_DB):
            os.remove(TEST_DB)

        for i in range(1, TestServer.N_clients + 1):
            if os.path.isfile(f"./session{i}.txt"):
                os.remove(f"./session{i}.txt")
        
    def test_server(self):
        N = TestServer.N_clients    # clients
        E = 100                     # events per client

        db = Database(TEST_DB)
        
        thread_pool = []

        # add new users and run its clients
        for i in range(N):
            user, password = f"user{i}", "password"
            db.add_user(user, password)
            thread_pool.append(Thread(target=session, 
                                      args=(user, password, TestServer.HOST, TestServer.PORT, E, True))) 
        starter.clear()

        for t in thread_pool:
            t.start()
        
        starter.set()

        for t in thread_pool:   # ждем завершения обработки всех запущенных клиентов
            t.join()   

        sizes = []
        lines = []
        for i in range(1, N+1): # 1-based sql index
            db.save_session(i)
            if (os.path.isfile(f"./session{i}.txt")):
                sizes.append(os.path.getsize(f"./session{i}.txt"))
                with open(f"./session{i}.txt") as f:
                    lines.append(len(f.read().split("\n")))
        
                
        self.assertTrue(len(sizes) == TestServer.N_clients, "In DB should be dumps from all clients")
        self.assertTrue(all(sizes), "All dumps should not be emplty")
        self.assertTrue(all([s == E + 1 for s in lines]), "Number of send and saved events must mutch")



if __name__ == '__main__':
    unittest.main()