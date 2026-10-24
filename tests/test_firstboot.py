"""Pruebas del flujo interactivo con comandos de cuentas simulados, sin privilegios."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = (r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else shutil.which("bash"))
SCRIPT = "os/overlay/usr/local/sbin/culinaryos-firstboot"

class FirstbootTests(unittest.TestCase):
    def run_shell(self, body, stdin="", marker=None):
        with tempfile.TemporaryDirectory(prefix="culinary-firstboot-") as temporary:
            state = Path(temporary)
            if marker is not None:
                (state / "setup-admin").write_bytes(marker.encode("utf-8"))
            result = subprocess.run(
                [BASH, "--noprofile", "--norc", "-c", 'source "$1"; shift; ' + body,
                 "firstboot-test", SCRIPT, state.as_posix()],
                cwd=ROOT, input=stdin.encode("utf-8"), capture_output=True, timeout=10)
            result.stdout = result.stdout.decode("utf-8")
            result.stderr = result.stderr.decode("utf-8")
            return result

    def test_password_mismatch_then_success(self):
        result = self.run_shell('calls=0; passwd(){ calls=$((calls+1)); (( calls >= 2 )); }; '
                                'set_account_password adminlocal; printf "CALLS=%s" "$calls"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CALLS=2", result.stdout)
        self.assertIn("no aparecen", result.stdout)

    def test_password_failure_is_bounded(self):
        result = self.run_shell('calls=0; passwd(){ calls=$((calls+1)); return 1; }; '
                                'if set_account_password adminlocal; then rc=0; else rc=$?; fi; '
                                'printf "CALLS=%s" "$calls"; exit "$rc"')
        self.assertEqual(result.returncode, 1)
        self.assertIn("CALLS=3", result.stdout)
        self.assertIn("Alta sin completar", result.stderr)

    def test_password_success_does_not_repeat(self):
        result = self.run_shell('calls=0; passwd(){ calls=$((calls+1)); return 0; }; '
                                'set_account_password operador; printf "CALLS=%s" "$calls"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CALLS=1", result.stdout)

    def test_existing_account_and_reserved_names_are_not_selected(self):
        result = self.run_shell('getent(){ [[ "$1" == passwd && "$2" == laboratorio ]]; }; '
                                'select_admin "$1"; printf "CHOSEN=%s" "$admin"',
                                stdin="root\noperador\nlaboratorio\nadminlocal\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CHOSEN=adminlocal", result.stdout)
        self.assertIn("La cuenta ya existe", result.stdout)

    def test_partial_setup_resumes_without_reading_new_name(self):
        result = self.run_shell('select_admin "$1"; printf "CHOSEN=%s" "$admin"',
                                marker="adminlocal\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Retomando", result.stdout)
        self.assertIn("CHOSEN=adminlocal", result.stdout)

    def test_bad_partial_setup_is_refused(self):
        result = self.run_shell('select_admin "$1"', marker="root\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Registro de alta no válido", result.stderr)

    def test_eof_does_not_loop_or_complete_setup(self):
        result = self.run_shell('select_admin "$1"')
        self.assertEqual(result.returncode, 1)
        self.assertIn("Entrada interrumpida", result.stderr)

if __name__ == "__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
