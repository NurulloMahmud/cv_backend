"""
Regression test — run after any backend change to verify all 37 endpoints.
Uses mongomock (in-memory MongoDB). No real DB or WeasyPrint needed.

Run:  python test_endpoints.py
"""
import os, sys, json, traceback

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['SECRET_KEY'] = 'test-secret-key-for-tests'
os.environ['DEBUG'] = 'True'
os.environ['JWT_SECRET_KEY'] = 'test-jwt-secret'
os.environ['ALLOWED_HOSTS'] = 'localhost,127.0.0.1,testserver'
os.environ['MONGODB_URI'] = 'MOCK'

import mongomock, mongoengine
mongoengine.disconnect_all()
mongoengine.connect('tezcv_test', alias='default',
                    mongo_client_class=mongomock.MongoClient,
                    uuidRepresentation='standard')
_real_connect = mongoengine.connect
mongoengine.connect = lambda *a, **kw: None  # skip settings.py reconnect

import django
from django.test import Client
from django.test.utils import setup_test_environment
setup_test_environment()
django.setup()

PASS = '\033[92m✓\033[0m'; FAIL = '\033[91m✗\033[0m'
results = []

def test(name, fn):
    try:
        fn(); results.append((True, name)); print(f'  {PASS} {name}')
    except AssertionError as e:
        results.append((False, name)); print(f'  {FAIL} {name}\n      {e}')
    except Exception:
        results.append((False, name)); print(f'  {FAIL} {name}'); traceback.print_exc()

def j(r): return json.loads(r.content)
def ok(r, code, msg=''): assert r.status_code == code, f'Expected {code}, got {r.status_code}. {msg} {r.content[:200]}'

client = Client()
state = {}

print('\n' + '='*60 + '\nTezCV.uz — Endpoint Regression Tests\n' + '='*60)

# ── Auth: Register ────────────────────────────────────────────────────────────
print('\n[AUTH] Register')

def t_register():
    r = client.post('/api/auth/register/', {'email':'test@example.com','password':'SecurePass123','first_name':'John','last_name':'Doe'}, content_type='application/json')
    ok(r, 201); d = j(r)
    assert 'access' in d and 'refresh' in d and 'user' in d
    assert d['user']['email'] == 'test@example.com'
    assert 'password' not in d['user']
    state['access'] = d['access']; state['refresh'] = d['refresh']
test('POST /api/auth/register/ — success', t_register)

def t_register_dup():
    r = client.post('/api/auth/register/', {'email':'test@example.com','password':'AnotherPass123'}, content_type='application/json')
    ok(r, 400); assert 'email' in j(r)
test('POST /api/auth/register/ — duplicate email → 400', t_register_dup)

def t_register_weak():
    r = client.post('/api/auth/register/', {'email':'weak@example.com','password':'short'}, content_type='application/json')
    ok(r, 400)
test('POST /api/auth/register/ — weak password → 400', t_register_weak)

# ── Auth: Login ───────────────────────────────────────────────────────────────
print('\n[AUTH] Login')

def t_login():
    r = client.post('/api/auth/login/', {'email':'test@example.com','password':'SecurePass123'}, content_type='application/json')
    ok(r, 200); d = j(r)
    assert 'access' in d and 'refresh' in d
    state['access'] = d['access']; state['refresh'] = d['refresh']
test('POST /api/auth/login/ — success', t_login)

test('POST /api/auth/login/ — wrong password → 401', lambda: ok(client.post('/api/auth/login/', {'email':'test@example.com','password':'Wrong1'}, content_type='application/json'), 401))
test('POST /api/auth/login/ — unknown email → 401', lambda: ok(client.post('/api/auth/login/', {'email':'ghost@x.com','password':'Pass1234'}, content_type='application/json'), 401))

# ── Auth: Profile ─────────────────────────────────────────────────────────────
print('\n[AUTH] Profile')

def t_profile():
    r = client.get('/api/auth/profile/', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200); assert j(r)['email'] == 'test@example.com'
