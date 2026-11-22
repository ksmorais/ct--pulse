"""CT Pulse 2.0: aplicação WSGI + SQLite, somente biblioteca padrão Python."""
import argparse, datetime as dt, getpass, hashlib, hmac, json, mimetypes, os, re, secrets, sqlite3, time
from pathlib import Path
from contextlib import contextmanager
from http.cookies import SimpleCookie
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('CT_DB', ROOT/'data'/'ctpulse.sqlite3'))
SECURE=os.environ.get('CT_SECURE_COOKIE','0')=='1'
BELTS=['Branca','Amarela','Laranja','Verde','Azul','Marrom','Preta']
ROLES=['admin','teacher','student']
class APIError(Exception):
    def __init__(self, status, message): self.status=status; self.message=message

def fail(message,status=400): raise APIError(status,message)
def today():
    # Brasília UTC-3 (fallback para instalações Windows sem tzdata)
    try: tz=ZoneInfo('America/Sao_Paulo')
    except Exception: tz=dt.timezone(dt.timedelta(hours=-3))
    return dt.datetime.now(tz).date().isoformat()
def db_connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB,timeout=10,isolation_level=None); conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON'); conn.execute('PRAGMA busy_timeout=10000'); return conn

@contextmanager
def connection():
    c=db_connect()
    try:
        with c: yield c
    finally: c.close()

def init():
    with connection() as c:
        c.execute('PRAGMA journal_mode=WAL'); c.executescript((ROOT/'schema.sql').read_text())
def hash_password(pw):
    salt=secrets.token_hex(16); digest=hashlib.pbkdf2_hmac('sha256',pw.encode(),bytes.fromhex(salt),600000).hex(); return f'{salt}:{digest}'
def verify(pw,stored):
    salt,digest=stored.split(':'); return hmac.compare_digest(digest,hashlib.pbkdf2_hmac('sha256',pw.encode(),bytes.fromhex(salt),600000).hex())
def tokenhash(t): return hashlib.sha256(t.encode()).hexdigest()
def password(p):
    if not isinstance(p,str) or not 12<=len(p)<=128: fail('A senha deve ter entre 12 e 128 caracteres.')
    return p
def string(d,k,limit=150):
    v=d.get(k); v=v.strip() if isinstance(v,str) else ''
    if not v or len(v)>limit: fail(f'Campo {k} inválido (máximo de {limit} caracteres).')
    return v
def email(d):
    v=string(d,'email',254).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v): fail('E-mail inválido.')
    return v
def integer(d,k,lo=1,hi=10**9):
    v=d.get(k)
    if type(v)!=int or not lo<=v<=hi: fail(f'Campo {k} inválido.')
    return v
def date_value(d,k='date'):
    try: return dt.date.fromisoformat(string(d,k,10)).isoformat()
    except ValueError: fail('Data inválida.')
def get(c,sql,args=()):
    row=c.execute(sql,args).fetchone()
    if row is None: fail('Registro não encontrado.',404)
    return dict(row)
def rows(c,sql,args=()): return [dict(x) for x in c.execute(sql,args)]
def allow(u,*roles):
    if u['role'] not in roles: fail('Acesso não autorizado.',403)
def student(c,sid): return get(c,"SELECT id,name,email,active,plan_cents,belt FROM users WHERE id=? AND role='student'",(sid,))
def class_access(c,u,cid):
    cl=get(c,'SELECT * FROM classes WHERE id=?',(cid,))
    if u['role']=='teacher' and cl['teacher_id']!=u['id']: fail('Turma de outro professor.',403)
    return cl
def teacher_student(c,u,sid):
    if u['role']=='teacher' and not c.execute('SELECT 1 FROM enrollments e JOIN classes cl ON cl.id=e.class_id WHERE e.student_id=? AND cl.teacher_id=?',(sid,u['id'])).fetchone(): fail('Aluno fora das suas turmas.',403)
def public(u): return {k:u[k] for k in ('id','name','email','role','belt','plan_cents','active')}
def create_user(c,name,mail,pw,role,plan=0):
    return c.execute('INSERT INTO users(name,email,password_hash,role,plan_cents) VALUES(?,?,?,?,?)',(name,mail,hash_password(password(pw)),role,plan)).lastrowid
