import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"os/overlay/usr/local/lib/culinaryos"))
import hashlib
import http.client
import http.server
import json
import os
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import pki
from securedata import Keyring,canonical
from store import Store
from syncworker import HTTPSCentral,deliver

class SyncTLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.binary=os.environ.get("CULINARYOS_OPENSSL","openssl")
        cls.password=cls.root/"passphrase";cls.password.write_text(os.urandom(24).hex())
        cls.ca=cls.root/"ca";cls.server=cls.root/"server";cls.client=cls.root/"client"
        def run(args):
            command=[cls.binary,*map(str,args)]
            if args[0]=="genpkey":command+=["-pass","file:"+str(cls.password)]
            elif args[0]=="req" and "-x509" in args:command+=["-passin","file:"+str(cls.password)]
            elif args[0]=="ca":command+=["-passin","file:"+str(cls.password)]
            subprocess.run(command,capture_output=True,check=True,timeout=20)
        with patch("pki.execute",side_effect=run):
            pki.init_ca(cls.ca)
            pki.request(cls.server,"localhost","127.0.0.1")
            pki.issue(cls.ca,cls.server/"server.csr",cls.server/"server.crt","localhost","127.0.0.1")
            pki.request(cls.client,"local-01.internal","127.0.0.1")
            pki.issue(cls.ca,cls.client/"server.csr",cls.client/"client.crt","local-01.internal","127.0.0.1",purpose="client")
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                raw=self.rfile.read(min(int(self.headers.get("Content-Length","0")),128*1024))
                body=json.loads(raw)
                cls.requests.append(body["event_id"])
                if cls.mode=="redirect":
                    self.send_response(302);self.send_header("Location","https://not-contacted.invalid/");self.end_headers();return
                digest=hashlib.sha256(raw).hexdigest()
                ack={"site_id":body["site_id"],"event_id":body["event_id"],
                     "sha256":digest if cls.mode!="bad-ack" else "0"*64,"status":"committed"}
                encoded=canonical(ack)
                self.send_response(200);self.send_header("Content-Length",str(len(encoded)));self.end_headers();self.wfile.write(encoded)
        cls.requests=[];cls.mode="ok"
        cls.http=http.server.HTTPServer(("127.0.0.1",0),Handler)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.server/"server.crt",cls.server/"server.key")
        context.load_verify_locations(cls.ca/"ca.crt");context.verify_mode=ssl.CERT_REQUIRED
        cls.http.socket=context.wrap_socket(cls.http.socket,server_side=True)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.config={"url":"https://127.0.0.1:"+str(cls.http.server_port)+"/v1/events",
                    "ca_file":str(cls.ca/"ca.crt"),"client_certificate":str(cls.client/"client.crt"),"client_key":str(cls.client/"server.key")}
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join(timeout=3);cls.tmp.cleanup()
    def setUp(self):
        type(self).mode="ok"
    def test_actual_mutual_tls_and_ack(self):
        event={"site_id":"local-01","event_id":"tls-event"}
        ack=HTTPSCentral(self.config).send(event,hashlib.sha256(canonical(event)).hexdigest())
        self.assertEqual(ack["event_id"],"tls-event")
        self.assertEqual(ack["sha256"],hashlib.sha256(canonical(event)).hexdigest())
    def test_no_client_certificate_rejected(self):
        context=ssl.create_default_context(cafile=str(self.ca/"ca.crt"))
        connection=http.client.HTTPSConnection("127.0.0.1",self.http.server_port,timeout=3,context=context)
        try:
            with self.assertRaises((OSError,http.client.HTTPException)):
                connection.request("POST","/",body=b"{}");connection.getresponse()
        finally:connection.close()
    def test_redirect_is_not_followed(self):
        type(self).mode="redirect"
        with self.assertRaises(ValueError):HTTPSCentral(self.config).send({"site_id":"local-01","event_id":"redirect"},"0"*64)
    def test_real_tls_bad_ack_retains_event(self):
        type(self).mode="bad-ack"
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/"store.sqlite","local-01",Keyring(Keyring.generate()),0)
            store.put("record1",1,{"value":"synthetic"},"bad-ack-event",0)
            result=deliver(store,HTTPSCentral(self.config))
            self.assertEqual(result["state"],"pending");self.assertEqual(store.status()["pending"],1)
    def test_plain_http_and_url_credentials_rejected(self):
        for url in ("http://127.0.0.1/","https://user:secret@host/"):
            with self.assertRaises(ValueError):HTTPSCentral({**self.config,"url":url})
if __name__=="__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