test('GET /api/auth/profile/ — authenticated', t_profile)
test('GET /api/auth/profile/ — no token → 401', lambda: ok(client.get('/api/auth/profile/'), 401))

def t_profile_update():
    r = client.put('/api/auth/profile/', {'first_name':'Jane','phone_number':'+1234567890'}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200); d = j(r); assert d['first_name'] == 'Jane'
test('PUT /api/auth/profile/ — update fields', t_profile_update)

# ── Auth: Token refresh ───────────────────────────────────────────────────────
print('\n[AUTH] Token refresh')

def t_refresh():
    r = client.post('/api/auth/token/refresh/', {'refresh': state['refresh']}, content_type='application/json')
    ok(r, 200); d = j(r); assert 'access' in d and 'refresh' in d
    state['old_refresh'] = state['refresh']
    state['access'] = d['access']; state['refresh'] = d['refresh']
test('POST /api/auth/token/refresh/ — new pair returned', t_refresh)

def t_refresh_reuse():
    r = client.post('/api/auth/token/refresh/', {'refresh': state['old_refresh']}, content_type='application/json')
    ok(r, 401)
test('POST /api/auth/token/refresh/ — reuse blacklisted token → 401', t_refresh_reuse)
test('POST /api/auth/token/refresh/ — invalid token → 401', lambda: ok(client.post('/api/auth/token/refresh/', {'refresh':'bad.token.here'}, content_type='application/json'), 401))

# ── Auth: Change password ─────────────────────────────────────────────────────
print('\n[AUTH] Change password')

def t_chpw():
    r = client.post('/api/auth/change-password/', {'old_password':'SecurePass123','new_password':'NewSecure456'}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200)
    r2 = client.post('/api/auth/login/', {'email':'test@example.com','password':'NewSecure456'}, content_type='application/json')
    ok(r2, 200); d = j(r2); state['access'] = d['access']; state['refresh'] = d['refresh']