def make_payment(c,sid,month,amount,due):
    c.execute('INSERT OR IGNORE INTO payments(student_id,month,amount_cents,due) VALUES(?,?,?,?)',(sid,month,amount,due))

def seed_demo():
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM users LIMIT 1').fetchone(): fail('O banco não está vazio. Use outro arquivo CT_DB.')
        a=create_user(c,'Administração','admin@ctpulse.com',(os.environ.get('CT_DEMO_PASSWORD') or 'DemoAdmin2026!'),'admin'); t=create_user(c,'Prof. Diego','prof@ctpulse.com',(os.environ.get('CT_DEMO_PASSWORD') or 'DemoProfessor2026!'),'teacher'); s=create_user(c,'Marina Costa','aluno@ctpulse.com',(os.environ.get('CT_DEMO_PASSWORD') or 'DemoAluno2026!'),'student',15900)
        s2=create_user(c,'João Martins','joao@ctpulse.com',(os.environ.get('CT_DEMO_PASSWORD') or 'DemoJoao2026!'),'student',17900)
        cid=c.execute('INSERT INTO classes(name,teacher_id,days,time,capacity) VALUES(?,?,?,?,?)',('Muay Thai • Iniciante',t,'[1,3,5]','18:00',16)).lastrowid
        c.execute('INSERT INTO classes(name,teacher_id,days,time,capacity) VALUES(?,?,?,?,?)',('Jiu-jitsu • Fundamentos',t,'[2,4]','19:00',12))
        c.execute('INSERT INTO enrollments VALUES(?,?)',(s,cid)); c.execute('INSERT INTO enrollments VALUES(?,?)',(s2,cid))
        for sid,amount in [(s,15900),(s2,17900)]: make_payment(c,sid,today()[:7],amount,today()[:7]+'-20')
        nid=c.execute('INSERT INTO notices(author_id,title,body) VALUES(?,?,?)',(t,'Bem-vindos ao CT Pulse','Consulte a grade e reserve seu próximo treino.')).lastrowid
        c.executemany('INSERT INTO inbox(notice_id,student_id) VALUES(?,?)',[(nid,s),(nid,s2)]); c.commit()

def auth(c,env):
    cookie=SimpleCookie(); cookie.load(env.get('HTTP_COOKIE','')); tok=cookie.get('ct_session')
    if not tok: fail('Faça login para continuar.',401)
    rec=c.execute('SELECT u.*,s.csrf,s.token_hash FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1',(tokenhash(tok.value),int(time.time()))).fetchone()
    if not rec: fail('Sessão expirada. Entre novamente.',401)
    u=dict(rec)
    if env['REQUEST_METHOD']!='GET' and not hmac.compare_digest(env.get('HTTP_X_CSRF_TOKEN',''),u['csrf']): fail('Solicitação não autorizada.',403)
    return u

def login(c,env,d):
    mail=email(d); pw=d.get('password'); key=tokenhash(env.get('REMOTE_ADDR','')+'|'+mail); now=int(time.time())
    attempt=c.execute('SELECT * FROM login_attempts WHERE key=? AND until>?',(key,now)).fetchone()
    if attempt and attempt['attempts']>=8: fail('Muitas tentativas. Tente novamente em 15 minutos.',429)
    u=c.execute('SELECT * FROM users WHERE email=? AND active=1',(mail,)).fetchone()
    valid=isinstance(pw,str) and len(pw)<=128 and verify(pw,u['password_hash'] if u else '0'*32+':'+'0'*64)
    if not u or not valid:
        c.execute('INSERT INTO login_attempts VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET attempts=excluded.attempts,until=excluded.until',(key,(attempt['attempts'] if attempt else 0)+1,attempt['until'] if attempt else now+900)); c.commit(); fail('E-mail ou senha incorretos.',401)
    c.execute('DELETE FROM login_attempts WHERE key=? OR until<?',(key,now)); c.execute('DELETE FROM sessions WHERE expires<?',(now,)); tok=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(24)
    c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(tokenhash(tok),u['id'],csrf,now+43200)); c.commit()
    return {'user':public(dict(u)),'csrf':csrf}, [('Set-Cookie',f'ct_session={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200'+('; Secure' if SECURE else ''))]

