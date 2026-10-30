"""Stage only source and distributable application artifacts for an isolated ISO builder."""
from pathlib import Path
import argparse,hashlib,json,shutil,tarfile
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'MesaNexoNativo'
parser=argparse.ArgumentParser();parser.add_argument('--revision',type=int,required=True);parser.add_argument('--license-server',required=True);args=parser.parse_args()
if not 1<=args.revision<=99:raise SystemExit('Invalid revision')
if not args.license_server.startswith('https://'):raise SystemExit('--license-server must be HTTPS')
stage=ROOT/f'build/appliance-input-r{args.revision}'
archive=ROOT/f'build/appliance-input-r{args.revision}.tar.gz'
if stage.exists() or archive.exists():raise SystemExit('Do not overwrite a staged input')
stage.mkdir()

def copy(source,target):
    source=Path(source);target=stage/target
    if source.is_symlink():raise ValueError('No symlinks in input')
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)

def tree(source,target):
    for path in sorted(source.rglob('*')):
        if path.is_symlink():raise ValueError('No symlinks in input')
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
            copy(path,Path(target)/path.relative_to(source))

for folder in ('config','os','scripts','tests','docs'):
    tree(ROOT/folder,Path('CulinaryOS')/folder)
for name in ('README.md','VERSION'):copy(ROOT/name,Path('CulinaryOS')/name)
for name in ('Cargo.toml','Cargo.lock','build.rs','tauri.conf.json','tauri.linux.conf.json'):
    copy(APP/'src/MesaNexo.Web/src-tauri'/name,Path('application/client-source/src-tauri')/name)
for folder in ('src','icons','capabilities'):
    tree(APP/'src/MesaNexo.Web/src-tauri'/folder,Path('application/client-source/src-tauri')/folder)
tree(APP/'src/MesaNexo.Web/dist','application/client-source/dist')
for folder in ('backend','bridge'):
    for path in (APP/'artifacts/culinaryos-linux'/folder).iterdir():
        if path.is_file() and path.suffix!='.pdb':copy(path,Path('application/payload')/folder/path.name)
copy(APP/'artifacts/culinaryos-linux/rustup-init','application/toolchain/rustup-init')
tree(APP/'deploy/culinaryos','application/deploy/culinaryos')
(stage/'application/deploy/culinaryos/license-server.txt').write_text(args.license_server.rstrip('/')+'\n',encoding='ascii',newline='\n')
copy(APP/'branding/icons/icon-256.png','application/branding/icon-256.png')
for path in (stage/'application/payload/backend/MesaNexo.Api',stage/'application/payload/bridge/culinary-bridge'):
    assert path.read_bytes()[:4]==b'\x7fELF'
lines=[]
for p in sorted(stage.rglob('*')):
    if p.is_file():lines.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(stage).as_posix())
(stage/'SHA256SUMS').write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')
with tarfile.open(archive,'w:gz',compresslevel=1) as out:
    for p in sorted(stage.rglob('*')):
        if p.is_file():out.add(p,arcname=p.relative_to(stage).as_posix(),recursive=False)
print(json.dumps({'archive':str(archive),'files':len(lines),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'excludes':['VM disks','build credentials','operational state','site identities','private keys','development caches']},indent=2))
