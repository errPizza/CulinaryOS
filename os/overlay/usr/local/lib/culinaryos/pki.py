#!/usr/bin/python3
"""CA de sitio offline, CSR y certificados de servidor. Nunca se ejecuta al construir."""
import argparse
from contextlib import contextmanager
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import shutil
import subprocess

OPENSSL=os.environ.get("CULINARYOS_OPENSSL","openssl")
def execute(args):
    # Contraseñas solicitadas por OpenSSL en terminal; sin argumentos ni variables de contraseña.
    subprocess.run([OPENSSL,*map(str,args)],check=True,timeout=180)

def safe_path(directory):
    path=Path(directory).resolve()
    if any(c in path.as_posix() for c in ('"',"$","\n","\r")):
        raise ValueError("Ruta no compatible con configuración OpenSSL")
    return path

def dns_name(value):
    if not isinstance(value,str) or len(value)>253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",x) for x in value.split(".")):
        raise ValueError("Nombre DNS no válido")
    return value

def config_text(directory):
    return f"""[ca]
default_ca = site_ca
[site_ca]
dir = "{safe_path(directory).as_posix()}"
database = $dir/index.txt
new_certs_dir = $dir/newcerts
certificate = $dir/ca.crt
private_key = $dir/ca.key
serial = $dir/serial
crlnumber = $dir/crlnumber
default_md = sha256
default_days = 90
default_crl_days = 7
policy = policy_server
unique_subject = no
copy_extensions = none
[policy_server]
commonName = supplied
[req]
distinguished_name = root_name
prompt = no
x509_extensions = v3_ca
[root_name]
CN = CulinaryOs Local Root
[v3_ca]
basicConstraints = critical,CA:true,pathlen:0
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always
"""

@contextmanager
def ca_lock(directory):
    lock=Path(directory)/".lock"
    lock.mkdir(mode=0o700,exist_ok=False)
    try:yield
    finally:lock.rmdir()

def init_ca(directory):
    directory=safe_path(directory)
    os.umask(0o077)
    directory.mkdir(parents=True,mode=0o700,exist_ok=False)
    (directory/"newcerts").mkdir(mode=0o700)
    for name,text in {"ca.conf":config_text(directory),"index.txt":"","serial":"1000\n","crlnumber":"1000\n"}.items():
        (directory/name).write_text(text,encoding="utf-8")
    execute(["genpkey","-algorithm","EC","-pkeyopt","ec_paramgen_curve:P-256","-aes-256-cbc","-out",directory/"ca.key"])
    os.chmod(directory/"ca.key",0o600)
    execute(["req","-new","-x509","-sha256","-days","3650","-key",directory/"ca.key",
             "-out",directory/"ca.crt","-config",directory/"ca.conf"])
    return directory/"ca.crt"

def request(directory,name,address):
    dns_name(name);ipaddress.IPv4Address(address)
    directory=safe_path(directory)
    os.umask(0o077)
    directory.mkdir(parents=True,mode=0o700,exist_ok=False)
    execute(["req","-new","-newkey","ec","-pkeyopt","ec_paramgen_curve:P-256","-noenc",
             "-keyout",directory/"server.key","-out",directory/"server.csr",
             "-subj","/CN="+name,"-addext",f"subjectAltName=DNS:{name},IP:{address}"])
    os.chmod(directory/"server.key",0o600)
    return directory/"server.csr"

def issue(directory,csr,output,name,address,days=90,purpose="server"):
    if purpose not in ("server","client"):raise ValueError("Propósito de certificado no válido")
    dns_name(name);ipaddress.IPv4Address(address)
    if not 1<=days<=397:raise ValueError("Vigencia permitida: 1-397 días")
    directory=safe_path(directory);csr=Path(csr).resolve();output=Path(output).resolve()
    if output.exists():raise FileExistsError(output)
    # Extensiones autorizadas, sin copiar privilegios ni SAN arbitrarios del CSR.
    ext=directory/"leaf-extensions.conf"
    with ca_lock(directory):
        ext.write_text(f"[server]\nbasicConstraints=critical,CA:false\nkeyUsage=critical,digitalSignature\nextendedKeyUsage={"serverAuth" if purpose=="server" else "clientAuth"}\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\nsubjectAltName=DNS:{name},IP:{address}\n",encoding="utf-8")
        try:
            execute(["ca","-batch","-notext","-config",directory/"ca.conf","-extensions","server",
                     "-extfile",ext,"-days",str(days),"-in",csr,"-out",output])
        finally:ext.unlink(missing_ok=True)
    return output

