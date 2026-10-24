"""Ajuste acotado del generador Debian de entradas Linux de GRUB."""
import argparse
import os
from pathlib import Path
import re
import stat
import tempfile

ASSIGNMENT = re.compile(r'^quiet_boot=(?:"[01]"|\'[01]\'|[01])[ \t]*$', re.MULTILINE)

def quiet_generator(text):
    matches = list(ASSIGNMENT.finditer(text))
    if len(matches) != 1:
        raise ValueError("10_linux no tiene una asignación quiet_boot compatible y única; no se modifica.")
    return ASSIGNMENT.sub('quiet_boot="1"', text, count=1)

def configure_generator(path=Path("/etc/grub.d/10_linux"), check=False):
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
        raise ValueError("El generador debe ser un archivo regular de root sin escritura para otros.")
    original = path.read_text(encoding="utf-8")
    updated = quiet_generator(original)
    if check or updated == original:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(updated)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), stat.S_IMODE(metadata.st_mode))
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check-generator", "quiet-generator"))
    args = parser.parse_args()
    if args.command == "quiet-generator" and os.geteuid() != 0:
        parser.error("Se requiere root.")
    try:
        configure_generator(check=args.command == "check-generator")
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + "\n")
    print("Generador Linux de GRUB compatible." if args.command == "check-generator"
          else "Mensajes informativos de la entrada normal de GRUB ocultos.")

if __name__ == "__main__":
    main()
