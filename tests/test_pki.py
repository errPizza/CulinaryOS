import sys
sys.dont_write_bytecode=True
from pathlib import Path
import os
import ssl
import socket
import threading
import time
import subprocess
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"os/overlay/usr/local/lib/culinaryos"))
import pki
import lan

class PKITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.tmp.name)
        cls.password=cls.root/"test-passphrase"
        # Credencial efímera de prueba, no una CA ni contraseña distribuida.
        cls.password.write_text("ephemeral-"+os.urandom(24).hex(),encoding="ascii")
        cls.ca=cls.root/"ca";cls.server=cls.root/"server"
        cls.executable=os.environ.get("CULINARYOS_OPENSSL","openssl")
        subprocess.run([cls.executable,"version"],capture_output=True,check=True)
        def run(args):
            cmd=[cls.executable,*map(str,args)]
            if args[0]=="genpkey":cmd+=["-pass","file:"+str(cls.password)]
            elif args[0]=="req" and "-x509" in args:cmd+=["-passin","file:"+str(cls.password)]
            elif args[0]=="ca":cmd+=["-passin","file:"+str(cls.password)]
            subprocess.run(cmd,capture_output=True,check=True,timeout=20)
        cls.runner=staticmethod(run)
        with patch("pki.execute",side_effect=run):
            pki.init_ca(cls.ca)
            pki.request(cls.server,"culinaryos.internal","10.77.0.10")
            pki.issue(cls.ca,cls.server/"server.csr",cls.server/"server.crt","culinaryos.internal","10.77.0.10")
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def verify(self,*args):
        return subprocess.run([self.executable,"verify",*map(str,args),self.server/"server.crt"],
                              capture_output=True,text=True,timeout=10)
    def test_encrypted_ca_key(self):
        self.assertIn("ENCRYPTED",(self.ca/"ca.key").read_text())
    def test_chain_and_name_valid(self):
        self.assertEqual(self.verify("-CAfile",self.ca/"ca.crt","-verify_hostname","culinaryos.internal").returncode,0)
    def test_ip_san_valid(self):
        self.assertEqual(self.verify("-CAfile",self.ca/"ca.crt","-verify_ip","10.77.0.10").returncode,0)
    def test_wrong_name_rejected(self):
        self.assertNotEqual(self.verify("-CAfile",self.ca/"ca.crt","-verify_hostname","otro.internal").returncode,0)
    def test_untrusted_chain_rejected(self):
        self.assertNotEqual(self.verify("-no-CAfile","-no-CApath","-no-CAstore").returncode,0)
    def test_fingerprint_and_wrong_import(self):
        fingerprint=pki.fingerprint(self.ca/"ca.crt")
        self.assertEqual(len(fingerprint),64)
        with self.assertRaises(ValueError):pki.trust(self.ca/"ca.crt","0"*64)
    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError):
            pki.request(self.server,"culinaryos.internal","10.77.0.10")
    def test_san_injection_rejected(self):
        with self.assertRaises(ValueError):
            pki.request(self.root/"invalid","culinaryos.internal\nDNS:evil.internal","10.77.0.10")
    def test_expired_leaf_rejected(self):
        self.assertNotEqual(self.verify("-CAfile",self.ca/"ca.crt","-attime",str(int(time.time())+100*86400)).returncode,0)
    def handshake(self,name,ca):
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.server/"server.crt",self.server/"server.key")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1",0));listener.listen(1);listener.settimeout(4)
            port=listener.getsockname()[1]
            def accept():
                try:
                    conn,_=listener.accept()
                    with conn:
                        conn.settimeout(3)
                        with context.wrap_socket(conn,server_side=True):pass
                except (OSError,ssl.SSLError):pass
            worker=threading.Thread(target=accept,daemon=True);worker.start()
            result=lan.tls("127.0.0.1",port,name,str(ca))
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            return result
    def test_real_tls_local_trust(self):
        self.assertIs(self.handshake("culinaryos.internal",self.ca/"ca.crt"),True)
    def test_real_tls_wrong_hostname(self):
        self.assertIs(self.handshake("incorrecto.internal",self.ca/"ca.crt"),False)
    def test_csr_privileges_not_copied(self):
        directory=self.root/"hostile-csr";directory.mkdir()
        subprocess.run([self.executable,"req","-new","-newkey","ec","-pkeyopt","ec_paramgen_curve:P-256",
                        "-noenc","-keyout",directory/"key","-out",directory/"csr","-subj","/CN=wrong.internal",
                        "-addext","basicConstraints=critical,CA:TRUE","-addext","subjectAltName=DNS:wrong.internal"],capture_output=True,check=True)
        with patch("pki.execute",side_effect=self.runner):
            pki.issue(self.ca,directory/"csr",directory/"cert","culinaryos.internal","10.77.0.10")
        cert=subprocess.run([self.executable,"x509","-in",directory/"cert","-noout","-ext","basicConstraints,subjectAltName"],capture_output=True,text=True,check=True).stdout
        self.assertIn("CA:FALSE",cert);self.assertIn("DNS:culinaryos.internal",cert)
        self.assertNotIn("DNS:wrong.internal",cert)
    def test_revocation_and_crl(self):
        other=self.root/"revoked"
        with patch("pki.execute",side_effect=self.runner):
            pki.request(other,"culinaryos.internal","10.77.0.10")
            pki.issue(self.ca,other/"server.csr",other/"server.crt","culinaryos.internal","10.77.0.10")
            pki.revoke(self.ca,other/"server.crt")
            pki.crl(self.ca,self.root/"site.crl")
        p=subprocess.run([self.executable,"verify","-CAfile",self.ca/"ca.crt","-CRLfile",self.root/"site.crl",
                          "-crl_check",other/"server.crt"],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("revoked",p.stderr.lower())
if __name__=="__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
