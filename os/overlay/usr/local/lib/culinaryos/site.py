#!/usr/bin/python3
"""Genera una carpeta de despliegue revisable. No cambia la red ni abre puertos."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import uuid

# Authenticated internet time (NTS): licences reject a clock set back, so the LAN must not be able to fake it.
# Certificate dates are not checked while unsynchronised, otherwise a clock far behind could never recover.
INTERNET_TIME=("server time.cloudflare.com iburst nts\nserver nts.netnod.se iburst nts\n"
               "nocerttimecheck 1\nntsdumpdir /var/lib/chrony\n")

def hostname(value):
    if not isinstance(value,str) or len(value)>253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",x) for x in value.split(".")):
        raise ValueError("Nombre DNS no válido")
    return value

def validate(plan):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}",plan["site_id"]):
        raise ValueError("Identificador de sitio no válido")
    net=ipaddress.ip_network(plan["network"],strict=True)
    private=[ipaddress.ip_network(x) for x in ("10.0.0.0/8","172.16.0.0/12","192.168.0.0/16")]
    if net.version!=4 or not any(net.subnet_of(x) for x in private) or not 16<=net.prefixlen<=28:
        raise ValueError("Use una LAN RFC1918 /16 a /28")
    def address(value):
        ip=ipaddress.ip_address(value)
        if ip not in net or ip in (net.network_address,net.broadcast_address):
            raise ValueError("Dirección fuera de la LAN o reservada")
        return str(ip)
    gateway=address(plan["gateway"]) if plan.get("gateway") else None
    hostname(plan["server_name"])
    if not plan["server_name"].endswith(".internal"):
        raise ValueError("El plan usa un nombre privado .internal")
    mdns=plan.get("mdns_name","servidor-restaurante")
    hostname(mdns)
    if "." in mdns:raise ValueError("Nombre mDNS sin dominio")
    seen=set();names=set();server=[]
    for node in plan["nodes"]:
        name=hostname(node["name"])
        if "." in name or name in names:
            raise ValueError("Nombre de nodo duplicado o no válido")
        names.add(name)
        ip=address(node["address"])
        if ip in seen or ip==gateway:
            raise ValueError("Dirección duplicada o igual a gateway")
        seen.add(ip)
        if node["role"] not in ("servidor","meseros","cocina","gerente"):
            raise ValueError("Rol no válido")
        if node["role"]=="servidor":server.append(node["name"])
    if server!=[plan["server_node"]]:
        raise ValueError("Debe existir exactamente un servidor")
    if not isinstance(plan["local_time"],bool):
        raise ValueError("local_time debe ser booleano")
    ports=plan.get("application_ports",[])
    if len(ports)>8 or len(set(ports))!=len(ports) or any(type(p) is not int or not 1024<=p<=65535 for p in ports):
        raise ValueError("Puertos de aplicación explícitos 1024-65535, sin duplicados")
    probes=plan.get("internet_probes",[])
    if len(probes)>2:
        raise ValueError("Máximo dos sondas externas")
    for probe in probes:
        ip=ipaddress.ip_address(probe["address"])
        if not ip.is_global or type(probe["port"]) is not int or not 1<=probe["port"]<=65535:
            raise ValueError("Sonda externa requiere IP global y puerto válido")
    return plan

def render(plan,node_name,interface,medium="ethernet",ssid=None):
    validate(plan)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,14}",interface):
        raise ValueError("Nombre de interfaz no válido")
    node=next((n for n in plan["nodes"] if n["name"]==node_name),None)
    if node is None:raise ValueError("Nodo no registrado")
    if medium not in ("ethernet","wifi"):raise ValueError("Medio no válido")
    if node["role"]=="servidor" and medium!="ethernet":
        raise ValueError("Servidor previsto por Ethernet")
    if medium=="wifi" and (not isinstance(ssid,str) or not re.fullmatch(r"[A-Za-z0-9 ._-]{1,32}",ssid)):
        raise ValueError("SSID requerido; use 1-32 caracteres simples")
    net=ipaddress.ip_network(plan["network"])
    server=next(n for n in plan["nodes"] if n["name"]==plan["server_node"])
    con="culinaryos-"+plan["site_id"]+"-"+node_name+"-"+medium
    uid=str(uuid.uuid5(uuid.NAMESPACE_DNS,con+"."+interface))
    connection=f"[connection]\nid={con}\nuuid={uid}\ntype={medium}\ninterface-name={interface}\nautoconnect=false\n\n"
    if medium=="wifi":
        connection+=f"[wifi]\nmode=infrastructure\nssid={ssid}\n\n[wifi-security]\nkey-mgmt=wpa-psk\nproto=rsn;\npairwise=ccmp;\ngroup=ccmp;\npsk-flags=2\n\n"
    else:
        connection+="[ethernet]\n\n"
    gateway=plan.get("gateway")
    connection+=f"[ipv4]\nmethod=manual\naddress1={node['address']}/{net.prefixlen}"+(f",{gateway}" if gateway else "")+"\nignore-auto-dns=true\n"
    # Hosts administrado evita depender de DNS del ISP/router para el servidor.
    if gateway:connection+=f"dns={gateway};\n"
    else:connection+="never-default=true\n"
    connection+="\n[ipv6]\nmethod=link-local\nnever-default=true\n\n[proxy]\n"
    ports=plan.get("application_ports",[])
    if ports:
        raise ValueError("Aplicación ausente: no habilitar application_ports en esta etapa")
    nft="""#!/usr/sbin/nft -f
