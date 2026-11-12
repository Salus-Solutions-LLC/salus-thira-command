"""Shared Salus web links remain credential-free, tenant-bound, and attributed."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_shared_web_links_api_and_navigation(tmp_path):
    html = Path("static/index.html").read_text(encoding="utf-8")
    script = Path("static/app.js").read_text(encoding="utf-8")
    administration = html[html.index('<div class="nav-product-title">Administration</div>'):]
    assert administration.index('data-view="shared_web_links"') < administration.index('data-view="security"')
    assert 'data-view="shared_web_links">Web Links</button>' in administration
    feature = script[script.index("async function sharedWebLinks()"):script.index("async function securityReadiness()")]
    assert 'name="username"' not in feature
    assert 'name="password"' not in feature
    assert 'rel="noopener noreferrer"' in feature

    env = os.environ.copy()
    env.update({
        "SALUS_DB_PATH": str(tmp_path / "shared-links.db"),
        "SALUS_LOCAL_STORAGE_DIR": str(tmp_path / "attachments"),
        "SALUS_BACKUP_DIR": str(tmp_path / "backups"),
        "SALUS_SEED_DEMO": "0",
        "SALUS_AUTH_MODE": "prototype",
        "PYTHONPATH": os.pathsep.join(filter(None, (os.getcwd(), env.get("PYTHONPATH", "")))),
    })
    program = textwrap.dedent(r'''
        from fastapi.testclient import TestClient
        import app
        from portable_backup import collect_tenant_records

        def client(role, user='Fictional Salus Person', tenant='1'):
            return TestClient(app.app, headers={
                'X-Salus-Role': role,
                'X-Salus-User': user,
                'X-Salus-Tenant': tenant,
            })

        admin=client('System Administrator','Fictional Administrator')
        created=admin.post('/api/salcapa/shared-web-links',json={
            'url':'https://portal.example.invalid/sign-in',
            'description':'Fictional service portal',
        })
        assert created.status_code==200, created.text
        link=created.json()
        assert link['version']==1
        assert link['created_by']=='Fictional Administrator'
        assert 'username' not in link and 'password' not in link

        lead=client('Lead Assessor','Fictional Lead')
        listed=lead.get('/api/salcapa/shared-web-links')
        assert listed.status_code==200 and listed.json()==[link]
        updated=lead.patch(f"/api/salcapa/shared-web-links/{link['id']}",json={
            'url':'https://portal.example.invalid/home',
            'description':'Fictional service home page',
            'version':1,
        })
        assert updated.status_code==200, updated.text
        changed=updated.json()
        assert changed['version']==2 and changed['updated_by']=='Fictional Lead'

        stale=admin.patch(f"/api/salcapa/shared-web-links/{link['id']}",json={
            'url':'https://portal.example.invalid/stale',
            'description':'Stale edit',
            'version':1,
        })
        assert stale.status_code==409
        assert admin.post('/api/salcapa/shared-web-links',json={
            'url':'http://portal.example.invalid','description':'Not secure'
        }).status_code==422
        assert admin.post('/api/salcapa/shared-web-links',json={
            'url':'https://user:secret@portal.example.invalid','description':'Embedded credentials'
        }).status_code==422

        auditor=client('Auditor','Fictional Auditor')
        assert auditor.get('/api/salcapa/shared-web-links').status_code==200
        assert auditor.post('/api/salcapa/shared-web-links',json={
            'url':'https://audit.example.invalid','description':'Audit link'
        }).status_code==403
        assert auditor.patch(f"/api/salcapa/shared-web-links/{link['id']}",json={
            'url':changed['url'],'description':changed['description'],'version':2
        }).status_code==403

        for protected_role in ('Client Executive','Contributor'):
            protected=client(protected_role,'Fictional Protected Member')
            assert protected.get('/api/salcapa/shared-web-links').status_code==403
            assert protected.post('/api/salcapa/shared-web-links',json={
                'url':'https://member.example.invalid','description':'Member link'
            }).status_code==403

        other=client('Assessment Director','Other Tenant Director','2')
        assert other.get('/api/salcapa/shared-web-links').json()==[]
        assert other.patch(f"/api/salcapa/shared-web-links/{link['id']}",json={
            'url':changed['url'],'description':changed['description'],'version':2
        }).status_code==404

        conn=app.db()
        archive=collect_tenant_records(conn,1)
        assert len(archive['shared_web_links'])==1
        assert archive['shared_web_links'][0]['description']=='Fictional service home page'
        events=[dict(row) for row in conn.execute(
            "SELECT action,entity_type,user_name,tenant_id FROM audit_log "
            "WHERE entity_type='shared_web_link' ORDER BY id"
        )]
        conn.close()
        assert events==[
            {'action':'CREATE','entity_type':'shared_web_link','user_name':'Fictional Administrator','tenant_id':1},
            {'action':'UPDATE','entity_type':'shared_web_link','user_name':'Fictional Lead','tenant_id':1},
        ]
    ''')
    completed = subprocess.run(
        [sys.executable, "-c", program], env=env, capture_output=True, text=True, timeout=80
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
