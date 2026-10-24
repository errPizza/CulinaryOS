import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"os/overlay/usr/local/lib/culinaryos"))
import json
import tempfile
import unittest
from unittest.mock import patch
import apphost
import discovery
import deployment
import provision
import ups
import runtimehealth

class RuntimeTests(unittest.TestCase):
    def test_chrony_validation_avoids_config_file_access(self):
        from subprocess import CompletedProcess
        config="driftfile /var/lib/chrony/chrony.drift\nrtcsync\nlocal stratum 10\nallow 10.77.0.0/24\n"
        with patch("deployment.subprocess.run",return_value=CompletedProcess([],0,"","")) as run:
            deployment.validate_chrony(config)
        argv=run.call_args.args[0]
        self.assertEqual(argv,["chronyd","-p",*config.splitlines()])
        self.assertNotIn("-f",argv)
        self.assertEqual(run.call_args.kwargs["timeout"],10)

    def test_chrony_rejection_keeps_actual_error(self):
        from subprocess import CompletedProcess
        with patch("deployment.subprocess.run",return_value=CompletedProcess([],1,"","Cannot read configuration")):
            with self.assertRaisesRegex(RuntimeError,"Cannot read configuration"):
                deployment.validate_chrony("rtcsync\n")

    def test_chrony_timeout_fails_and_empty_config_is_not_run(self):
        from subprocess import TimeoutExpired
        with patch("deployment.subprocess.run",side_effect=TimeoutExpired("chronyd",10)):
            with self.assertRaisesRegex(RuntimeError,"10 segundos"):
                deployment.validate_chrony("rtcsync\n")
        with patch("deployment.subprocess.run") as run:
            with self.assertRaises(ValueError):deployment.validate_chrony("# sin directivas\n")
            run.assert_not_called()

    def runtime_fixture(self,branch=None,ups_mode=None,status=None,failure=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def mapped(value):return root/str(value).lstrip("/")
            if branch is not None:
                file=mapped("/etc/culinaryos/branch.json");file.parent.mkdir(parents=True);file.write_text(json.dumps(branch))
            if ups_mode is not None:
                file=mapped("/etc/nut/nut.conf");file.parent.mkdir(parents=True);file.write_text(ups_mode)
            with patch("runtimehealth.Path",side_effect=mapped),patch("dataio.Client") as client,patch("runtimehealth.run",side_effect=lambda a: "OB LB" if a[0]=="upsc" else "inactive"):
                if failure:client.return_value.call.side_effect=RuntimeError(failure)
                else:client.return_value.call.return_value=status
                return runtimehealth.checks()
    def test_unprovisioned_data_not_claimed_ready(self):
        rows=self.runtime_fixture()
        self.assertEqual(next(r for r in rows if r["id"]=="COS-DATA")["gravedad"],"no_aplica")
    def test_data_failure_is_critical_without_trace(self):
        rows=self.runtime_fixture(branch={"site_id":"local-01"},failure="SECRET_INTERNAL_TRACE")
        self.assertEqual(next(r for r in rows if r["id"]=="COS-DATA")["gravedad"],"critico")
        self.assertNotIn("SECRET_INTERNAL_TRACE",str(rows))
    def test_pending_sync_hides_endpoint(self):
        rows=self.runtime_fixture(branch={"site_id":"local-01","central":{"url":"https://SECRET_INTERNAL_URL/"}},status={"ready":True,"pending":4})
        row=next(r for r in rows if r["id"]=="COS-SYNC")
        self.assertEqual(row["gravedad"],"aviso");self.assertIn("4",row["mensaje"])
        self.assertNotIn("SECRET_INTERNAL_URL",str(rows))
    def test_critical_ups_not_downgraded_if_monitor_off(self):
        rows=self.runtime_fixture(ups_mode="MODE=standalone\n")
        self.assertEqual(next(r for r in rows if r["id"]=="COS-UPS")["gravedad"],"critico")
    def test_host_admin_guard(self):
        with patch("provision.sys.platform","win32"),self.assertRaises(PermissionError):provision.admin()
    def test_hosts_roundtrip_preserves_other_entries(self):
        old="127.0.0.1 localhost\n10.0.0.5 printer\n"
        new=deployment.hosts_content(old,"10.77.0.10 culinaryos.internal servidor-01\n")
        self.assertIn("10.0.0.5 printer",new)
        self.assertEqual(deployment.hosts_content(new,"10.77.0.10 culinaryos.internal servidor-01\n"),new)
    def test_hosts_conflict_rejected(self):
        with self.assertRaises(ValueError):
            deployment.hosts_content("10.0.0.8 culinaryos.internal\n","10.77.0.10 culinaryos.internal\n")
    def test_hosts_truncated_block_rejected(self):
        with self.assertRaises(ValueError):deployment.hosts_content("# BEGIN CulinaryOs site\n","10.77.0.10 culinaryos.internal\n")
    def test_usb_match_requires_exactly_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ("dev1","dev2"):
                p=root/name;p.mkdir();(p/"idVendor").write_text("051d");(p/"idProduct").write_text("0002");(p/"serial").write_text(name)
            with self.assertRaises(ValueError):ups.check_device({"vendor":"051d","product":"0002","serial":None},root)
            self.assertEqual(ups.check_device({"vendor":"051d","product":"0002","serial":"dev2"},root),"dev2")
    def test_ups_secrets_unique_and_local_only(self):
        a=ups.render("usbhid-ups","051d","0002")
        b=ups.render("usbhid-ups","051d","0002")
        self.assertNotEqual(a["upsd.users"],b["upsd.users"])
        self.assertIn("LISTEN 127.0.0.1",a["upsd.conf"])
        self.assertNotIn("0.0.0.0",a["upsd.conf"])
        password=a["upsd.users"].split("password = ")[1].split()[0]
        self.assertIn(password,a["upsmon.conf"])
    def test_ups_injection_and_unknown_driver_rejected(self):
        for driver,vendor,product,serial in [("dummy-ups","051d","0002",None),("usbhid-ups","051d\nexec","0002",None),("usbhid-ups","051d","0002",'x"\nSHUTDOWNCMD')]:
            with self.assertRaises(ValueError):ups.render(driver,vendor,product,serial)
    def test_discovery_parse_and_no_implicit_trust(self):
        text='=;enp1s0;IPv4;CulinaryOs\\032local-01;_culinaryos._tcp;local;servidor-restaurante.local;10.77.0.10;8443;"site_id=local-01"\n'
        result=discovery.parse(text,"enp1s0")
        self.assertEqual(result[0]["name"],"CulinaryOs local-01")
        self.assertFalse(result[0]["trusted"])
        self.assertEqual(discovery.parse(text,"other"),[])
    def test_discovery_does_not_trust_txt(self):
        candidate={"interface":"enp1s0","address":"10.77.0.66","port":8443,"metadata":["trusted=true"],"trusted":True}
        config={"network":"10.77.0.0/24","interface":"enp1s0","port":8443,"server_name":"culinaryos.internal","ca_file":"/ca.crt"}
        with patch("lan.tls",return_value=False):
            self.assertFalse(discovery.verify_candidate(candidate,config))
        with patch("lan.tls",return_value=True):
            self.assertTrue(discovery.verify_candidate(candidate,config))
    def test_discovery_rejects_outside_lan_before_tls(self):
        candidate={"interface":"enp1s0","address":"8.8.8.8","port":8443}
        cfg={"network":"10.77.0.0/24","interface":"enp1s0","port":8443,"server_name":"culinaryos.internal","ca_file":"/ca"}
        with patch("lan.tls") as tls:
            self.assertFalse(discovery.verify_candidate(candidate,cfg));tls.assert_not_called()
    def test_mdns_publish_has_no_secret(self):
        args=discovery.publish_arguments({"site_id":"local-01","server_name":"culinaryos.internal"},8443)
        self.assertEqual(args[0],"avahi-publish-service")
        self.assertIn("site_id=local-01",args)
        with self.assertRaises(ValueError):discovery.publish_arguments({"site_id":"bad\nid"},8443)
    def manifest(self,**changes):
        cfg={"version":1,"mode":"server","ui_argv":["/opt/culinaryos-app/bin/ui"],
             "backend_argv":["/opt/culinaryos-app/bin/backend"],"port":8443,
             "readiness_socket":"/run/culinaryos-app/ready.sock","tls_ca_file":"/etc/culinaryos/site-ca.crt"}
        cfg.update(changes)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"manifest.json";p.write_text(json.dumps(cfg))
            with patch("apphost.secure_file",side_effect=lambda p,*a,**k:Path(p)):
                return apphost.manifest(p)
    def test_manifest_requires_argument_arrays(self):
        with self.assertRaises(ValueError):self.manifest(backend_argv="exec backend")
    def test_manifest_readiness_path_restricted(self):
        with self.assertRaises(ValueError):self.manifest(readiness_socket="/tmp/forged.sock")
    def test_terminal_manifest_does_not_require_backend(self):
        cfg=self.manifest(mode="terminal",backend_argv=None)
        self.assertEqual(cfg["mode"],"terminal")
    def test_credential_names_and_paths_restricted(self):
        with self.assertRaises(ValueError):self.manifest(credentials={"bad\nName":"/etc/key"})
        with self.assertRaises(ValueError):self.manifest(credentials={"key":"/etc/key%h"})
if __name__=="__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