def state(c,u):
    role=u['role']; uid=u['id']; clsql='SELECT cl.*,u.name teacher,(SELECT count(*) FROM enrollments e JOIN users s ON s.id=e.student_id WHERE e.class_id=cl.id AND s.active=1) enrolled_count FROM classes cl JOIN users u ON u.id=cl.teacher_id '
    if role=='admin':
        students=rows(c,"SELECT id,name,email,active,plan_cents,belt FROM users WHERE role='student' ORDER BY name"); classes=rows(c,clsql+'ORDER BY cl.name'); teachers=rows(c,"SELECT id,name,email,active FROM users WHERE role='teacher' ORDER BY name"); enroll=rows(c,'SELECT * FROM enrollments'); bookings=rows(c,'SELECT * FROM bookings'); attendance=rows(c,'SELECT * FROM attendance'); payments=rows(c,'SELECT * FROM payments ORDER BY month DESC'); grades=rows(c,'SELECT * FROM grades ORDER BY date DESC,id DESC'); notices=rows(c,'SELECT n.*,u.name author FROM notices n JOIN users u ON u.id=n.author_id ORDER BY n.id DESC')
    elif role=='teacher':
        students=rows(c,"SELECT DISTINCT s.id,s.name,s.active,s.belt FROM users s JOIN enrollments e ON e.student_id=s.id JOIN classes cl ON cl.id=e.class_id WHERE cl.teacher_id=? ORDER BY s.name",(uid,)); classes=rows(c,clsql+'WHERE cl.teacher_id=? ORDER BY cl.name',(uid,)); teachers=[]; enroll=rows(c,'SELECT e.* FROM enrollments e JOIN classes cl ON cl.id=e.class_id WHERE cl.teacher_id=?',(uid,)); bookings=rows(c,'SELECT b.* FROM bookings b JOIN classes cl ON cl.id=b.class_id WHERE cl.teacher_id=?',(uid,)); attendance=rows(c,'SELECT a.* FROM attendance a JOIN classes cl ON cl.id=a.class_id WHERE cl.teacher_id=?',(uid,)); payments=[]; grades=rows(c,'SELECT g.* FROM grades g WHERE EXISTS(SELECT 1 FROM enrollments e JOIN classes cl ON cl.id=e.class_id WHERE e.student_id=g.student_id AND cl.teacher_id=?) ORDER BY g.id DESC',(uid,)); notices=rows(c,'SELECT n.*,u.name author FROM notices n JOIN users u ON u.id=n.author_id WHERE n.author_id=? ORDER BY n.id DESC',(uid,))
    else:
        students=[public(u)]; classes=rows(c,clsql+'WHERE cl.active=1 ORDER BY cl.name'); teachers=[]; enroll=rows(c,'SELECT * FROM enrollments WHERE student_id=?',(uid,)); bookings=rows(c,'SELECT * FROM bookings WHERE student_id=?',(uid,)); attendance=rows(c,'SELECT * FROM attendance WHERE student_id=?',(uid,)); payments=rows(c,'SELECT * FROM payments WHERE student_id=? ORDER BY month DESC',(uid,)); grades=rows(c,'SELECT * FROM grades WHERE student_id=? ORDER BY id DESC',(uid,)); notices=rows(c,'SELECT n.*,u.name author,i.read_at FROM inbox i JOIN notices n ON n.id=i.notice_id JOIN users u ON u.id=n.author_id WHERE i.student_id=? ORDER BY n.id DESC',(uid,))
    for cl in classes: cl['days']=json.loads(cl['days'])
    return dict(user=public(u),csrf=u['csrf'],today=today(),students=students,classes=classes,teachers=teachers,enrollments=enroll,bookings=bookings,attendance=attendance,payments=payments,grades=grades,notices=notices)

