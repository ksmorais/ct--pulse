import io,json,os,sys,tempfile,unittest,datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
class Client:
    def __init__(self): self.cookie='';self.csrf=''
    def req(self,path,data=None,expected=200,csrf=True):
        body=json.dumps(data).encode() if data is not None else b''; env={'REQUEST_METHOD':'GET' if data is None else 'POST','PATH_INFO':'/api/'+path,'CONTENT_LENGTH':str(len(body)),'CONTENT_TYPE':'application/json','wsgi.input':io.BytesIO(body),'HTTP_COOKIE':self.cookie,'HTTP_X_CSRF_TOKEN':self.csrf if csrf else '', 'REMOTE_ADDR':'127.0.0.1'}; result={}
        def respond(s,h): result.update(status=int(s.split()[0]),headers=h)
        obj=json.loads(b''.join(server.app(env,respond))); assert result['status']==expected,(path,result['status'],obj)
        for k,v in result['headers']:
            if k=='Set-Cookie': self.cookie=v.split(';')[0]
        if 'csrf' in obj:self.csrf=obj['csrf']
        return obj
    def login(self,email,pw): return self.req('login',{'email':email,'password':pw})
class TestCT(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();server.DB=Path(cls.tmp.name)/'test.sqlite';server.init();server.seed_demo()
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def test_complete_cross_device_flow(self):
        a,t,s,other=Client(),Client(),Client(),Client();a.login('admin@ctpulse.com','DemoAdmin2026!');t.login('prof@ctpulse.com','DemoProfessor2026!');s.login('aluno@ctpulse.com','DemoAluno2026!');other.login('joao@ctpulse.com','DemoJoao2026!');
        admin=a.req('state'); stu=s.req('state'); sid=stu['user']['id'];cid=stu['classes'][0]['id']; cid=stu['enrollments'][0]['class_id'];oid=other.req('state')['user']['id'];
        self.assertEqual(len(stu['students']),1);self.assertTrue(all(p['student_id']==sid for p in stu['payments']));self.assertFalse(t.req('state')['payments']);
        s.req('payment/mark',{'id':stu['payments'][0]['id'],'status':'paid'},403);s.req('notice',{'title':'x','body':'x','class_id':cid},403);a.req('payment/generate',{'month':server.today()[:7],'due':server.today()[:7]+'-20'},403,csrf=False)
        a.req('user/save',{'name':'Novo Aluno','email':'teste@ctpulse.com','password':'SenhaNova2026!','role':'student','plan_cents':20000}); new=Client();new.login('teste@ctpulse.com','SenhaNova2026!'); nid=new.req('state')['user']['id'];
        new.req('enrollment',{'class_id':cid,'student_id':oid,'active':1});self.assertTrue(any(x['student_id']==nid for x in a.req('state')['enrollments']));
        days=next(x for x in stu['classes'] if x['id']==cid)['days']; d=dt.date.fromisoformat(server.today());d+=dt.timedelta(days=next(i for i in range(7) if ((d+dt.timedelta(days=i)).weekday()+1)%7 in days));
        new.req('booking',{'class_id':cid,'date':d.isoformat()});new.req('booking',{'class_id':cid,'date':d.isoformat()}); b=new.req('state')['bookings'];self.assertEqual(len(b),1);other.req('booking/cancel',{'id':b[0]['id']},404);
        t.req('attendance',{'class_id':cid,'student_id':nid,'date':server.today(),'present':1});self.assertEqual(new.req('state')['attendance'][0]['present'],1)
        t.req('grade',{'student_id':nid,'belt':'Amarela','note':'Teste'});self.assertEqual(new.req('state')['user']['belt'],'Amarela')
        t.req('notice',{'class_id':cid,'title':'Treino teste','body':'Treino às 18h'}); notices=new.req('state')['notices'];self.assertEqual(notices[0]['title'],'Treino teste');new.req('notice/read',{'id':notices[0]['id']});self.assertIsNotNone(new.req('state')['notices'][0]['read_at']);
        pid=new.req('state')['payments'][0]['id'];a.req('payment/mark',{'id':pid,'status':'paid'});self.assertEqual(new.req('state')['payments'][0]['status'],'paid')
        # separate connection and fresh session prove persistent, shared database
        new2=Client();new2.login('teste@ctpulse.com','SenhaNova2026!');self.assertEqual(new2.req('state')['payments'][0]['status'],'paid');
        a.req('user/active',{'id':nid,'active':0});new.req('state',expected=401);new2.req('state',expected=401)
    def test_auth_and_validation(self):
        c=Client();c.req('state',expected=401);c.req('login',{'email':'admin@ctpulse.com','password':'bad'},401);c.login('admin@ctpulse.com','DemoAdmin2026!');c.req('user/save',{'role':'admin','name':'X','email':'x@x.com','password':'Password1234'},400);c.req('logout',{});c.req('state',expected=401)
if __name__=='__main__':unittest.main()
