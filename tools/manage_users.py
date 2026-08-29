#!/usr/bin/env python3
import argparse, getpass, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

ROLES=list(app.ROLE_PERMISSIONS)
CLEARANCES=list(app.SENSITIVITY_LEVELS)

def main():
    p=argparse.ArgumentParser(description='Manage Salus THIRA Command local/session/OIDC users.')
    sub=p.add_subparsers(dest='cmd',required=True)
    add=sub.add_parser('add'); add.add_argument('username'); add.add_argument('--display-name',default=''); add.add_argument('--email',default=''); add.add_argument('--role',choices=ROLES,default='System Administrator'); add.add_argument('--clearance',choices=CLEARANCES,default='Highly Sensitive'); add.add_argument('--tenant',type=int,default=1); add.add_argument('--password')
    oidc=sub.add_parser('bind-oidc'); oidc.add_argument('username'); oidc.add_argument('--subject',required=True); oidc.add_argument('--provider',default='oidc'); oidc.add_argument('--email',default='')
    sub.add_parser('list')
    disable=sub.add_parser('disable'); disable.add_argument('username')
    grant=sub.add_parser('grant'); grant.add_argument('username'); grant.add_argument('assessment_id',type=int); grant.add_argument('--role-override',default=''); grant.add_argument('--clearance',choices=['']+CLEARANCES,default='')
    revoke=sub.add_parser('revoke'); revoke.add_argument('username'); revoke.add_argument('assessment_id',type=int)
    args=p.parse_args(); c=app.db()
    if args.cmd=='list':
        for r in c.execute('SELECT id,tenant_id,username,display_name,email,identity_provider,external_subject,role,sensitivity_clearance,status FROM users ORDER BY username'): print(dict(r))
    elif args.cmd=='grant':
        u=c.execute('SELECT id,tenant_id FROM users WHERE lower(username)=lower(?)',(args.username,)).fetchone(); a=c.execute('SELECT tenant_id FROM assessments WHERE id=?',(args.assessment_id,)).fetchone()
        if not u or not a: raise SystemExit('User or assessment not found.')
        if u['tenant_id']!=a['tenant_id']: raise SystemExit('User and assessment must belong to the same tenant.')
        c.execute('''INSERT INTO assessment_access(user_id,assessment_id,role_override,sensitivity_clearance,created_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id,assessment_id) DO UPDATE SET role_override=excluded.role_override,sensitivity_clearance=excluded.sensitivity_clearance''',(u['id'],args.assessment_id,args.role_override,args.clearance,app.now())); c.commit(); print('granted',args.username,'assessment',args.assessment_id)
    elif args.cmd=='revoke':
        c.execute('DELETE FROM assessment_access WHERE user_id IN (SELECT id FROM users WHERE lower(username)=lower(?)) AND assessment_id=?',(args.username,args.assessment_id)); c.commit(); print('revoked',args.username,'assessment',args.assessment_id)
    elif args.cmd=='disable':
        c.execute("UPDATE users SET status='Disabled',updated_at=? WHERE lower(username)=lower(?)",(app.now(),args.username)); c.execute('DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE lower(username)=lower(?))',(args.username,)); c.commit(); print('disabled',args.username)
    elif args.cmd=='bind-oidc':
        cur=c.execute("UPDATE users SET external_subject=?,identity_provider=?,email=CASE WHEN ?<>'' THEN ? ELSE email END,updated_at=? WHERE lower(username)=lower(?)",(args.subject,args.provider,args.email,args.email,app.now(),args.username))
        if not cur.rowcount: raise SystemExit('User not found.')
        c.commit(); print('OIDC identity bound',args.username,args.provider,args.subject)
    else:
        password=args.password or getpass.getpass('Password (leave blank for OIDC-only account): ')
        if password and len(password)<12: raise SystemExit('Password must be at least 12 characters.')
        if not c.execute('SELECT 1 FROM tenants WHERE id=?',(args.tenant,)).fetchone(): raise SystemExit('Tenant does not exist.')
        ts=app.now(); encoded=app.hash_password(password) if password else ''
        c.execute('''INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,created_at,updated_at,email) VALUES(?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(username) DO UPDATE SET tenant_id=excluded.tenant_id,display_name=excluded.display_name,password_hash=CASE WHEN excluded.password_hash<>'' THEN excluded.password_hash ELSE users.password_hash END,role=excluded.role,sensitivity_clearance=excluded.sensitivity_clearance,status='Active',updated_at=excluded.updated_at,email=excluded.email''',(args.tenant,args.username,args.display_name,encoded,args.role,args.clearance,'Active',ts,ts,args.email.lower())); c.commit(); print('saved',args.username)
    c.close()
if __name__=='__main__': main()