def actions(c,u,path,d):
    role=u['role']; uid=u['id']; action=path.removeprefix('/api/')
    if action=='logout':
        c.execute('DELETE FROM sessions WHERE token_hash=?',(u['token_hash'],)); return {'ok':True}, [('Set-Cookie','ct_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'+('; Secure' if SECURE else ''))]
    if action=='password':
        old=d.get('old'); stored=get(c,'SELECT password_hash FROM users WHERE id=?',(uid,))['password_hash']
        if not isinstance(old,str) or len(old)>128 or not verify(old,stored): fail('Senha atual incorreta.',403)
        c.execute('UPDATE users SET password_hash=? WHERE id=?',(hash_password(password(d.get('password'))),uid)); c.execute('DELETE FROM sessions WHERE user_id=? AND token_hash<>?',(uid,u['token_hash']))
    elif action=='user/save':
        allow(u,'admin'); name=string(d,'name'); mail=email(d); r=d.get('role');
        if r not in ('student','teacher'): fail('Perfil inválido.')
        plan=integer(d,'plan_cents',0,10000000) if r=='student' else 0
        if d.get('id'):
            sid=integer(d,'id'); old=get(c,'SELECT * FROM users WHERE id=?',(sid,))
            if old['role']!=r: fail('Perfil não pode ser alterado.')
            c.execute('UPDATE users SET name=?,email=?,plan_cents=? WHERE id=?',(name,mail,plan,sid))
            if d.get('password'): c.execute('UPDATE users SET password_hash=? WHERE id=?',(hash_password(password(d['password'])),sid)); c.execute('DELETE FROM sessions WHERE user_id=?',(sid,))
        else: sid=create_user(c,name,mail,d.get('password',''),r,plan)
        if r=='student': make_payment(c,sid,today()[:7],plan,today()[:7]+'-20')
    elif action=='user/active':
        allow(u,'admin'); sid=integer(d,'id'); target=get(c,'SELECT role FROM users WHERE id=?',(sid,));
        if target['role']=='admin': fail('Administrador não pode ser desativado.')
        active=integer(d,'active',0,1)
        if active and target['role']=='student':
            if c.execute('SELECT 1 FROM enrollments e JOIN classes cl ON cl.id=e.class_id WHERE e.student_id=? AND (SELECT count(*) FROM enrollments en JOIN users us ON us.id=en.student_id WHERE en.class_id=cl.id AND us.active=1 AND us.id<>?)>=cl.capacity',(sid,sid)).fetchone(): fail('Há uma turma lotada vinculada ao aluno. Cancele a inscrição antes de reativar.',409)
        c.execute('UPDATE users SET active=? WHERE id=?',(active,sid))
        if not active: c.execute('DELETE FROM sessions WHERE user_id=?',(sid,)); c.execute('DELETE FROM bookings WHERE student_id=? AND date>=?',(sid,today()))
    elif action=='class/save':
        allow(u,'admin'); name=string(d,'name'); teacher=integer(d,'teacher_id'); get(c,"SELECT id FROM users WHERE id=? AND role='teacher' AND active=1",(teacher,)); days=d.get('days');
        if not isinstance(days,list) or not days or any(type(x)!=int or x not in range(7) for x in days): fail('Selecione dias válidos.')
        hour=string(d,'time',5)
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',hour): fail('Horário inválido.')
        cap=integer(d,'capacity',1,1000); args=(name,teacher,json.dumps(sorted(set(days))),hour,cap)
        if d.get('id'):
            cid=integer(d,'id'); class_access(c,u,cid); count=c.execute('SELECT count(*) FROM enrollments e JOIN users s ON s.id=e.student_id WHERE class_id=? AND s.active=1',(cid,)).fetchone()[0]
            if cap<count: fail('Capacidade inferior à quantidade de alunos ativos.')
            c.execute('UPDATE classes SET name=?,teacher_id=?,days=?,time=?,capacity=? WHERE id=?',args+(cid,))
        else: c.execute('INSERT INTO classes(name,teacher_id,days,time,capacity) VALUES(?,?,?,?,?)',args)
    elif action=='enrollment':
        allow(u,'admin','student'); sid=uid if role=='student' else integer(d,'student_id'); s=student(c,sid); cid=integer(d,'class_id'); cl=class_access(c,u,cid); active=integer(d,'active',0,1)
        if active:
            if not s['active'] or not cl['active']: fail('Aluno ou turma inativos.')
            count=c.execute('SELECT count(*) FROM enrollments e JOIN users s ON s.id=e.student_id WHERE class_id=? AND s.active=1',(cid,)).fetchone()[0]
            if not c.execute('SELECT 1 FROM enrollments WHERE class_id=? AND student_id=?',(cid,sid)).fetchone() and count>=cl['capacity']: fail('Turma lotada.',409)
            c.execute('INSERT OR IGNORE INTO enrollments VALUES(?,?)',(sid,cid))
        else: c.execute('DELETE FROM enrollments WHERE student_id=? AND class_id=?',(sid,cid)); c.execute('DELETE FROM bookings WHERE student_id=? AND class_id=? AND date>=?',(sid,cid,today()))
    elif action=='booking':
        allow(u,'student'); cid=integer(d,'class_id'); cl=class_access(c,u,cid); date=date_value(d); delta=(dt.date.fromisoformat(date)-dt.date.fromisoformat(today())).days
        if delta<0 or delta>90 or (dt.date.fromisoformat(date).weekday()+1)%7 not in json.loads(cl['days']): fail('Escolha uma data de aula nos próximos 90 dias.')
        get(c,'SELECT 1 FROM enrollments WHERE student_id=? AND class_id=?',(uid,cid));
        if not cl['active']: fail('Turma inativa.')
        c.execute('INSERT OR IGNORE INTO bookings(student_id,class_id,date) VALUES(?,?,?)',(uid,cid,date))
    elif action=='booking/cancel':
        allow(u,'student'); bid=integer(d,'id'); get(c,'SELECT id FROM bookings WHERE id=? AND student_id=?',(bid,uid)); c.execute('DELETE FROM bookings WHERE id=?',(bid,))
    elif action=='attendance':
        allow(u,'admin','teacher'); cid=integer(d,'class_id'); sid=integer(d,'student_id'); class_access(c,u,cid); student(c,sid); get(c,'SELECT 1 FROM enrollments WHERE class_id=? AND student_id=?',(cid,sid)); day=date_value(d)
        if day>today(): fail('Não é possível registrar presença futura.')
        c.execute('INSERT INTO attendance VALUES(?,?,?,?) ON CONFLICT(student_id,class_id,date) DO UPDATE SET present=excluded.present',(sid,cid,day,integer(d,'present',0,1)))
    elif action=='payment/generate':
        allow(u,'admin'); month=string(d,'month',7); due=date_value(d,'due')
        if due[:7]!=month: fail('Vencimento deve pertencer ao mês de referência.')
        for s in rows(c,"SELECT id,plan_cents FROM users WHERE role='student' AND active=1"): make_payment(c,s['id'],month,s['plan_cents'],due)
    elif action=='payment/mark':
        allow(u,'admin'); pid=integer(d,'id'); status=d.get('status');
        if status not in ('paid','pending'): fail('Status inválido.')
        get(c,'SELECT id FROM payments WHERE id=?',(pid,)); c.execute('UPDATE payments SET status=?,paid_at=? WHERE id=?',(status,today() if status=='paid' else None,pid))
    elif action=='grade':
        allow(u,'admin','teacher'); sid=integer(d,'student_id'); student(c,sid); teacher_student(c,u,sid); belt=d.get('belt');
        if belt not in BELTS: fail('Graduação inválida.')
        note=string(d,'note',1000); c.execute('INSERT INTO grades(student_id,author_id,belt,note,date) VALUES(?,?,?,?,?)',(sid,uid,belt,note,today())); c.execute('UPDATE users SET belt=? WHERE id=?',(belt,sid))
    elif action=='notice':
        allow(u,'admin','teacher'); title=string(d,'title'); body=string(d,'body',2000); cid=d.get('class_id');
        if cid is not None: cid=integer(d,'class_id'); class_access(c,u,cid); recipients=rows(c,'SELECT u.id FROM users u JOIN enrollments e ON e.student_id=u.id WHERE e.class_id=? AND u.active=1',(cid,))
        elif role=='admin': recipients=rows(c,"SELECT id FROM users WHERE role='student' AND active=1")
        else: fail('Selecione uma de suas turmas.')
        nid=c.execute('INSERT INTO notices(author_id,class_id,title,body) VALUES(?,?,?,?)',(uid,cid,title,body)).lastrowid
        c.executemany('INSERT INTO inbox(notice_id,student_id) VALUES(?,?)',[(nid,s['id']) for s in recipients])
    elif action=='notice/read':
        allow(u,'student'); nid=integer(d,'id'); get(c,'SELECT notice_id FROM inbox WHERE notice_id=? AND student_id=?',(nid,uid)); c.execute('UPDATE inbox SET read_at=CURRENT_TIMESTAMP WHERE notice_id=? AND student_id=?',(nid,uid))
    else: fail('Rota não encontrada.',404)
    return {'ok':True},[]

