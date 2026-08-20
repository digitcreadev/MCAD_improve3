#!/usr/bin/env python3
import hashlib, sys, zipfile
from pathlib import Path
out=Path(sys.argv[2])
excluded={'SHA256SUMS.txt','MCAD_NH_R2_RESULTS.zip','MCAD_NH_R2_RESULTS_SHA256.txt'}
files=[p for p in sorted(out.rglob('*')) if p.is_file() and p.name not in excluded and p.as_posix().split('/')[-2:] != ['logs','package.log']]
lines=[f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out).as_posix()}' for p in files]
(out/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
zip_path=out/'MCAD_NH_R2_RESULTS.zip'; epoch=(2026,8,20,0,0,0)
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted([x for x in out.rglob('*') if x.is_file() and x.name not in ('MCAD_NH_R2_RESULTS.zip','MCAD_NH_R2_RESULTS_SHA256.txt') and x.as_posix().split('/')[-2:] != ['logs','package.log']]):
        zi=zipfile.ZipInfo(p.relative_to(out).as_posix(),epoch); zi.external_attr=(0o644&0xFFFF)<<16; zi.compress_type=zipfile.ZIP_DEFLATED; z.writestr(zi,p.read_bytes(),compresslevel=9)
h=hashlib.sha256(zip_path.read_bytes()).hexdigest(); (out/'MCAD_NH_R2_RESULTS_SHA256.txt').write_text(f'{h}  MCAD_NH_R2_RESULTS.zip\n')
print('results_zip='+str(zip_path)); print('results_zip_sha256='+h); print('internal_checksum_count='+str(len(lines)))
