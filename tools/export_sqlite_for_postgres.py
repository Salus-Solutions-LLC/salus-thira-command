#!/usr/bin/env python3
import argparse, sqlite3, json, hashlib
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description='Export Salus THIRA SQLite records to deterministic NDJSON files for managed-database migration.')
    ap.add_argument('--db',default='thira.db'); ap.add_argument('--out',default='migration_export')
    a=ap.parse_args(); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(a.db); c.row_factory=sqlite3.Row
    tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    manifest={'source':str(Path(a.db).resolve()),'tables':[]}
    for table in tables:
        columns=[x[1] for x in c.execute(f'PRAGMA table_info("{table}")')]
        query=f'SELECT * FROM "{table}" ORDER BY id' if 'id' in columns else f'SELECT * FROM "{table}"'
        rows=[dict(r) for r in c.execute(query)]
        path=out/f'{table}.ndjson'
        data=''.join(json.dumps(r,sort_keys=True,default=str,separators=(',',':'))+'\n' for r in rows).encode()
        path.write_bytes(data)
        manifest['tables'].append({'table':table,'rows':len(rows),'file':path.name,'sha256':hashlib.sha256(data).hexdigest()})
    c.close(); (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True))
    print(f'Exported {len(tables)} tables to {out}')
if __name__=='__main__': main()
