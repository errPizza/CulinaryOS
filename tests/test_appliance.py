"""Integrated image checks; no writes to host users, disks, keys or services."""
import ast,importlib.util,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'os/overlay/usr/local/lib/culinaryos'
sys.path.insert(0,str(LIB))

class ApplianceTests(unittest.TestCase):
    def test_dev_installer_keeps_disk_choice_manual_and_hashes_its_default_password(self):
        config=json.loads((ROOT/'config/appliance.json').read_text(encoding='utf-8'))
        self.assertTrue(config['application_included']);self.assertTrue(config['kiosk'])
        build=(ROOT/'scripts/build-appliance.sh').read_text(encoding='utf-8')
        self.assertIn('--debian-installer live',build)
        self.assertIn('--debian-installer-preseedfile preseed.cfg',build)
        self.assertIn('config/preseed/culinaryos.cfg',build)
        self.assertNotIn('cp -a "$project/."',build)
        seed=(ROOT/'config/appliance-preseed.cfg').read_text(encoding='utf-8')
        for forbidden in ('partman-auto/disk','partman/confirm','passwd/user-password password','root-password'):
            self.assertNotIn(forbidden,seed)
        self.assertIn('passwd/user-password-crypted password @DEVMODE_PASSWORD_HASH@',seed)
        self.assertIn('passwd/username string devmode',seed)
        self.assertIn('passwd/user-fullname string DevMode',seed)
        self.assertIn('partman-auto/method string regular',seed)
        self.assertIn('partman-auto/choose_recipe select atomic',seed)
        self.assertIn('passwd/root-login boolean false',seed)
        self.assertIn('culinaryos-installer-finish',seed)

    def test_installer_is_the_first_boot_option_in_bios_and_uefi(self):
        base=ROOT/'config/appliance-bootloaders'
        bios=(base/'syslinux_common/install_gui.cfg').read_text(encoding='utf-8')
        uefi=(base/'grub-pc/grub.cfg').read_text(encoding='utf-8')
        self.assertIn('menu default',bios.split('label installtext')[0])
        self.assertLess(uefi.index("menuentry 'Instalar CulinaryOS"),uefi.index("menuentry 'Instalador en modo texto'"))
        for text in (bios,uefi):
            self.assertIn('@KERNEL_GI@',text);self.assertIn('@KERNEL_DI@',text)
            self.assertIn('rescue/enable=true',text)
            self.assertNotIn('partman-auto',text)
        self.assertIn('config/appliance-bootloaders', (ROOT/'scripts/build-appliance.sh').read_text(encoding='utf-8'))

    def test_firstboot_has_fresh_identity_and_no_live_operational_store(self):
        text=(ROOT/'os/appliance/usr/local/lib/culinaryos/appliance.py').read_text(encoding='utf-8')
        ast.parse(text)
        self.assertLess(text.index('persistent_root()'),text.index("run('useradd'"))
        self.assertIn("secrets.token_hex(8)",text)
        # The restaurant and manager are created in Culinary Restaurant's Setup mode, never on tty1.
        self.assertNotIn("initialize_branch",text)
        self.assertNotIn("input(",text)
        self.assertIn("setup_code=prepare_setup(operator)",text)
        self.assertIn("'setup-code':str(setup_code)",text)
        self.assertLess(text.index("installer.certificates(site)"),text.index("setup_code=prepare_setup(operator)"))
        self.assertIn("installer.certificates(site)",text)
        self.assertIn("register(APP/'application.json')",text)
        self.assertNotIn('NOPASSWD',text)
        self.assertIn("run('chpasswd',input='operador:'+password",text)
        self.assertIn('secrets.token_urlsafe(48)',text)
        # No accounts, site or operational keys are checked into the image overlay.
        for name in ('site.json','branch.json','application.json','restaurant-connection.json'):
            self.assertFalse((ROOT/'os/appliance/etc/culinaryos'/name).exists())

    def test_setup_code_goes_to_backend_credential_and_kiosk_copy_only(self):
        spec=importlib.util.spec_from_file_location('appliance',ROOT/'os/appliance/usr/local/lib/culinaryos/appliance.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        operator=types.SimpleNamespace(pw_uid=1001,pw_gid=1001)
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'etc';kiosk=Path(tmp)/'kiosk';(base/'secrets').mkdir(parents=True)
            with patch.object(module,'BASE',base),patch.object(module,'SETUP',kiosk),patch.object(module.os,'chown',create=True) as chown,patch.object(module.os,'fchown',create=True) as fchown:
                code_file=module.prepare_setup(operator)
                first=code_file.read_bytes()
                (kiosk/'setup-code').unlink()
                self.assertEqual(module.prepare_setup(operator),code_file)
            self.assertEqual(code_file,base/'secrets/restaurant-setup.code')
            self.assertGreaterEqual(len(first.strip()),32)
            self.assertEqual(code_file.read_bytes(),first,'a rerun keeps the same backend code')
            self.assertEqual((kiosk/'setup-code').read_bytes(),first)
            self.assertIn(((kiosk,1001,1001),{}),[(c.args,c.kwargs) for c in chown.call_args_list])
            self.assertIn((1001,1001),[c.args[1:] for c in fchown.call_args_list])
            self.assertIn((0,0),[c.args[1:] for c in fchown.call_args_list])
            (kiosk/'setup-code').unlink()
            if hasattr(os,'symlink'):
                try:os.symlink(base/'elsewhere',kiosk/'setup-code')
                except OSError:pass
                else:
                    with patch.object(module,'BASE',base),patch.object(module,'SETUP',kiosk),patch.object(module.os,'chown',create=True),self.assertRaises(OSError):
                        module.create_private(kiosk/'setup-code',b'x')

    def test_local_network_mode_uses_loopback_and_does_not_require_internet(self):
        spec=importlib.util.spec_from_file_location('appliance',ROOT/'os/appliance/usr/local/lib/culinaryos/appliance.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with patch('builtins.input',return_value=''):
            site,rendered=module.network_config('site-fresh')
        self.assertTrue(site['local_only']);self.assertEqual(site['server_address'],'127.0.0.1')
        self.assertEqual(site['interface'],'lo');self.assertEqual(site['internet_probes'],[])
        self.assertIsNone(rendered)

    def test_machine_name_alias_does_not_block_firstboot_or_remove_other_hosts(self):
        spec=importlib.util.spec_from_file_location('appliance',ROOT/'os/appliance/usr/local/lib/culinaryos/appliance.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        original='127.0.0.1 localhost\n127.0.1.1 culinaryos.internal culinaryos # equipo\n::1 localhost ip6-localhost culinaryos.internal\n192.168.1.99 impresora\n'
        for address in ('127.0.0.1','192.168.1.10'):
            result=module.application_hosts(original,{'server_name':'culinaryos.internal','server_address':address})
            self.assertIn('127.0.0.1 localhost',result)
            self.assertIn('127.0.1.1 culinaryos # equipo',result)
            self.assertIn('::1 localhost ip6-localhost',result)
            self.assertIn('192.168.1.99 impresora',result)
            self.assertEqual(result.count('culinaryos.internal'),1)
            self.assertIn(address+' culinaryos.internal',result)

    def test_service_name_pointing_to_another_machine_is_not_silently_replaced(self):
        spec=importlib.util.spec_from_file_location('appliance',ROOT/'os/appliance/usr/local/lib/culinaryos/appliance.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with self.assertRaises(ValueError):
            module.application_hosts('192.168.1.99 culinaryos.internal\n',{'server_name':'culinaryos.internal','server_address':'127.0.0.1'})

    def test_units_started_by_firstboot_never_wait_for_firstboot(self):
        # appliance.py runs inside culinaryos-firstboot.service (no start timeout) and starts these
        # units; any of them ordered after firstboot deadlocks the first boot behind the splash.
        def files(name):
            unit=ROOT/'os/appliance/etc/systemd/system'/name
            if not unit.exists():unit=ROOT/'os/overlay/etc/systemd/system'/name
            dropins=[p for base in ('overlay','appliance') for p in sorted((ROOT/'os'/base/'etc/systemd/system'/(name+'.d')).glob('*.conf'))]
            return [unit,*dropins]
        def after(name):
            # systemd ignores an empty After= in drop-ins: dependencies can only be added.
            return {value for path in files(name) if path.exists() for line in path.read_text(encoding='utf-8').splitlines() if line.startswith('After=') for value in line[6:].split()}
        seen=set();pending=['culinaryos-data.service','culinaryos-sync.timer','culinaryos-backend.service']
        while pending:
            name=pending.pop()
            if name in seen:continue
            seen.add(name)
            ordering=after(name)
            self.assertNotIn('culinaryos-firstboot.service',ordering,name)
            pending.extend(x for x in ordering if x.startswith('culinaryos-'))
        self.assertIn('culinaryos-data.service',seen)
        firstboot=(ROOT/'os/appliance/etc/systemd/system/culinaryos-firstboot.service.d/appliance.conf').read_text(encoding='utf-8')
        self.assertIn('TimeoutStartSec=15min',firstboot,'the integrated first boot has no prompts and must not wait forever')
        for path in (ROOT/'os').rglob('*.conf'):
            if '.service.d' in str(path):
                self.assertNotIn('\nAfter=\n','\n'+path.read_text(encoding='utf-8'),'empty After= does not reset dependencies: '+str(path))

    def test_local_registration_keeps_real_tls_checks_without_lan_port_or_announcement(self):
        import provision,apphost,lan,deployment
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            def mapped(value):
                p=Path(value)
                if str(value).replace('\\','/').startswith('/') and not p.is_relative_to(base):return base/p.as_posix().lstrip('/')
                return p
            def write(path,data,mode=0o644):
                p=mapped(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data if isinstance(data,bytes) else json.dumps(data).encode())
            site={'site_id':'site-fresh','role':'servidor','server_address':'127.0.0.1','server_name':'culinaryos.internal','local_only':True}
            write('/etc/culinaryos/site.json',site);write('/etc/culinaryos/branch.json',{'site_id':'site-fresh'})
            write('/etc/nftables.conf',b'LOCAL DENY BASELINE')
            cfg={'mode':'server','port':8443,'tls_ca_file':'/etc/ca.crt','credentials':{}}
            with patch.object(provision,'admin'),patch.object(provision,'manifest',return_value=cfg),patch.object(provision,'Path',side_effect=mapped),patch.object(provision,'atomic',side_effect=write),patch.object(deployment,'write_file',side_effect=write),patch.object(provision.subprocess,'run') as calls,patch.object(lan,'tls',return_value=True) as tls:
                provision.register('/opt/new-application.json')
            self.assertTrue(tls.called)
            self.assertEqual(mapped('/etc/nftables.conf').read_bytes(),b'LOCAL DENY BASELINE')
            self.assertTrue(mapped('/etc/culinaryos/application.registered').exists())
            all_args=[str(item) for call in calls.call_args_list for item in call.args[0]]
            self.assertNotIn('culinaryos-publish.service',all_args)
            self.assertNotIn('/usr/local/sbin/culinaryos-firewall-apply',all_args)
            self.assertIn('culinaryos-backend.service',all_args)

    def test_failed_tls_never_registers_local_app(self):
        import provision,lan,deployment
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            def mapped(value):
                p=Path(value)
                return base/p.as_posix().lstrip('/') if str(value).replace('\\','/').startswith('/') and not p.is_relative_to(base) else p
            def write(path,data,mode=0o644):
                p=mapped(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data if isinstance(data,bytes) else json.dumps(data).encode())
            site={'site_id':'site-fresh','role':'servidor','server_address':'127.0.0.1','server_name':'culinaryos.internal','local_only':True}
            write('/etc/culinaryos/site.json',site);write('/etc/culinaryos/branch.json',{})
            write('/etc/nftables.conf',b'BASELINE')
            cfg={'mode':'server','port':8443,'tls_ca_file':'/etc/ca.crt','credentials':{}}
            with patch.object(provision,'admin'),patch.object(provision,'manifest',return_value=cfg),patch.object(provision,'Path',side_effect=mapped),patch.object(provision,'atomic',side_effect=write),patch.object(deployment,'write_file',side_effect=write),patch.object(provision.subprocess,'run'),patch.object(lan,'tls',return_value=False),self.assertRaises(RuntimeError):
                provision.register('/opt/new-application.json')
            self.assertFalse(mapped('/etc/culinaryos/application.registered').exists())
            self.assertFalse(mapped('/etc/culinaryos/application.json').exists())
            self.assertEqual(mapped('/etc/nftables.conf').read_bytes(),b'BASELINE')

if __name__=='__main__':unittest.main()
