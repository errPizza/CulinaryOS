"""Kit de recuperación y restauración; sin servicios, PostgreSQL ni escrituras fuera de carpetas temporales."""
import base64,hashlib,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'os/overlay/usr/local/lib/culinaryos'))
sys.path.insert(0,str(ROOT/'os/appliance/usr/local/lib/culinaryos'))
import recovery
from securedata import Keyring,encode

PASSWORD='una-contraseña-de-prueba'

def tree(base,site):
    (base/'secrets').mkdir();(base/'integrations').mkdir()
    values={'site.json':json.dumps({'site_id':site,'server_name':'s.internal','server_address':'127.0.0.1','local_only':True}),
            'branch.json':json.dumps({'version':1,'site_id':site,'central':None}),'secrets/branch.keys.json':json.dumps(Keyring.generate()),
            'restaurant-ca.crt':'ca','secrets/restaurant-ca.key':'ca-key','restaurant-tls.crt':'tls','secrets/restaurant-tls.key':'tls-key',
            'restaurant-connection.json':'{}','printer.json':'{"a":1}','integrations/pac.json':'{"token":"x"}'}
    for name,value in values.items():(base/name).write_text(value,encoding='utf-8')
    (base/'application.json').write_text(json.dumps({'backend_argv':['api','--site','site-new','--port','8443']}),encoding='utf-8')
    return values

class KitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)/'etc';self.base.mkdir()
        self.values=tree(self.base,'site-a')
    def kit(self):return recovery.seal_kit(recovery.read_files(self.base),PASSWORD,'site-a')
    def test_kit_round_trip_keeps_every_file(self):
        site,files=recovery.open_kit(self.kit(),PASSWORD)
        self.assertEqual(site,'site-a')
        self.assertEqual({name:base64.b64decode(item['data']).decode('utf-8') for name,item in files.items()},self.values)
        self.assertNotIn('application.json',files,'the manifest belongs to the new machine')
    def test_kit_shows_no_secret_and_holds_no_license(self):
        text=json.dumps(self.kit())
        for secret in ('ca-key','tls-key','token'):self.assertNotIn(secret,text)
        self.assertFalse(any('license' in name for name in recovery.read_files(self.base)))
    def test_wrong_password_and_other_site_are_refused(self):
        kit=self.kit()
        with self.assertRaises(Exception):recovery.open_kit(kit,'otra-contraseña-distinta')
        with self.assertRaises(Exception):recovery.open_kit({**kit,'site_id':'site-b'},PASSWORD)
    def test_short_password_refused(self):
        with self.assertRaises(ValueError):recovery.seal_kit({},'corta','site-a')
    def test_missing_required_file_stops_the_kit(self):
        (self.base/'secrets/restaurant-ca.key').unlink()
        with self.assertRaises(ValueError):recovery.read_files(self.base)
    def test_kit_cannot_write_outside_its_list(self):
        for name in ('../../etc/passwd','secrets/otra.key','integrations/../x.json','application.json'):
            self.assertFalse(recovery.allowed(name),name)
        files=recovery.read_files(self.base)
        files['../../etc/passwd']={'data':encode(b'x'),'mode':0o644}
        with self.assertRaises(ValueError):recovery.open_kit(recovery.seal_kit(files,PASSWORD,'site-a'),PASSWORD)
    def test_kit_mixing_branches_is_refused(self):
        with self.assertRaises(ValueError):recovery.open_kit(recovery.seal_kit(recovery.read_files(self.base),PASSWORD,'site-b'),PASSWORD)
    def test_dump_must_match_its_checksum(self):
        dump=Path(self.tmp.name)/'a.dump';dump.write_bytes(b'copia')
        Path(str(dump)+'.sha256').write_text(hashlib.sha256(b'copia').hexdigest()+'  '+str(dump)+'\n')
        recovery.check_dump(dump)
        dump.write_bytes(b'otra')
        with self.assertRaises(ValueError):recovery.check_dump(dump)
        Path(str(dump)+'.sha256').unlink()
        with self.assertRaises(OSError):recovery.check_dump(dump)