def revoke(directory,certificate):
    directory=safe_path(directory)
    with ca_lock(directory):
        execute(["ca","-config",directory/"ca.conf","-revoke",Path(certificate).resolve(),"-crl_reason","keyCompromise"])

def crl(directory,output):
    directory=safe_path(directory);output=Path(output).resolve()
    if output.exists():raise FileExistsError(output)
    with ca_lock(directory):
        execute(["ca","-config",directory/"ca.conf","-gencrl","-out",output])

def fingerprint(certificate):
    # PEM normalizado a DER; se rechazan bundles para importar exactamente una raíz.
    import ssl
    pem=Path(certificate).read_text(encoding="ascii")
    if pem.count("-----BEGIN CERTIFICATE-----")!=1 or pem.count("-----END CERTIFICATE-----")!=1:
        raise ValueError("Se requiere exactamente un certificado")
    der=ssl.PEM_cert_to_DER_cert(pem)
    return hashlib.sha256(der).hexdigest()

def trust(certificate,expected):
    actual=fingerprint(certificate)
    if not re.fullmatch(r"[0-9a-fA-F:]{64,95}",expected) or actual!=expected.replace(":","").lower():
        raise ValueError("Huella de CA no coincide con la verificada por canal administrativo")
    if os.name!="posix" or not hasattr(os,"geteuid") or os.geteuid()!=0:
        raise PermissionError("Importar confianza sólo como root en el invitado Debian")
    p=subprocess.run([OPENSSL,"x509","-in",str(certificate),"-noout","-ext","basicConstraints"],
                     capture_output=True,text=True,check=True,timeout=5)
    if "CA:TRUE" not in p.stdout:raise ValueError("No es una CA")
    execute(["verify","-CAfile",certificate,certificate])
    execute(["x509","-in",certificate,"-noout","-checkend","604800"])
    dest=Path("/usr/local/share/ca-certificates")/("culinaryos-"+actual[:16]+".crt")
    if dest.exists():
        if fingerprint(dest)!=actual:raise ValueError("Certificado existente diferente")
    else:
        with open(dest,"x",encoding="ascii") as f:f.write(Path(certificate).read_text(encoding="ascii"))
        os.chmod(dest,0o644)
    subprocess.run(["update-ca-certificates"],check=True,timeout=60)
    return dest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("init-ca");p.add_argument("--directory",required=True)
    p=sub.add_parser("request")
    p.add_argument("--directory",required=True);p.add_argument("--name",required=True);p.add_argument("--address",required=True)
    p=sub.add_parser("issue")
    p.add_argument("--directory",required=True);p.add_argument("--csr",required=True)
    p.add_argument("--output",required=True);p.add_argument("--name",required=True);p.add_argument("--address",required=True)
    p.add_argument("--days",type=int,default=90)
    p.add_argument("--purpose",choices=("server","client"),default="server")
    for cmd in ("revoke","crl"):
        p=sub.add_parser(cmd);p.add_argument("--directory",required=True)
        p.add_argument("--certificate" if cmd=="revoke" else "--output",required=True)
    p=sub.add_parser("fingerprint");p.add_argument("--certificate",required=True)
    p=sub.add_parser("trust");p.add_argument("--certificate",required=True);p.add_argument("--fingerprint",required=True)
    args=parser.parse_args();c=args.command
    if c=="init-ca":init_ca(args.directory)
    elif c=="request":request(args.directory,args.name,args.address)
    elif c=="issue":issue(args.directory,args.csr,args.output,args.name,args.address,args.days,args.purpose)
    elif c=="revoke":revoke(args.directory,args.certificate)
    elif c=="crl":crl(args.directory,args.output)
    elif c=="fingerprint":print(fingerprint(args.certificate))
    elif c=="trust":trust(args.certificate,args.fingerprint)
if __name__=="__main__":
    main()
