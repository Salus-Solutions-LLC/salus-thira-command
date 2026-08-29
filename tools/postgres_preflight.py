#!/usr/bin/env python3
import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from managed_database import managed_target_status
r=managed_target_status()
print(json.dumps(r,indent=2))
raise SystemExit(0 if r.get('healthy') and r.get('configured') else 2)
