import sys
sys.dont_write_bytecode=True
from pathlib import Path
import copy
import json
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"os/overlay/usr/local/lib/culinaryos"))
import site as builtin_site
import importlib.util
spec=importlib.util.spec_from_file_location("culinary_site",Path(__file__).resolve().parents[1]/"os/overlay/usr/local/lib/culinaryos/site.py")
site=importlib.util.module_from_spec(spec);spec.loader.exec_module(site)
import lan
ROOT=Path(__file__).resolve().parents[1]
def plan():return json.loads((ROOT/"config/network/site-plan.json").read_text())
def evidence(**kw):
    e=dict(configured=True,role="meseros",link=True,address=True,server=True,name=True,
           gateway_configured=True,gateway=True,application_configured=False,
           internet_configured=False)
    e.update(kw);return e
def row(e,code):return next(x for x in lan.evaluate(e) if x["id"]=="COS-LAN-"+code)
class NetworkTests(unittest.TestCase):
    def test_unique_manual_profiles(self):
        p=plan()
        for node in p["nodes"]:
            files=site.render(p,node["name"],"enp1s0")
            self.assertIn("method=manual",files["connection.nmconnection"])
            self.assertIn("autoconnect=false",files["connection.nmconnection"])
            self.assertIn(node["address"]+"/24",files["connection.nmconnection"])
            self.assertIsNone(json.loads(files["site.json"])["application"])
    def test_server_ports_closed_except_time(self):
        files=site.render(plan(),"servidor-01","enp1s0")
        self.assertIn('iifname "enp1s0" ip saddr 10.77.0.0/24 udp dport 123 accept',files["nftables.conf"])
        self.assertNotIn("elements =",files["nftables.conf"])
        self.assertNotIn("dport 22 accept",files["nftables.conf"])
    def test_terminal_has_no_inbound_time(self):
        self.assertNotIn("dport 123",site.render(plan(),"meseros-01","wlp1s0","wifi","CulinaryOperativa")["nftables.conf"])
    def test_wifi_has_no_secret(self):
        files=site.render(plan(),"meseros-01","wlp1s0","wifi","CulinaryOperativa")
        self.assertIn("psk-flags=2",files["connection.nmconnection"])
        self.assertNotIn("psk=",files["connection.nmconnection"])
    def test_server_requires_ethernet(self):
        with self.assertRaises(ValueError):site.render(plan(),"servidor-01","wlp1s0","wifi","Operativa")
    def test_reject_duplicate_address(self):
        p=plan();p["nodes"][1]["address"]=p["nodes"][0]["address"]
        with self.assertRaises(ValueError):site.validate(p)
    def test_reject_invalid_network_and_gateway(self):
        for field,value in [("network","8.8.8.0/24"),("gateway","10.78.0.1"),("gateway","10.77.0.10")]:
            p=plan();p[field]=value
            with self.assertRaises(ValueError):site.validate(p)
    def test_reject_config_injection(self):
        for interface in ("enp1s0\n[evil]","x; accept",'-bad'):
            with self.assertRaises(ValueError):site.render(plan(),"servidor-01",interface)
        with self.assertRaises(ValueError):site.render(plan(),"meseros-01","wlp1s0","wifi","a\n[evil]")
    def test_refuse_application_opening(self):
        p=plan();p["application_ports"]=[8443]
        with self.assertRaises(ValueError):site.render(p,"servidor-01","enp1s0")
    def test_no_gateway_still_local(self):
        p=plan();p["gateway"]=None
        files=site.render(p,"meseros-01","enp1s0")
        self.assertIn("never-default=true",files["connection.nmconnection"])
        self.assertEqual(json.loads(files["site.json"])["server_address"],"10.77.0.10")
    def test_chrony_internet_time_is_authenticated(self):
        server=site.render(plan(),"servidor-01","enp1s0")["chrony.conf"]
        self.assertIn("server time.cloudflare.com iburst nts",server)
        self.assertIn("local stratum 10",server)
        self.assertIn("makestep 1.0 -1",server)
        terminal=site.render(plan(),"meseros-01","enp1s0")["chrony.conf"]
        self.assertIn("server 10.77.0.10 iburst",terminal)
        self.assertNotIn("nts",terminal)
        for conf in (server,terminal,(ROOT/"os/overlay/etc/chrony/chrony.conf").read_text(encoding="utf-8")):
            self.assertNotIn("pool ",conf)
            self.assertNotIn("debian.org",conf)
        for line in server.splitlines():
            if line.startswith("server "):self.assertTrue(line.endswith(" nts"))
    def test_internet_down_server_reachable(self):
        r=row(evidence(internet_configured=True,internet=False),"INTERNET")
        self.assertEqual(r["gravedad"],"aviso")
        self.assertIn("servidor sigue accesible",r["mensaje"])
        self.assertEqual(row(evidence(),"SERVER")["gravedad"],"correcto")
    def test_server_unreachable_is_not_proven_power_failure(self):
        r=row(evidence(server=False),"SERVER")
        self.assertIn("firewall",r["mensaje"])
        self.assertNotIn("apagado",r["mensaje"])
    def test_link_failure_does_not_blame_internet(self):
        e=evidence(link=False,internet_configured=True,internet=False,server=False)
        self.assertEqual(row(e,"INTERNET")["gravedad"],"desconocido")
        self.assertEqual(row(e,"SERVER")["gravedad"],"desconocido")
    def test_bad_name_keeps_server_evidence(self):
        e=evidence(name=False)
        self.assertEqual(row(e,"NAME")["gravedad"],"aviso")
        self.assertEqual(row(e,"SERVER")["gravedad"],"correcto")
    def test_application_absence_explicit(self):
        self.assertEqual(row(evidence(),"SERVICE")["gravedad"],"no_aplica")
    def test_tls_failure_is_separate(self):
        e=evidence(application_configured=True,service_tcp=True,tls=False)
        self.assertEqual(row(e,"SERVER")["gravedad"],"correcto")
        self.assertEqual(row(e,"TLS")["gravedad"],"aviso")
    def test_no_external_probe_by_default(self):
        cfg=json.loads(site.render(plan(),"meseros-01","enp1s0")["site.json"])
        def localrun(args,timeout=2):
            if args[0]=="ip":return '[{"flags":["LOWER_UP"],"addr_info":[{"local":"10.77.0.101"}]}]'
            return "10.77.0.10 STREAM culinaryos.internal"
        with patch("lan.run",side_effect=localrun),patch("lan.ping",return_value=True),patch("lan.tcp") as tcp:
            lan.collect(cfg)
            tcp.assert_not_called()
    def test_public_server_cannot_be_labeled_internal(self):
        cfg=json.loads(site.render(plan(),"meseros-01","enp1s0")["site.json"])
        cfg["server_address"]="8.8.8.8"
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"site.json";p.write_text(json.dumps(cfg))
            with patch("lan.collect") as collect:
                self.assertEqual(lan.from_file(p)[0]["id"],"COS-LAN-CONFIG")
                collect.assert_not_called()
    def test_alert_schema(self):
        for r in lan.evaluate(evidence()):
            self.assertEqual(set(r),{"id","parte","gravedad","mensaje","accion"})
    def test_invalid_site_never_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"site.json";p.write_text('{"enabled":true}')
            self.assertEqual(lan.from_file(p)[0]["id"],"COS-LAN-CONFIG")
if __name__=="__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
