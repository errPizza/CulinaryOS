#!/usr/bin/python3
"""DNS-SD: encontrar candidatos no equivale a confiar en ellos."""
import argparse
import json
import re
import subprocess

SERVICE="_culinaryos._tcp"
def publish_arguments(site,port):
    if type(port) is not int or not 1024<=port<=65535:raise ValueError("Puerto inválido")
    if not re.fullmatch(r"[a-z0-9-]{1,32}",site["site_id"]):raise ValueError("Sitio inválido")
    # Sólo metadatos públicos. El cliente debe tener CA/identidad aprovisionadas.
    return ["avahi-publish-service","--service","CulinaryOs "+site["site_id"],SERVICE,str(port),
            "protocol=1","site_id="+site["site_id"],"tls_name="+site["server_name"]]
def unescape(value):
    return re.sub(r"\\([0-9]{3})",lambda m:chr(int(m.group(1))),value)
def parse(output,interface=None):
    result=[]
    for line in output.splitlines():
        fields=line.split(";")
        if len(fields)<10 or fields[0]!="=" or fields[4]!=SERVICE:continue
        if interface and fields[1]!=interface:continue
        try:port=int(fields[8])
        except ValueError:continue
        if not 1024<=port<=65535:continue
        result.append({"interface":fields[1],"family":fields[2],"name":unescape(fields[3]),
                       "hostname":fields[6],"address":fields[7],"port":port,
                       "metadata":fields[9:],"trusted":False})
    return result
def browse(interface=None):
    p=subprocess.run(["avahi-browse","--resolve","--terminate","--parsable",SERVICE],
                     capture_output=True,text=True,timeout=8,check=True)
    return parse(p.stdout,interface)
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--interface");args=parser.parse_args()
    print(json.dumps(browse(args.interface),ensure_ascii=False,indent=2))

def verify_candidate(candidate,config):
    import ipaddress
    from lan import tls
    network=ipaddress.ip_network(config["network"],strict=True)
    try:
        address=ipaddress.ip_address(candidate["address"])
        if address.version!=4 or address not in network or candidate["port"]!=config["port"]:
            return False
        if candidate["interface"]!=config["interface"]:return False
        # Ignorar TXT como fuente de confianza: identidad y CA vienen del aprovisionamiento.
        return tls(str(address),candidate["port"],config["server_name"],config["ca_file"]) is True
    except (KeyError,ValueError,OSError):return False

if __name__=="__main__":main()