class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        origin=root/'origin';origin.mkdir();tree(origin,'site-a')
        self.base=root/'etc';self.base.mkdir();tree(self.base,'site-new')
        self.sqlite=root/'sqlite';self.sqlite.mkdir();(self.sqlite/'store.sqlite').write_text('fresh')
        self.kit=root/'kit.json';self.kit.write_text(json.dumps(recovery.seal_kit(recovery.read_files(origin),PASSWORD,'site-a')))
        self.dump=root/'a.dump';self.dump.write_bytes(b'copia')
        Path(str(self.dump)+'.sha256').write_text(hashlib.sha256(b'copia').hexdigest()+'  a.dump\n')
        hosts=root/'hosts';hosts.write_text('127.0.0.1 localhost'+chr(10))
        self.calls=[]
        self.owners={}
        self.installer=types.SimpleNamespace(initialized=MagicMock(return_value={'meta':None}),app_command=MagicMock(return_value=types.SimpleNamespace(returncode=0,stdout=b'{"valid":true}')))
        self.appliance=types.SimpleNamespace(application_hosts=MagicMock(return_value='hosts\n'),write=MagicMock())
        def write_file(path,data,mode=0o644):
            Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_bytes(data)
        def run(args,**kwargs):
            self.calls.append(' '.join(map(str,args)));return types.SimpleNamespace(returncode=0)
        temporary=tempfile.TemporaryDirectory
        modules={'appliance':self.appliance,'appliance_install':self.installer,'deployment':types.SimpleNamespace(write_file=write_file),
                 'provision':types.SimpleNamespace(admin=lambda:None,central_credentials=lambda:self.calls.append('central')),
                 'pwd':types.SimpleNamespace(getpwnam=lambda name:types.SimpleNamespace(pw_gid=99))}
        for item in (patch.dict(sys.modules,modules),patch.object(recovery,'CONFIG',self.base),patch.object(recovery,'SQLITE',self.sqlite),
                     patch.object(recovery,'BACKUPS',root/'backups'),patch.object(recovery,'HOSTS',hosts),patch.object(recovery.subprocess,'run',side_effect=run),
                     patch.object(recovery.getpass,'getpass',return_value=PASSWORD),
                     patch.object(recovery.os,'chown',create=True,side_effect=lambda path,uid,gid:self.owners.__setitem__(Path(path).name,gid)),
                     patch.object(recovery.tempfile,'TemporaryDirectory',side_effect=lambda **kwargs:temporary())):
            item.start();self.addCleanup(item.stop)
    def site(self):return json.loads((self.base/'site.json').read_text())['site_id']
    def test_restore_installs_identity_and_swaps_the_database_only_after_verifying(self):
        recovery.restore(self.kit,self.dump)
        self.assertEqual(self.site(),'site-a')
        self.assertEqual(json.loads((self.base/'application.json').read_text())['backend_argv'][2],'site-a')
        self.assertEqual(list(self.sqlite.glob('store.sqlite*')),[])
        order=[next(i for i,c in enumerate(self.calls) if key in c) for key in ('pg_restore','systemctl stop','DROP DATABASE culinaryos','RENAME TO culinaryos','systemctl start')]
        self.assertEqual(order,sorted(order))
        args=' '.join(self.installer.app_command.call_args.args)
        for expected in ('--verify-store','--site site-a','Database=culinaryos_restore'):self.assertIn(expected,args)
    def test_a_restore_declares_itself_to_the_checkpoints_before_the_backend_starts(self):
        (self.base/'integrations').mkdir(exist_ok=True)
        (self.base/'integrations/checkpoints.json').write_text('{}')
        self.installer.app_command.side_effect=lambda *a,**k:(self.calls.append('accept') if '--accept-checkpoints' in a else None) or types.SimpleNamespace(returncode=0,stdout=b'{"valid":true}')
        recovery.restore(self.kit,self.dump)
        self.assertLess(self.calls.index('accept'),next(i for i,c in enumerate(self.calls) if 'systemctl start' in c))
    def test_failed_verification_leaves_the_machine_untouched(self):
        self.installer.app_command.return_value=types.SimpleNamespace(returncode=4,stdout=b'{"valid":false}')
        with self.assertRaises(ValueError):recovery.restore(self.kit,self.dump)
        self.assertEqual(self.site(),'site-new')
        self.assertTrue((self.sqlite/'store.sqlite').exists())
        self.assertFalse(any('systemctl' in c for c in self.calls),self.calls)
        self.assertIn('DROP DATABASE IF EXISTS culinaryos_restore',self.calls[-1])
    def test_a_machine_with_a_restaurant_is_refused_before_anything_runs(self):
        self.installer.initialized.return_value={'meta':{'data':{}}}
        with self.assertRaises(ValueError):recovery.restore(self.kit,self.dump)
        self.assertEqual(self.calls,[])
    def test_bad_dump_stops_before_touching_postgresql(self):
        self.dump.write_bytes(b'alterada')
        with self.assertRaises(ValueError):recovery.restore(self.kit,self.dump)
        self.assertEqual(self.calls,[])
    def test_failure_during_the_swap_puts_the_previous_files_back(self):
        self.appliance.write.side_effect=OSError('disco')
        with self.assertRaises(OSError):recovery.restore(self.kit,self.dump)
        self.assertEqual(self.site(),'site-new')
        self.assertTrue((self.sqlite/'store.sqlite').exists())
        self.assertFalse(any(c.endswith('DROP DATABASE culinaryos') for c in self.calls),self.calls)
    def test_shared_files_go_to_the_service_group_and_secrets_stay_with_root(self):
        files={'printer.json':{'data':encode(b'{}'),'mode':0o640},'secrets/restaurant-ca.key':{'data':encode(b'k'),'mode':0o600}}
        recovery.install_files(files,'site-a',99)
        self.assertEqual(self.owners,{'printer.json':99,'restaurant-ca.key':0})

class ProjectTests(unittest.TestCase):
    def test_image_ships_both_commands(self):
        for name,command in (('culinaryos-recovery-kit','kit'),('culinaryos-restore','restore')):
            data=(ROOT/'os/appliance/usr/local/sbin'/name).read_bytes()
            self.assertNotIn(b'\r',data)
            self.assertIn(('recovery.py '+command+' "$@"').encode(),data)

if __name__=='__main__':
    unittest.main(verbosity=1)
