#!/usr/bin/python3
"""Inspect the actual installer ISO and its SquashFS payload without booting it."""
import argparse,hashlib,json,re,subprocess,tempfile
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('iso',type=Path);parser.add_argument('--application',required=True,type=Path);parser.add_argument('--report',required=True,type=Path);parser.add_argument('--firstboot-source',type=Path);args=parser.parse_args()
iso=args.iso.resolve(strict=True)
def call(*command):return subprocess.check_output(list(map(str,command)),stderr=subprocess.DEVNULL)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
report={'iso':iso.name,'bytes':iso.stat().st_size,'sha256':sha(iso)}
boot=call('xorriso','-indev',iso,'-report_el_torito','plain').decode()
if not re.search(r'BIOS',boot) or not re.search(r'UEFI',boot):raise ValueError('Missing BIOS / UEFI boot entry')
report['bios']=True;report['uefi']=True
with tempfile.TemporaryDirectory(prefix='culinary-iso-audit-',dir=iso.parent) as tmp:
    tmp=Path(tmp)
    for source,name in [('/live/filesystem.squashfs','root.squashfs'),('/boot/grub/grub.cfg','grub.cfg'),('/isolinux/install.cfg','install.cfg'),('/install/preseed.cfg','preseed.cfg')]:
        call('xorriso','-osirrox','on','-indev',iso,'-extract',source,tmp/name)
    for name in ('grub.cfg','install.cfg'):
        text=(tmp/name).read_text()
        if '@KERNEL' in text or '@INITRD' in text:raise ValueError('Unexpanded installer boot entry')
        if 'file=/cdrom/install/preseed.cfg' not in text:raise ValueError('Wrong preseed boot path')
    seed=(tmp/'preseed.cfg').read_text()
    if 'partman-auto/disk' in seed:raise ValueError('Installer selects a disk without asking')
    if re.search(r'^\s*d-i\s+passwd/user-password\s+password\b',seed,re.M):raise ValueError('Plaintext account password in preseed')
    if re.search(r'^\s*d-i\s+passwd/root-password\b',seed,re.M):raise ValueError('Root password in preseed')
    if not re.search(r'^\s*d-i\s+passwd/user-password-crypted\s+password\s+\$6\$',seed,re.M):raise ValueError('Missing SHA-512 crypt password')
    if not re.search(r'^\s*d-i\s+partman-auto/method\s+string\s+regular\s*$',seed,re.M):raise ValueError('Missing guided whole-disk partitioning')
    if not re.search(r'^\s*d-i\s+partman-auto/choose_recipe\s+select\s+atomic\s*$',seed,re.M):raise ValueError('Missing atomic partition recipe')
    if 'in-target /usr/local/sbin/culinaryos-installer-finish' not in seed:raise ValueError('Missing installer completion')
    sq=tmp/'root.squashfs'
    report['rootfsSha256']=sha(sq)
    listing=call('unsquashfs','-ls',sq).decode()
    for forbidden in ('etc/culinaryos/site.json','etc/culinaryos/branch.json','etc/culinaryos/application.json','etc/culinaryos/secrets/branch.keys.json','var/lib/culinaryos-data/store.sqlite','var/lib/culinaryos/provisioned','root/qa-secret.json','usr/local/lib/culinaryos/qa-firstboot.py'):
        if 'squashfs-root/'+forbidden+'\n' in listing:raise ValueError('Operational/test state in ISO: '+forbidden)
    def cat(name):return call('unsquashfs','-cat',sq,name)
    if cat('etc/machine-id').strip():raise ValueError('Machine identity was not reset')
    passwd=cat('etc/passwd').decode()
    if any(int(row.split(':')[2])>=1000 and row.split(':')[0]!='nobody' for row in passwd.splitlines()):raise ValueError('Personal account present in ISO')
    hashes={}
    for name,source in [('opt/culinaryos-app/client/culinary-restaurant','payload/client/culinary-restaurant'),('opt/culinaryos-app/client/culinary-bridge','payload/client/culinary-bridge'),('opt/culinaryos-app/backend/MesaNexo.Api','payload/backend/MesaNexo.Api')]:
        value=cat(name)
        if value[:6]!=b'\x7fELF\x02\x01':raise ValueError('Not an ELF64 Linux executable: '+name)
        digest=hashlib.sha256(value).hexdigest()
        if digest!=sha(args.application/source):raise ValueError('Packaged executable mismatch: '+name)
        hashes[name]=digest
    firstboot=hashlib.sha256(cat('usr/local/lib/culinaryos/appliance.py')).hexdigest()
    if args.firstboot_source and firstboot!=sha(args.firstboot_source):raise ValueError('Firstboot source mismatch')
    report['firstbootSha256']=firstboot
    mouse=cat('opt/culinaryos-app/kiosk/openbox.xml').decode()
    if 'Left Middle Right' not in mouse or 'name="Focus"' not in mouse:raise ValueError('Missing mouse focus fix')
    config=json.loads(cat('etc/culinaryos/build.json'))
    if config.get('application_included') is not True or config.get('kiosk') is not True:raise ValueError('Not integrated kiosk image')
    report.update({'noPersonalAccounts':True,'noOperationalKeysOrData':True,'noAutomaticDiskErasure':True,'compiledExecutables':hashes,'kiosk':True,'installerPreseed':True})
args.report.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