test('POST /api/auth/change-password/ — success + re-login', t_chpw)
test('POST /api/auth/change-password/ — wrong old password → 400', lambda: ok(client.post('/api/auth/change-password/', {'old_password':'WrongOld','new_password':'AnotherNew123'}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}'), 400))

# ── CV: Create & retrieve ─────────────────────────────────────────────────────
print('\n[CV] Create & retrieve')

def t_cv_create_auth():
    r = client.post('/api/cv/', {'title':'My CV','template_choice':1}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 201); d = j(r)
    assert 'id' in d and d['title'] == 'My CV'
    for key in ('personal_info','experiences','education','skills','languages','certificates'):
        assert key in d
    state['cv_id'] = d['id']
test('POST /api/cv/ — authenticated create', t_cv_create_auth)

def t_cv_create_anon():
    r = client.post('/api/cv/', {'title':'Anon CV','template_choice':2}, content_type='application/json')
    ok(r, 201)
    sk = r.get('X-Session-Key')
    assert sk, 'X-Session-Key header missing'
    state['anon_cv_id'] = j(r)['id']; state['anon_sk'] = sk
test('POST /api/cv/ — anonymous, X-Session-Key returned', t_cv_create_anon)

def t_cv_list():
    r = client.get('/api/cv/', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200); ids = [x['id'] for x in j(r)]
    assert state['cv_id'] in ids
test('GET /api/cv/ — authenticated list', t_cv_list)

test('GET /api/cv/<id>/ — detail', lambda: ok(client.get(f'/api/cv/{state["cv_id"]}/', HTTP_AUTHORIZATION=f'Bearer {state["access"]}'), 200))
test('GET /api/cv/<id>/ — anonymous correct session key', lambda: ok(client.get(f'/api/cv/{state["anon_cv_id"]}/', HTTP_X_SESSION_KEY=state['anon_sk']), 200))
test('GET /api/cv/<id>/ — anonymous wrong session key → 403', lambda: ok(client.get(f'/api/cv/{state["anon_cv_id"]}/', HTTP_X_SESSION_KEY='wrong-key'), 403))
test('GET /api/cv/<bad-id>/ — not found → 404', lambda: ok(client.get('/api/cv/000000000000000000000000/', HTTP_AUTHORIZATION=f'Bearer {state["access"]}'), 404))

# ── CV: PATCH ─────────────────────────────────────────────────────────────────
print('\n[CV] PATCH')

def t_patch_personal():
    r = client.patch(f'/api/cv/{state["cv_id"]}/', {'personal_info':{'full_name':'Jane Doe','email':'jane@example.com','phone':'+99890 123 45 67','address':'Tashkent','city':'Tashkent','country':'Uzbekistan','linkedin':'','github':'','website':'','summary':'Dev.'}}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200); assert j(r)['personal_info']['full_name'] == 'Jane Doe'
test('PATCH /api/cv/<id>/ — personal_info', t_patch_personal)

def t_patch_exp():
    r = client.patch(f'/api/cv/{state["cv_id"]}/', {'experiences':[{'company':'TechCorp','position':'Senior Dev','location':'Tashkent','start_date':'2022-01','end_date':'','is_current':True,'description':'Led frontend.','order':0}]}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200); d = j(r); assert len(d['experiences']) == 1 and d['experiences'][0]['is_current'] is True
test('PATCH /api/cv/<id>/ — experiences', t_patch_exp)

def t_patch_edu_skills():
    r = client.patch(f'/api/cv/{state["cv_id"]}/', {'education':[{'institution':'TUIT','degree':"Bachelor's",'field_of_study':'CS','location':'Tashkent','start_date':'2016-09','end_date':'2020-06','is_current':False,'gpa':'3.8','description':'','order':0}],'skills':[{'name':'React','level':'advanced','category':'Frontend','order':0},{'name':'Python','level':'intermediate','category':'Backend','order':1}],'languages':[{'name':'Uzbek','proficiency':'native'},{'name':'English','proficiency':'fluent'}]}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200); d = j(r)
    assert d['education'][0]['gpa'] == '3.8'
    assert len(d['skills']) == 2 and len(d['languages']) == 2
test('PATCH /api/cv/<id>/ — education, skills, languages', t_patch_edu_skills)

def t_patch_template():
    r = client.patch(f'/api/cv/{state["cv_id"]}/', {'template_choice':2}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200); assert j(r)['template_choice'] == 2
test('PATCH /api/cv/<id>/ — template_choice', t_patch_template)

def t_patch_unauthorized():
    r2 = client.post('/api/auth/register/', {'email':'other@example.com','password':'OtherPass456'}, content_type='application/json')
    tok = j(r2)['access']
    ok(client.patch(f'/api/cv/{state["cv_id"]}/', {'title':'Hacked'}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {tok}'), 403)
test('PATCH /api/cv/<id>/ — wrong user → 403', t_patch_unauthorized)

# ── CV: PUT ───────────────────────────────────────────────────────────────────
print('\n[CV] PUT (full replace)')

def t_put():
    body = {'title':'Updated','template_choice':3,'personal_info':{'full_name':'John Smith','email':'john@x.com','phone':'+1','address':'Tashkent','city':'Tashkent','country':'UZ','linkedin':'','github':'','website':'','summary':'Dev.'},'experiences':[],'education':[],'skills':[{'name':'TypeScript','level':'advanced','category':'','order':0}],'languages':[],'certificates':[]}
    r = client.put(f'/api/cv/{state["cv_id"]}/', body, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200); d = j(r)
    assert d['title'] == 'Updated' and d['template_choice'] == 3
    assert len(d['experiences']) == 0 and d['skills'][0]['name'] == 'TypeScript'
test('PUT /api/cv/<id>/ — full replace', t_put)

# ── CV: DELETE ────────────────────────────────────────────────────────────────
print('\n[CV] DELETE')

def t_delete():
    r = client.post('/api/cv/', {'title':'To Delete'}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    tmp = j(r)['id']
    ok(client.delete(f'/api/cv/{tmp}/', HTTP_AUTHORIZATION=f'Bearer {state["access"]}'), 204)
    ok(client.get(f'/api/cv/{tmp}/', HTTP_AUTHORIZATION=f'Bearer {state["access"]}'), 404)
test('DELETE /api/cv/<id>/ — deleted, then 404', t_delete)

def t_delete_unauth():
    r2 = client.post('/api/auth/register/', {'email':'third@x.com','password':'ThirdPass789'}, content_type='application/json')
    ok(client.delete(f'/api/cv/{state["cv_id"]}/', HTTP_AUTHORIZATION=f'Bearer {j(r2)["access"]}'), 403)
test('DELETE /api/cv/<id>/ — wrong user → 403', t_delete_unauth)

# ── PDF ───────────────────────────────────────────────────────────────────────
print('\n[PDF]')

def t_pdf_export():
    r = client.get(f'/api/pdf/{state["cv_id"]}/export-pdf/', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    assert r.status_code in (200, 503), f'Expected 200 or 503, got {r.status_code}'
    if r.status_code == 503:
        assert 'WeasyPrint' in j(r)['detail'] or 'PDF' in j(r)['detail']
        print('      (WeasyPrint system libs not present — 503 returned correctly)')
    else:
        assert r['Content-Type'] == 'application/pdf'
test('GET /api/pdf/<id>/export-pdf/ — 200 or graceful 503', t_pdf_export)

test('GET /api/pdf/<bad-id>/export-pdf/ — not found → 404', lambda: ok(client.get('/api/pdf/000000000000000000000000/export-pdf/', HTTP_AUTHORIZATION=f'Bearer {state["access"]}'), 404))

def t_pdf_wrong_owner():
    r2 = client.post('/api/auth/register/', {'email':'fourth@x.com','password':'FourthPass000'}, content_type='application/json')
    ok(client.get(f'/api/pdf/{state["cv_id"]}/export-pdf/', HTTP_AUTHORIZATION=f'Bearer {j(r2)["access"]}'), 403)
test('GET /api/pdf/<id>/export-pdf/ — wrong owner → 403', t_pdf_wrong_owner)

def t_pdf_preview():
    r = client.get(f'/api/pdf/{state["cv_id"]}/preview/', HTTP_AUTHORIZATION=f'Bearer {state["access"]}')
    ok(r, 200); assert 'text/html' in r['Content-Type']
test('GET /api/pdf/<id>/preview/ — returns HTML', t_pdf_preview)

# ── Auth: Logout ──────────────────────────────────────────────────────────────
print('\n[AUTH] Logout')

def t_logout():
    ok(client.post('/api/auth/logout/', {'refresh': state['refresh']}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {state["access"]}'), 204)
test('POST /api/auth/logout/ — 204', t_logout)

def t_refresh_after_logout():
    ok(client.post('/api/auth/token/refresh/', {'refresh': state['refresh']}, content_type='application/json'), 401)
test('POST /api/auth/token/refresh/ — after logout, blacklisted → 401', t_refresh_after_logout)

# ── Docs ──────────────────────────────────────────────────────────────────────
print('\n[API Docs]')
test('GET /api/schema/ — 200', lambda: ok(client.get('/api/schema/'), 200))
test('GET /api/docs/ — 200', lambda: ok(client.get('/api/docs/'), 200))

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(1 for ok_, _ in results if ok_)
failed = sum(1 for ok_, _ in results if not ok_)
print(f'\n{"="*60}')
print(f'Results: {passed}/{len(results)} passed' + (f'  ({failed} failed)' if failed else ''))
if failed:
    print('Failed:')
    for ok_, name in results:
        if not ok_: print(f'  {FAIL} {name}')
print('='*60 + '\n')
sys.exit(0 if failed == 0 else 1)
