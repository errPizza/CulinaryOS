import io
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import tarfile
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"os/overlay/usr/local/lib/culinaryos"))
import backup

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name);self.root=self.base/"root";self.dest=self.base/"copies"
        self.dest.mkdir()
        p=self.root/"etc/culinaryos/health.json"
        p.parent.mkdir(parents=True);p.write_text('{"dns_host":""}',encoding="utf-8")
        (self.root/"etc/shadow").write_text("NEVER_INCLUDE_THIS")
    def tearDown(self): self.tmp.cleanup()
    def test_roundtrip_real_files(self):
        archive=backup.create(self.root,self.dest);staging=self.base/"restored"
        backup.restore_staging(archive,staging)
        self.assertEqual((staging/"etc/culinaryos/health.json").read_bytes(),(self.root/"etc/culinaryos/health.json").read_bytes())
        self.assertFalse((staging/"etc/shadow").exists())
    def test_allowlist_only(self):
        archive=backup.create(self.root,self.dest)
        with tarfile.open(archive) as t:self.assertEqual(t.getnames(),["etc/culinaryos/health.json"])
    def test_modified_archive(self):
        archive=backup.create(self.root,self.dest)
        with open(archive,"ab") as f:f.write(b"tampered")
        with self.assertRaisesRegex(ValueError,"Checksum"):backup.restore_staging(archive,self.base/"restore")
        self.assertFalse((self.base/"restore").exists())
    def malicious(self,name,kind=tarfile.REGTYPE):
        path=self.dest/"evil.tar.gz"
        with tarfile.open(path,"w:gz") as t:
            m=tarfile.TarInfo(name);m.type=kind
            if kind==tarfile.SYMTYPE:m.linkname="../../outside"
            t.addfile(m,io.BytesIO(b""))
        Path(str(path)+".sha256").write_text(backup.checksum(path))
        return path
    def test_unsafe_paths(self):
        for name in ("../escape","/etc/nftables.conf","etc/shadow"):
            with self.subTest(name=name),self.assertRaises(ValueError):
                backup.restore_staging(self.malicious(name),self.base/"restore")
    def test_symlink_rejected(self):
        with self.assertRaises(ValueError):backup.restore_staging(self.malicious("etc/nftables.conf",tarfile.SYMTYPE),self.base/"restore")
    def test_existing_destination(self):
        archive=backup.create(self.root,self.dest);staging=self.base/"existing";staging.mkdir()
        (staging/"keep").write_text("original")
        with self.assertRaises(FileExistsError):backup.restore_staging(archive,staging)
        self.assertEqual((staging/"keep").read_text(),"original")
    def test_duplicate_members_rejected(self):
        path=self.dest/"duplicate.tar.gz"
        with tarfile.open(path,"w:gz") as t:
            for _ in range(2):
                t.addfile(tarfile.TarInfo("etc/nftables.conf"),io.BytesIO(b""))
        with self.assertRaisesRegex(ValueError,"duplicadas"): backup.validate(path)
    def test_oversized_member_rejected(self):
        path=self.dest/"large.tar.gz"
        with tarfile.open(path,"w:gz") as t:
            m=tarfile.TarInfo("etc/nftables.conf");m.size=1024*1024+1
            t.addfile(m,io.BytesIO(b"0"*m.size))
        with self.assertRaises(ValueError): backup.validate(path)
    def test_empty_archive_rejected(self):
        path=self.dest/"empty.tar.gz"
        with tarfile.open(path,"w:gz"): pass
        with self.assertRaisesRegex(ValueError,"vacía"): backup.validate(path)
    def test_checksum_required(self):
        archive=backup.create(self.root,self.dest);Path(str(archive)+".sha256").unlink()
        with self.assertRaises(FileNotFoundError):backup.restore_staging(archive,self.base/"restore")
if __name__=="__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
