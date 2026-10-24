import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"os/overlay/usr/local/lib/culinaryos"))
import base64
from contextlib import contextmanager, ExitStack
from types import SimpleNamespace
import stat
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
import socket
import time
from securedata import protect_keyring,unprotect_keyring
import unittest
from unittest.mock import patch
from securedata import Keyring,canonical,hash_password,verify_password
from store import Store
from syncworker import deliver
import dataio

class CredentialTests(unittest.TestCase):
    DIRECTORY="/run/credentials/culinaryos-data.service"

    @contextmanager
    def credential(self, directory=None, changes=None, readonly=True):
        import securedata
        raw=Keyring.generate()
        metadata={p:SimpleNamespace(st_mode=stat.S_IFDIR|0o755,st_uid=0)
                  for p in ("/","/run","/run/credentials")}
        metadata[self.DIRECTORY]=SimpleNamespace(st_mode=stat.S_IFDIR|0o550,st_uid=0)
        metadata[self.DIRECTORY+"/keyring"]=SimpleNamespace(st_mode=stat.S_IFREG|0o440,st_uid=0)
        metadata.update(changes or {})
        with ExitStack() as stack:
            stack.enter_context(patch("securedata.sys.platform","linux"))
            stack.enter_context(patch.dict(os.environ,{"CREDENTIALS_DIRECTORY":directory or self.DIRECTORY}))
            stack.enter_context(patch("securedata.os.geteuid",return_value=1001,create=True))
            stack.enter_context(patch("securedata.os.ST_RDONLY",1,create=True))
            stack.enter_context(patch("securedata.os.lstat",side_effect=lambda p:metadata[str(p)]))
            stack.enter_context(patch("securedata.os.statvfs",return_value=SimpleNamespace(f_flag=int(readonly)),create=True))
            path=stack.enter_context(patch("securedata.Path"))
            path.return_value.read_text.return_value=json.dumps(raw)
            yield raw,path

    def test_systemd_acl_mask_is_accepted_on_protected_readonly_mount(self):
        with self.credential() as (raw,path):
            loaded=Keyring.load_systemd_credential()
            self.assertEqual(loaded.active,raw["active"])
            path.assert_called_once_with(self.DIRECTORY+"/keyring")

    def test_systemd_private_owner_fallback_is_accepted(self):
        changed={self.DIRECTORY:SimpleNamespace(st_mode=stat.S_IFDIR|0o500,st_uid=1001),
                 self.DIRECTORY+"/keyring":SimpleNamespace(st_mode=stat.S_IFREG|0o400,st_uid=1001)}
        with self.credential(changes=changed) as (raw,_):
            self.assertEqual(Keyring.load_systemd_credential().active,raw["active"])

    def test_credential_shared_with_other_users_is_rejected(self):
        for location,mode in [(self.DIRECTORY,stat.S_IFDIR|0o555),
                              (self.DIRECTORY+"/keyring",stat.S_IFREG|0o444)]:
            with self.subTest(location=location),self.credential(changes={location:SimpleNamespace(st_mode=mode,st_uid=0)}) as (_,path):
                with self.assertRaises(PermissionError):Keyring.load_systemd_credential()
                path.return_value.read_text.assert_not_called()

    def test_writable_or_executable_credential_is_rejected(self):
        for mode in (0o640,0o450,0o440|stat.S_IFLNK):
            kind=stat.S_IFLNK if mode & stat.S_IFLNK else stat.S_IFREG
            changed={self.DIRECTORY+"/keyring":SimpleNamespace(st_mode=kind|(mode&0o777),st_uid=0)}
            with self.subTest(mode=mode),self.credential(changes=changed):
                with self.assertRaises(PermissionError):Keyring.load_systemd_credential()

    def test_unprotected_mount_is_rejected(self):
        with self.credential(readonly=False):
            with self.assertRaises(PermissionError):Keyring.load_systemd_credential()

    def test_environment_cannot_redirect_to_an_arbitrary_directory(self):
        for path in ("/tmp/creds","run/credentials/culinaryos-data.service",
                     "/run/credentials/other.service","/run/credentials/../culinaryos-data.service"):
            with self.subTest(path=path),self.credential(directory=path):
                with self.assertRaises(PermissionError):Keyring.load_systemd_credential()

    def test_untrusted_owner_or_parent_is_rejected(self):
        changes=({"/run/credentials":SimpleNamespace(st_mode=stat.S_IFDIR|0o777,st_uid=0)},
                 {"/run":SimpleNamespace(st_mode=stat.S_IFLNK|0o755,st_uid=0)},
                 {self.DIRECTORY+"/keyring":SimpleNamespace(st_mode=stat.S_IFREG|0o440,st_uid=2000)})
        for changed in changes:
            with self.subTest(changed=changed),self.credential(changes=changed):
                with self.assertRaises(PermissionError):Keyring.load_systemd_credential()

    def test_normal_key_files_keep_private_permission_requirement(self):
        with patch("securedata.Path") as path,patch("securedata.os.name","posix"):
            path.return_value.is_symlink.return_value=False
            path.return_value.read_text.return_value=json.dumps(Keyring.generate())
            for mode in (0o440,0o640,0o644):
                path.return_value.stat.return_value.st_mode=stat.S_IFREG|mode
                with self.subTest(mode=mode),self.assertRaises(PermissionError):Keyring.load("normal-key-file")
            path.return_value.stat.return_value.st_mode=stat.S_IFREG|0o600
            self.assertIsInstance(Keyring.load("normal-key-file"),Keyring)

    def test_configured_store_uses_systemd_specific_loader(self):
        keys=Keyring(Keyring.generate())
        with patch("dataio.persistent_root"),patch("dataio.Path") as path,patch("dataio.Store") as store,patch("dataio.Keyring.load_systemd_credential",return_value=keys) as load:
            path.return_value.read_text.return_value=json.dumps({"version":1,"site_id":"local-01"})
            self.assertEqual(dataio.configured_store(),store.return_value)
            load.assert_called_once_with()
            self.assertIs(store.call_args.args[2],keys)

