"""Verificaciones estáticas; no sustituyen nft, systemd ni una VM."""
import ast
import sys
sys.dont_write_bytecode=True
import json
import re
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class ProjectTests(unittest.TestCase):
    def test_target(self):
        cfg=json.loads((ROOT/"config/project.json").read_text())
        self.assertEqual((cfg["name"],cfg["distribution"],cfg["architecture"]),("CulinaryOs","trixie","amd64"))
        self.assertEqual(cfg["profiles"],["terminal","servidor","sucursal"])
        self.assertFalse(cfg["application_included"])
    def test_python_compiles(self):
        for p in list((ROOT/"os").rglob("*.py"))+list((ROOT/"tests").glob("*.py")):
            ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
    def test_linux_text_encoding(self):
        for base in ("os","scripts","config"):
            for p in (ROOT/base).rglob("*"):
                if p.is_file() and p.suffix!=".ps1":
                    raw=p.read_bytes()
                    if p.suffix==".png":
                        self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"),str(p))
                        continue
                    self.assertFalse(raw.startswith(b"\xef\xbb\xbf"),str(p))
                    self.assertNotIn(b"\r",raw,str(p))
    def test_no_keys_passwords(self):
        for p in (ROOT/"os").rglob("*"):
            if p.is_file():
                data=p.read_bytes()
                # The integrated first boot gives the kiosk account a random password
                # (secrets.token_urlsafe, checked in test_appliance); nothing else may set one.
                tokens=(b"NOPASSWD",) if p==ROOT/"os/appliance/usr/local/lib/culinaryos/appliance.py" else (b"NOPASSWD",b"chpasswd")
                for token in tokens:self.assertNotIn(token,data,str(p))
                self.assertIsNone(re.search(rb"-----BEGIN (?:[A-Z0-9 ]* )?PRIVATE KEY-----",data),str(p))
                self.assertNotIn(p.suffix,(".key",".csr",".p12",".sqlite",".db",".pyc"),str(p))
                self.assertNotIn("secrets",p.parts,str(p))
        for name in ("branch.json","application.json","application.server","application.registered"):
            self.assertFalse((ROOT/"os/overlay/etc/culinaryos"/name).exists())
    def test_no_application_payload(self):
        forbidden={"softwareprototipo","node_modules",".env","id_rsa","id_ed25519"}
        for p in (ROOT/"os").rglob("*"):
            self.assertFalse(any(part.lower() in forbidden for part in p.parts),str(p))
        build=(ROOT/"scripts/build.sh").read_text(encoding="utf-8")
        self.assertIn('cp -a "$project/os/overlay/."',build)
        self.assertNotIn('cp -a "$project/."',build)
    def test_no_installer(self):
        self.assertIn("--debian-installer none",(ROOT/"scripts/build.sh").read_text())
    def test_no_default_live_admin(self):
        build=(ROOT/"scripts/build.sh").read_text()
        self.assertIn("nocomponents=user-setup,sudo,polkit,lightdm",build)
        self.assertIn("live-config.noautologin",build)
    def test_dual_stack_firewall(self):
        rules=(ROOT/"os/overlay/etc/nftables.conf").read_text()
        self.assertIn("table inet culinaryos",rules)
        self.assertEqual(rules.count("policy drop;"),2)
        self.assertIn("ipv6-icmp",rules)
        self.assertNotIn("tcp dport 22 accept",rules)
    def test_health_independent_of_internet(self):
        unit=(ROOT/"os/overlay/etc/systemd/system/culinaryos-health.service").read_text()
        self.assertNotIn("network-online.target",unit)
        self.assertIn("ProtectSystem=strict",unit)
        self.assertIn("MemoryMax=",unit)
    def test_timer_bounded(self):
        self.assertIn("OnUnitInactiveSec=120s",(ROOT/"os/overlay/etc/systemd/system/culinaryos-health.timer").read_text())
    def test_boot_flags_preserve_options_and_are_idempotent(self):
        import os
        import shutil
        import subprocess
        bash = (r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else shutil.which("bash"))
        fragment = "os/overlay/etc/default/grub.d/60-culinaryos-splash.cfg"
        for options, expected in [("", ["quiet", "splash"]),
                                  ("root=UUID=abc quiet audit=1", ["root=UUID=abc", "quiet", "audit=1", "splash"]),
                                  ("quiet splash", ["quiet", "splash"]),
                                  ("quiet splash loglevel=7 systemd.show_status=1", ["quiet", "splash", "loglevel=7", "systemd.show_status=1"])]:
            with self.subTest(options=options):
                command = 'GRUB_CMDLINE_LINUX_DEFAULT=$2; . "$1"; . "$1"; printf "%s\\n" "$GRUB_CMDLINE_LINUX_DEFAULT" "$GRUB_GFXPAYLOAD_LINUX" "$GRUB_TIMEOUT_STYLE" "$GRUB_TIMEOUT"'
                result = subprocess.run([bash, "--noprofile", "--norc", "-c", command, "boot-test", fragment, options],
                                        cwd=ROOT, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                lines = result.stdout.splitlines()
                defaults = ([] if any(x.startswith("loglevel=") for x in expected) else ["loglevel=3"])
                defaults += ([] if any(x.startswith("systemd.show_status=") for x in expected) else ["systemd.show_status=error"])
                self.assertEqual(lines[0].split(), expected + defaults)
                self.assertEqual(lines[1:], ["keep", "hidden", "1"])
    def test_grub_generator_quiet_mode_preserves_loading_and_recovery_logic(self):
        import importlib.util
        path = ROOT/"os/overlay/usr/local/lib/culinaryos/bootconfig.py"
        spec = importlib.util.spec_from_file_location("bootconfig", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = '#!/bin/sh\nquiet_boot="0"\nif [ x"$quiet_boot" = x0 ] || [ x"$type" != xsimple ]; then\n  echo loading\nfi\nlinux /vmlinuz root=UUID=abc\ninitrd /initrd.img\n'
        expected = original.replace('quiet_boot="0"', 'quiet_boot="1"', 1)
        self.assertEqual(module.quiet_generator(original), expected)
        self.assertEqual(module.quiet_generator(expected), expected)

    def test_grub_generator_unknown_layout_is_refused(self):
        import importlib.util
        path = ROOT/"os/overlay/usr/local/lib/culinaryos/bootconfig.py"
        spec = importlib.util.spec_from_file_location("bootconfig", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for original in ('quiet_boot="auto"\n', 'echo unchanged\n',
                         'quiet_boot="0"\nquiet_boot="1"\n'):
            with self.subTest(original=original), self.assertRaises(ValueError):
                module.quiet_generator(original)

if __name__=="__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