STATUS={200:'OK',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',405:'Method Not Allowed',409:'Conflict',413:'Payload Too Large',429:'Too Many Requests',500:'Internal Server Error'}
def app(env,start):
    path=env.get('PATH_INFO','/'); method=env['REQUEST_METHOD']; headers=[]; status=200
    try:
        if path.startswith('/api/'):
            if method not in ('GET','POST'): fail('Método não permitido.',405)
            if method=='POST':
                if env.get('CONTENT_TYPE','').split(';')[0]!='application/json': fail('Envie JSON.')
                try: size=int(env.get('CONTENT_LENGTH') or '0')
                except ValueError: fail('Conteúdo inválido.')
                if size<0 or size>65536: fail('Conteúdo muito grande.',413)
                try: d=json.loads(env['wsgi.input'].read(size))
                except (ValueError,UnicodeError): fail('JSON inválido.')
                if not isinstance(d,dict): fail('JSON inválido.')
            with connection() as c:
                if method=='POST': c.execute('BEGIN IMMEDIATE')
                else: c.execute('BEGIN')
                if path=='/api/login' and method=='POST': payload,headers=login(c,env,d)
                else:
                    u=auth(c,env)
                    if path=='/api/state' and method=='GET': payload=state(c,u)
                    elif method=='POST': payload,headers=actions(c,u,path,d)
                    else: fail('Rota não encontrada.',404)
                c.commit()
            content=json.dumps(payload,ensure_ascii=False).encode(); typ='application/json; charset=utf-8'
        else:
            if method!='GET': fail('Método não permitido.',405)
            name='index.html' if path=='/' else path.lstrip('/')
            if name not in ('index.html','app.js','style.css','manifest.webmanifest','sw.js','icon.png','icon-512.png'): fail('Página não encontrada.',404)
            f=ROOT/'static'/name; content=f.read_bytes(); typ= 'application/manifest+json' if name.endswith('webmanifest') else (mimetypes.guess_type(name)[0] or 'application/octet-stream')
    except APIError as e: status=e.status; content=json.dumps({'error':e.message},ensure_ascii=False).encode(); typ='application/json; charset=utf-8'
    except sqlite3.IntegrityError: status=409; content=json.dumps({'error':'Registro já existente ou dados relacionados inválidos.'}).encode(); typ='application/json'
    except Exception:
        import traceback; traceback.print_exc(); status=500; content=b'{"error":"Erro interno do servidor."}'; typ='application/json'
    start(f'{status} {STATUS[status]}',[('Content-Type',typ),('Content-Length',str(len(content))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('X-Frame-Options','DENY'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")]+headers); return [content]
class ThreadServer(ThreadingMixIn,WSGIServer): daemon_threads=True
if __name__=='__main__':
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True); sub.add_parser('init'); sub.add_parser('demo'); a=sub.add_parser('admin'); a.add_argument('--email',required=True); a.add_argument('--name',default='Administração'); serve=sub.add_parser('serve'); serve.add_argument('--host',default='127.0.0.1'); serve.add_argument('--port',type=int,default=8000); arg=p.parse_args(); init()
    if arg.command=='init': print('Banco criado:',DB)
    elif arg.command=='demo': seed_demo(); print('Dados fictícios criados em',DB)
    elif arg.command=='admin':
        pw=getpass.getpass('Senha (12+ caracteres): ')
        if pw!=getpass.getpass('Confirme a senha: '): raise SystemExit('Senhas diferentes.')
        with connection() as c: create_user(c,arg.name,email({'email':arg.email}),pw,'admin')
        print('Administrador criado.')
    else:
        print(f'CT Pulse em http://{arg.host}:{arg.port} | banco {DB}',flush=True)
        with make_server(arg.host,arg.port,app,server_class=ThreadServer) as server: server.serve_forever()