class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.raw=Keyring.generate();self.keys=Keyring(self.raw)
        self.store=Store(self.root/"db.sqlite","local-01",self.keys,min_free_bytes=0)
    def tearDown(self):self.temp.cleanup()
    def put(self,number=1,**kw):
        return self.store.put("record1",number,kw.get("data",{"secret":"PRIVATE_OPERATION_973"}),"event"+str(number),number-1)
    def test_published_interoperability_vector(self):
        vector=json.loads((Path(__file__).parent/"vectors/crypto-v1.json").read_text(encoding="utf-8"))
        keys=Keyring({"active":"vector-v1","keys":{"vector-v1":vector["key_b64"]}})
        envelope=vector["envelope"]
        self.assertEqual(keys.open(envelope,vector["context"]),json.loads(vector["plaintext_utf8"]))
        with patch("securedata.os.urandom",return_value=base64.b64decode(envelope["nonce"])):
            self.assertEqual(keys.seal(json.loads(vector["plaintext_utf8"]),vector["context"]),envelope)
    def test_aead_roundtrip(self):
        c={"purpose":"unit","site_id":"local-01"}
        self.assertEqual(self.keys.open(self.keys.seal({"x":3},c),c),{"x":3})
    def test_fresh_nonce(self):
        self.assertNotEqual(self.keys.seal("x",{})["nonce"],self.keys.seal("x",{})["nonce"])
    def test_changed_ciphertext_rejected(self):
        env=self.keys.seal("x",{});raw=bytearray(base64.b64decode(env["ciphertext"]));raw[0]^=1
        env["ciphertext"]=base64.b64encode(raw).decode()
        with self.assertRaises(Exception):self.keys.open(env,{})
    def test_context_and_site_bound(self):
        env=self.keys.seal("x",{"site_id":"a"})
        with self.assertRaises(Exception):self.keys.open(env,{"site_id":"b"})
    def test_wrong_key_rejected(self):
        with self.assertRaises(Exception):Keyring(Keyring.generate()).open(self.keys.seal("x",{}),{})
    def test_argon_password(self):
        encoded=hash_password("unique test password")
        self.assertTrue(encoded.startswith("$argon2id$"))
        self.assertTrue(verify_password(encoded,"unique test password"))
        self.assertFalse(verify_password(encoded,"incorrect"))
    def test_record_and_event_commit(self):
        self.put();self.assertEqual(self.store.get("record1")["data"]["secret"],"PRIVATE_OPERATION_973")
        self.assertEqual(self.store.status()["pending"],1)
    def test_disk_has_no_payload_plaintext(self):
        self.put()
        for file in self.root.iterdir():
            if file.is_file():self.assertNotIn(b"PRIVATE_OPERATION_973",file.read_bytes())
    def test_synchronous_and_wal(self):
        with self.store.connection() as db:
            self.assertEqual(db.execute("PRAGMA synchronous").fetchone()[0],2)
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0],"wal")
    def test_atomic_rollback_if_second_encryption_fails(self):
        original=self.keys.seal
        calls=0
        def fail(data,ctx):
            nonlocal calls
            calls+=1
            if calls==2:raise RuntimeError("injected failure")
            return original(data,ctx)
        with patch.object(self.keys,"seal",side_effect=fail),self.assertRaises(RuntimeError):self.put()
        self.assertIsNone(self.store.get("record1"));self.assertEqual(self.store.status()["pending"],0)
    def test_idempotent_client_retry(self):
        self.put();self.assertTrue(self.put()["duplicate"]);self.assertEqual(self.store.status()["events"],1)
    def test_event_id_content_mismatch_rejected(self):
        self.put()
        with self.assertRaises(ValueError):self.put(data={"different":True})
    def test_version_conflict_rejected(self):
        self.put()
        with self.assertRaises(ValueError):self.store.put("record1",1,{}, "other",0)
    def test_reopen_persists(self):
        self.put()
        reopened=Store(self.root/"db.sqlite","local-01",self.keys,0)
        self.assertEqual(reopened.get("record1")["version"],1)
    def test_wrong_site_rejected(self):
        with self.assertRaises(ValueError):Store(self.root/"db.sqlite","local-02",self.keys,0)
    def test_disk_low_does_not_confirm(self):
        self.store.min_free_bytes=2**100
        with self.assertRaises(OSError):self.put()
        self.assertIsNone(self.store.get("record1"))
    def test_offline_retains_and_retries(self):
        self.put()
        class Offline:
            def send(self,e,d):raise OSError("offline")
        self.assertEqual(deliver(self.store,Offline(),now=100)["state"],"pending")
        self.assertEqual(self.store.status()["pending"],1)
        self.assertEqual(self.store.pending(now=101),[])
        self.assertEqual(len(self.store.pending(now=106)),1)
    def test_fifo_retry_blocks_later_events(self):
        self.put();self.put(2)
        self.store.retry("event1",100)
        self.assertEqual(self.store.pending(now=101),[])
    def test_valid_ack(self):
        self.put()
        class Central:
            def send(self,e,d):return {"site_id":e["site_id"],"event_id":e["event_id"],"sha256":d,"status":"committed"}
        self.assertEqual(deliver(self.store,Central())["sent"],1)
        self.assertEqual(self.store.status()["pending"],0)
    def test_bad_ack_does_not_drop(self):
        self.put()
        class Central:
            def send(self,e,d):return {"site_id":"wrong","event_id":e["event_id"],"sha256":d,"status":"committed"}
        self.assertEqual(deliver(self.store,Central())["state"],"pending")
        self.assertEqual(self.store.status()["pending"],1)
    def test_lost_response_at_least_once(self):
        self.put()
        seen=set()
        class Central:
            def send(self,e,d):
                duplicate=e["event_id"] in seen;seen.add(e["event_id"])
                if not duplicate:raise OSError("response lost after commit")
                return {"site_id":e["site_id"],"event_id":e["event_id"],"sha256":d,"status":"committed"}
        transport=Central();deliver(self.store,transport,100);deliver(self.store,transport,106)
        self.assertEqual(len(seen),1);self.assertEqual(self.store.status()["pending"],0)
    def test_snapshot_restore(self):
        self.put();self.store.snapshot(self.root/"copy.sqlite")
        restored=Store(self.root/"copy.sqlite","local-01",self.keys,0)
        self.assertEqual(restored.get("record1")["version"],1)
    def test_rotation_preserves_records_and_events(self):
        self.put();new=Keyring.generate()
        self.raw["keys"].update(new["keys"]);self.raw["active"]=new["active"]
        self.store.keys=Keyring(self.raw);self.store.rotate()
        newonly=Store(self.root/"db.sqlite","local-01",Keyring(new),0)
        self.assertEqual(newonly.get("record1")["version"],1);self.assertEqual(len(newonly.pending()),1)
    def test_uncommitted_process_kill_recovers(self):
        self.put()
        code="import sqlite3,sys,time; c=sqlite3.connect(sys.argv[1]); c.execute('BEGIN IMMEDIATE'); c.execute(\"UPDATE records SET envelope='UNCOMMITTED'\"); print('ready',flush=True); time.sleep(30)"
        p=subprocess.Popen([sys.executable,"-c",code,str(self.root/"db.sqlite")],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(p.stdout.readline().strip(),"ready")
            p.kill();p.wait(timeout=5)
        finally:
            if p.poll() is None:p.kill();p.wait(timeout=5)
            p.stdout.close()
        self.assertEqual(self.store.get("record1")["version"],1)
        self.assertTrue(self.store.status()["ready"])
    def test_reopen_with_wrong_key_fails_before_ready(self):
        with self.assertRaises(Exception):Store(self.root/"db.sqlite","local-01",Keyring(Keyring.generate()),0)
    def test_clock_rollback_does_not_stall_forever(self):
        self.put();self.store.retry("event1",now=9999999)
        self.assertEqual(len(self.store.pending(now=100)),1)
    def test_key_backup_roundtrip_and_scope(self):
        encrypted=protect_keyring(self.raw,"long test backup password","local-01")
        self.assertEqual(unprotect_keyring(encrypted,"long test backup password","local-01"),self.raw)
        self.assertNotIn(self.raw["keys"][self.raw["active"]],json.dumps(encrypted))
        with self.assertRaises(ValueError):unprotect_keyring(encrypted,"long test backup password","other")
        with self.assertRaises(Exception):unprotect_keyring(encrypted,"incorrect password","local-01")
    @unittest.skipUnless(hasattr(socket,"AF_UNIX"),"Transporte AF_UNIX pendiente de entorno Linux")
    def test_real_unix_ipc(self):
        path=self.root/"ipc.sock";stop=threading.Event()
        worker=threading.Thread(target=dataio.serve,args=(self.store,path,stop),daemon=True)
        worker.start()
        try:
            for _ in range(100):
                if path.exists():break
                time.sleep(.01)
            client=dataio.Client(path)
            self.assertTrue(client.call("health")["ready"])
            client.call("put",record_id="ipc1",version=1,expected_version=0,event_id="ipc-event",data={"x":4})
            self.assertEqual(client.call("get",record_id="ipc1")["data"],{"x":4})
            with self.assertRaises(ValueError):client.call("invalid")
        finally:
            stop.set();worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
    def test_dispatch_rejects_unknown(self):
        with self.assertRaises(ValueError):dataio.dispatch(self.store,{"op":"exec","command":"none"})
    def test_payload_size_rejected(self):
        with self.assertRaises(ValueError):self.put(data={"x":"a"*70000})
        self.assertEqual(self.store.status()["events"],0)
if __name__=="__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
