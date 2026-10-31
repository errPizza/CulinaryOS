import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"os/overlay/usr/local/lib/culinaryos"))
import unittest
from unittest.mock import patch
import subprocess
import health

def baseline():
    return dict(failed_services=0,network_up=True,route=True,dns_configured=False,
                disk_free_ratio=.5,root_readonly=False,permissions=True,
                mem_available_ratio=.6,memory_pressure=0,load_per_cpu=.2,
                journal_bytes=1024,kernel_errors=0,firewall=True,apt_age_hours=1,
                upgradable=0,reboot=False,certificates_configured=False,
                backup_enabled=False,maintenance=False)
def row(e,code):
    return next(x for x in health.evaluate(e) if x["id"]=="COS-"+code)
class DiagnosticsTests(unittest.TestCase):
    def test_baseline(self):
        self.assertFalse(any(x["gravedad"]=="critico" for x in health.evaluate(baseline())))
    def test_offline_remains_local(self):
        e=baseline(); e.update(network_up=False,route=False)
        self.assertEqual(row(e,"NETWORK")["gravedad"],"aviso")
        self.assertFalse(any(x["gravedad"]=="critico" for x in health.evaluate(e)))
    def test_low_disk_levels(self):
        for free,expected in [(.14,"aviso"),(.04,"critico"),(.15,"correcto")]:
            e=baseline();e["disk_free_ratio"]=free
            self.assertEqual(row(e,"DISK")["gravedad"],expected)
    def test_critical_indicators(self):
        for code,key,value in [("READONLY","root_readonly",True),("PERMISSIONS","permissions",False),("FIREWALL","firewall",False)]:
            with self.subTest(code=code):
                e=baseline();e[key]=value
                self.assertEqual(row(e,code)["gravedad"],"critico")
    def test_a_failing_disk_is_critical(self):
        e=baseline();e["smart_passed"]=False
        self.assertEqual(row(e,"SMART")["gravedad"],"critico")
        e["smart_passed"]=True
        self.assertEqual(row(e,"SMART")["gravedad"],"correcto")
    def test_temperature_levels(self):
        for degrees,expected in [(70,"correcto"),(85,"aviso"),(96,"critico")]:
            e=baseline();e["temperature"]=degrees
            self.assertEqual(row(e,"TEMPERATURE")["gravedad"],expected)
    def test_a_machine_without_sensors_is_not_an_alarm(self):
        for code in ("SMART","TEMPERATURE"):self.assertEqual(row(baseline(),code)["gravedad"],"no_aplica")
    def test_smartctl_reports_failure_through_an_error_exit(self):
        replies=[subprocess.CompletedProcess([],0,"/dev/sda disk\n/dev/sr0 rom\n/dev/sdb disk\n",""),
                 subprocess.CompletedProcess([],0,'{"smart_status":{"passed":true}}',""),
                 subprocess.CompletedProcess([],8,'{"smart_status":{"passed":false}}',"")]
        with patch("health.subprocess.run",side_effect=replies) as run:
            self.assertIs(health.disk_health(),False)
        self.assertEqual(run.call_count,3)
    def test_no_smart_answer_is_unknown(self):
        replies=[subprocess.CompletedProcess([],0,"/dev/vda disk\n",""),subprocess.CompletedProcess([],1,'{}',"")]
        with patch("health.subprocess.run",side_effect=replies):
            self.assertIsNone(health.disk_health())
    def test_failed_services(self):
        e=baseline();e["failed_services"]=2
        self.assertEqual(row(e,"SERVICES")["gravedad"],"aviso")
    def test_unknown_never_becomes_ok(self):
        for item in health.evaluate({}):
            self.assertIn(item["gravedad"],("desconocido","no_aplica"))
    def test_resource_pressure(self):
        e=baseline();e.update(mem_available_ratio=.03,memory_pressure=15,load_per_cpu=3,journal_bytes=300*1024*1024)
        for code in ("MEMORY","PRESSURE","LOAD","LOGS"):
            self.assertEqual(row(e,code)["gravedad"],"aviso")
    def test_dns_optional_and_failure(self):
        e=baseline()
        self.assertEqual(row(e,"DNS")["gravedad"],"no_aplica")
        e.update(dns_configured=True,dns=False)
        self.assertEqual(row(e,"DNS")["gravedad"],"aviso")
    def test_certificate_expiry(self):
        e=baseline();e.update(certificates_configured=True,certificates=False)
        self.assertEqual(row(e,"CERTIFICATES")["gravedad"],"aviso")
    def test_backup_unconfigured_explicit(self):
        self.assertIn("no hay protección",row(baseline(),"BACKUP")["mensaje"])
    def test_stale_failed_and_missing_backup(self):
        for age,failed in [(72,False),(1,True),(None,True)]:
            e=baseline();e.update(backup_enabled=True,backup_age_hours=age,backup_failed=failed)
            self.assertNotEqual(row(e,"BACKUP")["gravedad"],"correcto")
    def test_updates_reboot(self):
        e=baseline();e.update(apt_age_hours=200,upgradable=3,reboot=True)
        for code in ("UPDATES","PACKAGES","REBOOT"):
            self.assertEqual(row(e,code)["gravedad"],"aviso")
    def test_no_internal_data_public(self):
        e=baseline();e["internal_log"]="SECRET password trace address"
        self.assertNotIn("SECRET",str(health.evaluate(e)))
    def test_alert_contract(self):
        e=baseline();e.update(failed_services=1,permissions=False)
        for item in health.evaluate(e):
            self.assertEqual(set(item),{"id","parte","gravedad","mensaje","accion"})
            self.assertTrue(all(isinstance(x,str) and x for x in item.values()))
    def test_timeout_unknown(self):
        with patch("health.subprocess.run",side_effect=subprocess.TimeoutExpired("ip",3)):
            self.assertIsNone(health.run(["ip","link"]))
    def test_command_failure_unknown(self):
        with patch("health.subprocess.run",return_value=subprocess.CompletedProcess([],1,"","private")):
            self.assertIsNone(health.run(["systemctl"]))
if __name__=="__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
