#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import dr_validate_backup_file
ap=argparse.ArgumentParser(); ap.add_argument('backup'); a=ap.parse_args()
r=dr_validate_backup_file(a.backup); print(json.dumps(r,indent=2,default=str)); raise SystemExit(0 if r.get('ok') else 2)