flush ruleset
table inet culinaryos {
    set application_ports {
        type inet_service;
    }
    chain input {
        type filter hook input priority filter; policy drop;
        iifname "lo" accept
        ct state invalid drop
        ct state established,related accept
        meta l4proto { icmp, ipv6-icmp } accept
        udp sport 67 udp dport 68 accept
        udp sport 547 udp dport 546 accept
"""
    nft+=f'        iifname "{interface}" ip saddr {net} ip ttl 255 udp dport 5353 accept\n'
    nft+=f'        iifname "{interface}" ip6 saddr fe80::/10 ip6 hoplimit 255 udp dport 5353 accept\n'
    if node["role"]=="servidor":
        nft+=f'        iifname "{interface}" ip saddr {net} tcp dport @application_ports accept\n'
        if plan["local_time"]:
            nft+=f'        iifname "{interface}" ip saddr {net} udp dport 123 accept\n'
    nft+='''        limit rate 4/second burst 8 packets log prefix "CulinaryOs drop: " level info
    }
    chain forward {
        type filter hook forward priority filter; policy drop;
    }
    chain output {
        type filter hook output priority filter; policy accept;
    }
}
'''
    site={"enabled":True,"site_id":plan["site_id"],"node":node_name,"role":node["role"],
          "interface":interface,"network":plan["network"],"expected_address":node["address"],
          "server_address":server["address"],"server_name":plan["server_name"],
          "gateway":gateway,"mdns_name":plan.get("mdns_name","servidor-restaurante")+".local",
          "medium":medium,"ssid":ssid,"internet_probes":plan.get("internet_probes",[]),
          "application":None}
    chrony="driftfile /var/lib/chrony/chrony.drift\nrtcsync\nmakestep 1.0 -1\ncmdport 0\n"
    if plan["local_time"]:
        if node["role"]=="servidor":
            chrony+=INTERNET_TIME+f"local stratum 10\nallow {net}\n"
        else:
            chrony+=f"server {server['address']} iburst maxpoll 6\n"
    else:
        chrony+=INTERNET_TIME+"port 0\n"
    mdns_host=plan.get("mdns_name","servidor-restaurante") if node["role"]=="servidor" else node_name
    avahi=f"[server]\nhost-name={mdns_host}\ndomain-name=local\nallow-interfaces={interface}\nuse-ipv4=yes\nuse-ipv6=yes\nallow-point-to-point=no\nratelimit-interval-usec=1000000\nratelimit-burst=20\n\n[wide-area]\nenable-wide-area=no\n\n[publish]\ndisable-publishing={'no' if node['role']=='servidor' else 'yes'}\ndisable-user-service-publishing={'no' if node['role']=='servidor' else 'yes'}\npublish-hinfo=no\npublish-workstation=no\npublish-domain=no\n\n[reflector]\nenable-reflector=no\n"
    return {"connection.nmconnection":connection,"avahi-daemon.conf":avahi,
            "site-plan.json":json.dumps(plan,ensure_ascii=False,indent=2)+"\n","nftables.conf":nft,
            "site.json":json.dumps(site,ensure_ascii=False,indent=2)+"\n",
            "hosts.fragment":f"{server['address']} {plan['server_name']} {server['name']}\n",
            "chrony.conf":chrony,
            "DEPLOY.txt":f"Nodo: {node_name}\nRol de ubicación: {node['role']}\nInterfaz: {interface}\nIP: {node['address']}/{net.prefixlen}\nConexión: {con}\nNo aplicado. autoconnect=false. Consulte docs/RED-LOCAL.md y CERTIFICADOS-LOCALES.md.\n"}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",required=True);p.add_argument("--node",required=True)
    p.add_argument("--interface",required=True)
    p.add_argument("--medium",choices=("ethernet","wifi"),default="ethernet")
    p.add_argument("--ssid");p.add_argument("--output",required=True)
    args=p.parse_args()
    plan=json.loads(Path(args.plan).read_text(encoding="utf-8"))
    files=render(plan,args.node,args.interface,args.medium,args.ssid)
    out=Path(args.output)
    out.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name,content in files.items():
        file=out/name
        with open(file,"x",encoding="utf-8",newline="\n") as f:f.write(content)
        os.chmod(file,0o600)
    print("Carpeta preparada; revise antes de instalar:",out)
if __name__=="__main__":
    main()
