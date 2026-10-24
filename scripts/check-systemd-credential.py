"""Comprueba la credencial real sin imprimirla ni abrir SQLite."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location("culinaryos_checked_crypto",Path(__file__).with_name("securedata.py"))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.Keyring.load_systemd_credential()
print("Credencial systemd aceptada con el usuario del almacén.")
