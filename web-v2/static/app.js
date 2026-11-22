'use strict';
const $=id=>document.getElementById(id), app=$('app'), modal=$('modal');
let S=null, page='home', csrf='', toastTimer, currentSubmit, busy=false, filter={}, signupEnabled=false;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>(Number(v||0)/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'}), date=v=>v?String(v).slice(0,10).split('-').reverse().join('/'):'—', weekdays=['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'], roles={admin:'Administrador',teacher:'Professor',student:'Aluno'};
const pill=(v,kind='')=>`<span class="pill ${kind}">${esc(v)}</span>`;
const btn=(label,action,id='',primary=false)=>`<button type="button" class="${primary?'primary':''}" data-action="${esc(action)}" data-id="${esc(id)}">${esc(label)}</button>`;
const card=(title,html)=>`<section class="card"><h2>${esc(title)}</h2>${html}</section>`;
const empty=msg=>`<p class="empty">${esc(msg)}</p>`;
const row=(title,sub,action='')=>`<div class="list-row"><div><p>${esc(title)}</p><small>${esc(sub)}</small></div><div class="actions">${action}</div></div>`;
const stat=(title,v,sub='')=>`<div class="card stat"><small>${esc(title)}</small><strong>${esc(v)}</strong><small>${esc(sub)}</small></div>`;
const find=(list,id)=>S[list].find(x=>x.id===Number(id)), cls=id=>find('classes',id)?.name||'Turma', student=id=>find('students',id)?.name||'Aluno';
function toast(msg){$('toast').textContent=msg;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').textContent='',4500)}
async function api(path,data){const response=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',credentials:'same-origin',headers:data===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:data===undefined?undefined:JSON.stringify(data)});const p=await response.json();if(!response.ok){if(response.status===401&&path!=='login'){S=null;csrf='';if(modal.open)modal.close();loginView();}throw new Error(p.error||'Falha de comunicação.')}return p}
async function refresh(renderNow=true){S=await api('state');csrf=S.csrf;if(renderNow)render()}
async function mutate(path,data){await api(path,data);await refresh();toast('Alteração salva no banco de dados.');}
function loginView(){const signupLink=signupEnabled?'<div class="auth-switch"><span>Novo no CT Pulse?</span><button type="button" id="go-register" class="auth-link">Criar conta de aluno</button></div>':'';app.innerHTML=`<div class="login"><section class="login-hero"><div class="brand"><span class="logo">CT</span> CT PULSE</div><h1>Seu treino.<br>Sua evolução.</h1><p>Gestão de centros de treinamento, do controle administrativo ao acompanhamento de cada aluno.</p></section><main class="login-main"><form id="login"><span class="eyebrow">Área segura</span><h1>Bem-vindo de volta</h1><p class="muted">Acesse sua conta para continuar.</p><label class="field" for="email">E-mail</label><input id="email" name="email" type="email" autocomplete="username" required><label class="field" for="password">Senha</label><input id="password" name="password" type="password" autocomplete="current-password" required><p id="login-success" class="auth-success" role="status" aria-live="polite"></p><p class="error" id="login-error" role="alert"></p><button class="primary">Entrar no CT Pulse</button>${signupLink}<p class="muted"><small>Os dados são compartilhados entre dispositivos conectados ao mesmo servidor.</small></p></form></main></div>`;if(signupEnabled)$('go-register').onclick=registerView;$('login').onsubmit=async e=>{e.preventDefault();let b=e.target.querySelector('button');b.disabled=true;try{const d=Object.fromEntries(new FormData(e.target));let r=await api('login',d);csrf=r.csrf;page='home';filter={};await refresh()}catch(err){if($('login-error'))$('login-error').textContent=err.message}finally{b.disabled=false}}}
function registerView(){
  app.innerHTML='<div class="login"><section class="login-hero"><div class="brand"><span class="logo">CT</span> CT PULSE</div><h1>Faça parte do CT Pulse.</h1><p>Crie sua conta de aluno para consultar turmas, agendar aulas e acompanhar seus treinos.</p></section><main class="login-main"><form id="register"><span class="eyebrow">Cadastro de aluno</span><h1>Crie sua conta</h1><p class="muted">Cadastre-se gratuitamente na demonstração.</p><label class="field" for="reg-name">Nome</label><input id="reg-name" name="name" type="text" maxlength="150" autocomplete="name" required><label class="field" for="reg-email">E-mail</label><input id="reg-email" name="email" type="email" maxlength="254" autocomplete="email" required><label class="field" for="reg-password">Senha (mínimo de 12 caracteres)</label><input id="reg-password" name="password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required><label class="field" for="reg-confirm">Confirmar senha</label><input id="reg-confirm" name="confirm" type="password" minlength="12" maxlength="128" autocomplete="new-password" required><p class="auth-hint">Ambiente demonstrativo: use apenas dados fictícios. O cadastro não verifica a titularidade do e-mail e os dados podem ser apagados quando o serviço reiniciar.</p><p class="error" id="register-error" role="alert"></p><button type="submit" class="primary">Criar minha conta</button><button type="button" id="go-login" class="auth-link">Já tenho conta · Entrar</button></form></main></div>';
  $('go-login').onclick=loginView;
  $('register').onsubmit=async e=>{
    e.preventDefault();
    const data=Object.fromEntries(new FormData(e.target));
    const b=e.target.querySelector('button[type="submit"]');
    const err=$('register-error');
    err.textContent='';
    if(data.password!==data.confirm){err.textContent='As senhas não coincidem.';return;}
    if(!signupEnabled){err.textContent='Cadastro indisponível.';return;}
    b.disabled=true;
    try{
      await api('register',{name:data.name,email:data.email,password:data.password});
      loginView();
      $('email').value=data.email.trim();
      $('login-success').textContent='Conta criada! Faça login com seu e-mail e sua senha.';
      $('password').focus();
    }catch(ex){err.textContent=ex.message;}
    finally{b.disabled=false;}
  };
}
const navs={admin:[['home','Início','⌂'],['students','Alunos','♟'],['teachers','Professores','◉'],['classes','Turmas','▦'],['attendance','Chamada','✓'],['finance','Financeiro','R$'],['news','Avisos','✉'],['profile','Perfil','♙']],teacher:[['home','Início','⌂'],['classes','Turmas','▦'],['attendance','Chamada','✓'],['grades','Graduação','★'],['news','Avisos','✉'],['profile','Perfil','♙']],student:[['home','Início','⌂'],['classes','Turmas','▦'],['schedule','Agenda','▤'],['finance','Mensalidade','R$'],['news','Avisos','✉'],['profile','Perfil','♙']]};
function render(){if(!S)return loginView();const u=S.user,n=navs[u.role],body=views[page]?.()||views.home();app.innerHTML=`<div class="mobile-head"><div class="brand"><span class="logo">CT</span> CT PULSE</div>${btn('Sair','logout')}</div><div class="shell"><aside class="sidebar"><div class="brand"><span class="logo">CT</span> CT PULSE</div><nav class="nav" aria-label="Menu principal">${n.map(([k,t,s])=>`<button data-action="nav" data-id="${k}" class="${k===page?'active':''}" ${k===page?'aria-current="page"':''}><span class="symbol" aria-hidden="true">${s}</span><span>${t}</span></button>`).join('')}</nav><div class="account"><p>${esc(u.name)}</p><small>${roles[u.role]}</small>${btn('Sair','logout')}</div></aside><main class="main"><div class="top"><div><span class="eyebrow">CT Pulse / ${roles[u.role]}</span><h1>${esc(n.find(x=>x[0]===page)?.[1]||'Início')}</h1><small>${date(S.today)} · Dados centralizados</small></div>${btn('Atualizar ↻','refresh')}</div>${body}</main></div>`;if(page==='students'||page==='teachers'){$('search').oninput=e=>{filter.search=e.target.value;$('results').innerHTML=userRows(page==='teachers'?'teacher':'student')}}if(page==='students'&&S.user.role==='admin'&&S.native_students_lab)loadNativeStudents();if((page==='teachers'||page==='classes')&&S.user.role==='admin'&&S.native_students_lab)loadNativeAcademy();}
function nextDate(c){for(let i=0;i<8;i++){let d=new Date(S.today+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+i);if(c.days.includes(d.getUTCDay()))return d.toISOString().slice(0,10)}return S.today}
const views={home(){let u=S.user,admin=u.role==='admin',stu=u.role==='student',paid=S.payments.filter(x=>x.status==='paid').reduce((a,b)=>a+b.amount_cents,0),pending=S.payments.filter(x=>x.status==='pending').reduce((a,b)=>a+b.amount_cents,0);return `<section class="hero"><span class="eyebrow">Seu centro de treinamento</span><h2>Olá, ${esc(u.name.split(' ')[0])}!</h2><p>${stu?'Confira sua agenda, mensalidade e evolução.':'Acompanhe os dados e as atividades do CT em um só lugar.'}</p></section><div class="grid">${stu?stat('Turmas inscritas',S.enrollments.length)+stat('Aulas agendadas',S.bookings.filter(b=>b.date>=S.today).length)+stat('Presenças',S.attendance.filter(a=>a.present).length)+stat('Graduação',u.belt):stat('Alunos ativos',S.students.filter(s=>s.active).length)+stat('Turmas',S.classes.length)+ (admin?stat('Recebido (total)',money(paid))+stat('Pendente (total)',money(pending)):stat('Presenças registradas',S.attendance.filter(a=>a.present).length))}</div>${card('Comunicados recentes',S.notices.slice(0,3).map(n=>row(n.title,n.author+' · '+date(n.created_at))).join('')||empty('Nenhum comunicado.'))}${card(stu?'Próximas aulas':'Turmas',S.classes.slice(0,4).map(c=>row(c.name,c.days.map(d=>weekdays[d]).join(' / ')+' · '+c.time+' · '+c.teacher)).join('')||empty('Nenhuma turma cadastrada.'))}`},students(){const lab=S.native_students_lab?'<section class="card native-lab"><div class="top"><div><h2>Laboratório Firestore — alunos fictícios</h2><p class="muted">Cadastros separados da lista principal. Não geram conta de login, mensalidade ou inscrição.</p></div><div class="actions">'+btn('Recarregar','native-reload')+btn('+ Aluno de teste','native-new','',true)+'</div></div><div id="native-students-results" aria-live="polite">Carregando dados de teste…</div></section>':'';return `<div class="top"><input class="search" id="search" aria-label="Buscar aluno" placeholder="Buscar aluno…" value="${esc(filter.search||'')}">${btn('+ Novo aluno','user-new','student',true)}</div><section class="card" id="results">${userRows('student')}</section>${lab}`},teachers(){return `<div class="top"><input class="search" id="search" aria-label="Buscar professor" placeholder="Buscar professor…" value="${esc(filter.search||'')}">${btn('+ Novo professor','user-new','teacher',true)}</div><section class="card" id="results">${userRows('teacher')}</section>${S.user.role==='admin'&&S.native_students_lab?nativeAcademyPanel('teachers'):''}`},classes(){let admin=S.user.role==='admin',stu=S.user.role==='student';return `<div class="top"><p class="muted">Grade de horários e disponibilidade.</p>${admin?btn('+ Nova turma','class-edit','',true):''}</div><div class="class-grid">${S.classes.map(c=>{let en=S.enrollments.some(e=>e.class_id===c.id&&e.student_id===S.user.id);return `<section class="card">${pill(c.enrolled_count+' / '+c.capacity+' alunos',c.enrolled_count>=c.capacity?'warn':'')}<h2>${esc(c.name)}</h2><p class="muted">${esc(c.teacher)} · ${c.days.map(d=>weekdays[d]).join(', ')} · ${esc(c.time)}</p><div class="actions">${admin?btn('Editar','class-edit',c.id)+btn('Gerenciar inscrições','enroll-admin',c.id):stu?btn(en?'Cancelar inscrição':'Inscrever-se','enroll',c.id,!en)+(en?btn('Agendar aula','book',c.id,true):''):btn('Ver chamada','class-attendance',c.id,true)}</div></section>`}).join('')||empty('Nenhuma turma disponível.')}</div>${admin&&S.native_students_lab?nativeAcademyPanel('classes'):''}`},attendance(){let cid=Number(filter.classId)||S.classes[0]?.id, day=filter.day||S.today;return `<div class="filter"><label>Turma<select id="att-class" data-filter="classId">${S.classes.map(c=>`<option value="${c.id}" ${c.id===cid?'selected':''}>${esc(c.name)}</option>`).join('')}</select></label><label>Data<input type="date" id="att-day" value="${esc(day)}" max="${S.today}" data-filter="day"></label></div>${card('Lista de chamada',S.enrollments.filter(e=>e.class_id===cid).map(e=>{let a=S.attendance.find(x=>x.class_id===cid&&x.student_id===e.student_id&&x.date===day);return row(student(e.student_id),a?(a.present?'Presente':'Ausente'):'Ainda não registrado',btn('Presente','presence',`${cid}:${e.student_id}:1`,a?.present===1)+btn('Ausente','presence',`${cid}:${e.student_id}:0`,a?.present===0))}).join('')||empty('Nenhum aluno inscrito nesta turma.'))}`},schedule(){return card('Aulas agendadas',S.bookings.sort((a,b)=>a.date.localeCompare(b.date)).map(b=>row(cls(b.class_id),date(b.date),btn('Cancelar','booking-cancel',b.id))).join('')||empty('Inscreva-se em uma turma e agende um treino.'))+card('Minha frequência',S.attendance.map(a=>row(cls(a.class_id),date(a.date),pill(a.present?'Presente':'Ausente',a.present?'':'warn'))).join('')||empty('Nenhuma frequência registrada.'))},finance(){
  const admin=S.user.role==='admin',methods={pix:'Pix',boleto:'Boleto',card:'Cartão'};
  const intro=admin?'Controle de mensalidades e baixas manuais.':'Consulte suas mensalidades e escolha um método de pagamento demonstrativo.';
  const note=S.payments_demo?'<p class="demo-note"><strong>Modo demonstração:</strong> Pix, boleto e cartão são apenas opções simuladas. Nenhuma cobrança, QR Code, boleto ou transação real é emitida.</p>':'';
  const items=S.payments.map(p=>{
    const req=(S.payment_requests||[]).find(x=>x.payment_id===p.id);
    const detail=p.month+' · Vence em '+date(p.due)+(req?' · Método solicitado (demo): '+(methods[req.method]||'—'):'');
    const status=pill(p.status==='paid'?'Pago':'Pendente',p.status==='paid'?'':'warn');
    const choose=S.payments_demo&&p.status==='pending'&&p.amount_cents>0?btn('Escolher pagamento (demo)','payment-options',p.id):'';
    const mark=admin?btn(p.status==='paid'?'Estornar registro':'Registrar baixa manual','payment',p.id):'';
    return row((admin?student(p.student_id)+' · ':'')+money(p.amount_cents),detail,status+choose+mark);
  }).join('');
  return '<div class="top"><p class="muted">'+intro+'</p>'+(admin?btn('Gerar mensalidades','payment-generate','',true):'')+'</div>'+note+card('Mensalidades',items||empty('Nenhuma mensalidade cadastrada.'));
},grades(){return card('Registrar evolução',S.students.map(s=>row(s.name,s.belt,btn('Nova graduação','grade',s.id,true))).join('')||empty('Nenhum aluno nas suas turmas.'))+card('Histórico',S.grades.map(g=>row(student(g.student_id)+' · '+g.belt,date(g.date)+' · '+g.note)).join('')||empty('Nenhuma graduação registrada.'))},news(){
  const stu=S.user.role==='student',admin=S.user.role==='admin';
  const header='<div class="top"><p class="muted">Comunicados compartilhados entre dispositivos.</p>'+(!stu?btn('+ Novo comunicado','notice','',true):'')+'</div>';
  const items=S.notices.map(n=>{
    const canEdit=admin||(!stu&&n.author_id===S.user.id);
    const tools=canEdit?'<div class="notice-actions">'+btn('Editar','notice-edit',n.id)+btn('Excluir','notice-delete',n.id)+'</div>':'';
    const read=stu&&!n.read_at?btn('Marcar como lido','read',n.id):'';
    return '<article class="card"><div class="notice-title"><h2>'+esc(n.title)+'</h2>'+(stu&&!n.read_at?pill('Novo','warn'):'')+'</div><small>'+esc(n.author)+' · '+date(n.created_at)+(n.class_id?' · '+esc(cls(n.class_id)):'')+'</small><p class="notice-body">'+esc(n.body)+'</p>'+tools+read+'</article>';
  }).join('');
  return header+(items||empty('Nenhum aviso por enquanto.'));
},profile(){const u=S.user;return card('Minha conta',row(u.name,u.email,pill(roles[u.role]))+btn('Alterar senha','password'))+(u.role==='student'?card('Minha evolução',row('Graduação atual',u.belt)+S.grades.map(g=>row(g.belt,date(g.date)+' · '+g.note)).join('')):'')+card('Acesso em outros dispositivos','<p class="muted">Abra o mesmo endereço no computador ou celular. Use a opção “Adicionar à tela de início” do navegador quando disponível. O acesso exige conexão com o servidor.</p>')}};
let nativeStudents=[];
function nativeStudentRows(){
  return nativeStudents.map(s=>row(s.name,
    s.email+' · '+money(s.plan_cents)+' · '+s.belt+' · '+(s.active?'Ativo':'Inativo'),
    btn('Editar','native-edit',s.id)+btn(s.active?'Desativar':'Reativar','native-toggle',s.id)
  )).join('')||empty('Nenhum aluno fictício criado neste laboratório.');
}
async function loadNativeStudents(){
  const node=$('native-students-results');
  if(!node||!S?.native_students_lab)return;
  node.textContent='Carregando dados do Firestore…';
  try{
    const result=await api('native-students');
    nativeStudents=Array.isArray(result.students)?result.students:[];
    if(node.isConnected)node.innerHTML=nativeStudentRows();
  }catch(error){
    if(node.isConnected)node.textContent='Não foi possível carregar o laboratório: '+error.message;
  }
}
let nativeAcademy={teachers:[],classes:[],enrollments:[]};
function nativeAcademyPanel(kind){
  const isTeachers=kind==='teachers';
  const action=isTeachers?btn('+ Professor de teste','native-teacher-new','',true):btn('+ Turma de teste','native-class-new','',true);
  return '<section class="card native-lab"><div class="top"><div><h2>Laboratório Firestore — '+(isTeachers?'professores':'turmas e inscrições')+'</h2><p class="muted">Registros fictícios separados do CT Pulse principal. Não criam contas ou cobranças reais.</p></div><div class="actions">'+btn('Recarregar','native-academy-reload')+action+'</div></div><div id="native-academy-results" aria-live="polite">Carregando laboratório…</div></section>';
}
function nativeAcademyRows(){
  if(page==='teachers'){
    return nativeAcademy.teachers.map(t=>row(t.name,t.email+' · Sem conta de login',pill(t.active?'Ativo':'Inativo',t.active?'':'gray'))).join('')||empty('Nenhum professor de teste cadastrado.');
  }
  return nativeAcademy.classes.map(c=>{
    const teacher=nativeAcademy.teachers.find(t=>t.id===c.teacher_id);
    const booked=nativeAcademy.enrollments.filter(e=>e.class_id===c.id);
    return row(c.name,
      (teacher?.name||'Professor')+' · '+c.days.map(d=>weekdays[d]).join(', ')+' '+c.time+' · '+c.enrolled_count+'/'+c.capacity+' inscritos (teste)',
      btn('Editar turma','native-class-edit',c.id)+btn('Gerenciar inscrições','native-class-enroll',c.id));
  }).join('')||empty('Nenhuma turma de teste cadastrada.');
}
async function loadNativeAcademy(){
  const node=$('native-academy-results');
  if(!node||!S?.native_students_lab)return;
  node.textContent='Carregando registros nativos…';
  try{
    const [academy,studentResult]=await Promise.all([api('native-academy'),api('native-students')]);
    nativeAcademy=academy;
    nativeStudents=Array.isArray(studentResult.students)?studentResult.students:[];
    if(node.isConnected)node.innerHTML=nativeAcademyRows();
  }catch(error){
    if(node.isConnected)node.textContent='Não foi possível carregar o laboratório: '+error.message;
  }
}
function nativeDaysInputs(selected=[1,3,5]){
  return '<p class="label">Dias da semana</p><div class="checkboxes">'+weekdays.map((day,i)=>
    '<label><input type="checkbox" name="native_days" value="'+i+'" '+(selected.includes(i)?'checked':'')+'>'+esc(day)+'</label>'
  ).join('')+'</div>';
}
function userRows(role){return S[role==='teacher'?'teachers':'students'].filter(s=>(s.name+' '+s.email).toLowerCase().includes((filter.search||'').toLowerCase())).map(s=>row(s.name,role==='student'?s.email+' · '+s.belt+' · '+money(s.plan_cents):s.email,pill(s.active?'Ativo':'Inativo',s.active?'':'gray')+btn('Editar','user-edit',`${role}:${s.id}`)+(role==='student'?btn('Graduação','grade',s.id):'')+btn(s.active?'Desativar':'Reativar','active',`${role}:${s.id}`))).join('')||empty('Nenhum cadastro encontrado.')}
function field(name,label,value='',type='text',extra=''){return `<label class="field" for="f-${name}">${esc(label)}</label><input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" ${extra}>`}
function select(name,label,opts,v){return `<label class="field" for="f-${name}">${esc(label)}</label><select id="f-${name}" name="${name}" required>${opts.map(([key,text])=>`<option value="${esc(key)}" ${String(v)===String(key)?'selected':''}>${esc(text)}</option>`).join('')}</select>`}
function area(name,label,value=''){return `<label class="field" for="f-${name}">${esc(label)}</label><textarea id="f-${name}" name="${name}" required maxlength="2000">${esc(value)}</textarea>`}
function open(title,html,submit,label='Salvar'){$('modal-title').textContent=title;$('fields').innerHTML=html;$('form-error').textContent='';currentSubmit=submit;$('modal-form').querySelector('button[type=submit]').textContent=label;modal.showModal()}
$('close').onclick=()=>modal.close();$('modal-form').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;let b=e.target.querySelector('button[type=submit]');b.disabled=true;try{await currentSubmit(new FormData(e.target));modal.close()}catch(err){$('form-error').textContent=err.message}finally{busy=false;b.disabled=false}};
async function handle(action,id){let u=S.user;switch(action){case 'nav':page=id;filter={};render();return;case 'refresh':await refresh();toast('Dados atualizados.');return;case 'logout':await api('logout',{});S=null;csrf='';loginView();return;case 'native-academy-reload':await loadNativeAcademy();return;
case 'native-teacher-new':{
  if(!S.native_students_lab||u.role!=='admin')throw Error('Laboratório indisponível.');
  open('Professor fictício · Firestore',
    '<p class="demo-note">Professor de teste sem senha ou acesso ao CT Pulse.</p>'+
    field('name','Nome fictício','','text','required maxlength="150"')+
    field('email','E-mail fictício','','email','required maxlength="254"'),
    async f=>{
      await api('native-academy/teacher/create',{name:f.get('name'),email:f.get('email')});
      await loadNativeAcademy();toast('Professor fictício salvo no Firestore.');
    },'Criar professor de teste');
  return;
}
case 'native-class-new':{
  if(!S.native_students_lab||u.role!=='admin')throw Error('Laboratório indisponível.');
  const teachers=nativeAcademy.teachers.filter(x=>x.active);
  if(!teachers.length)throw Error('Cadastre primeiro um professor no laboratório.');
  open('Turma fictícia · Firestore',
    '<p class="demo-note">Turma isolada: não modifica a grade principal.</p>'+
    field('name','Nome da turma','','text','required maxlength="150"')+
    select('teacher','Professor fictício',teachers.map(t=>[t.id,t.name]))+
    field('time','Horário','18:00','time','required')+
    field('capacity','Vagas',12,'number','required min="1" max="100" step="1"')+
    nativeDaysInputs(),
    async f=>{
      await api('native-academy/class/create',{
        name:f.get('name'),teacher_id:f.get('teacher'),
        time:f.get('time'),capacity:Number(f.get('capacity')),
        days:f.getAll('native_days').map(Number)});
      await loadNativeAcademy();toast('Turma fictícia salva.');
    },'Criar turma de teste');
  return;
}
case 'native-class-edit':{
  if(!S.native_students_lab||u.role!=='admin')throw Error('Laboratório indisponível.');
  const course=nativeAcademy.classes.find(x=>x.id===id);
  if(!course)throw Error('Turma fictícia não encontrada.');
  open('Editar turma fictícia · Firestore',
    field('name','Nome da turma',course.name,'text','required maxlength="150"')+
    field('time','Horário',course.time,'time','required')+
    field('capacity','Vagas',course.capacity,'number','required min="1" max="100" step="1"')+
    nativeDaysInputs(course.days),
    async f=>{
      await api('native-academy/class/update',{
        id:course.id,name:f.get('name'),time:f.get('time'),
        capacity:Number(f.get('capacity')),days:f.getAll('native_days').map(Number)
      });
      await loadNativeAcademy();toast('Turma fictícia atualizada.');
    });
  return;
}
case 'native-class-enroll':{
  if(!S.native_students_lab||u.role!=='admin')throw Error('Laboratório indisponível.');
  const course=nativeAcademy.classes.find(x=>x.id===id);
  if(!course)throw Error('Turma não encontrada.');
  if(!nativeStudents.length)throw Error('Cadastre um aluno no laboratório Firestore antes de inscrever.');
  const current=nativeAcademy.enrollments.filter(e=>e.class_id===course.id);
  open('Inscrições fictícias · '+course.name,
    '<p class="demo-note">Inscrições transacionais na turma de teste: '+course.enrolled_count+'/'+course.capacity+' vagas ocupadas. Sem agendamento ou cobrança.</p>'+
    select('student','Aluno fictício',nativeStudents.map(s=>[s.id,s.name]))+
    select('active','Ação',[[1,'Inscrever'],[0,'Cancelar inscrição']])+
    '<p class="muted">Inscritos atualmente: '+(current.length?current.map(e=>esc(nativeStudents.find(s=>s.id===e.student_id)?.name||'Aluno')).join(', '):'nenhum')+'</p>',
    async f=>{
      await api('native-academy/enrollment',{
        student_id:f.get('student'),class_id:course.id,active:Number(f.get('active'))});
      await loadNativeAcademy();toast('Inscrição demonstrativa atualizada.');
    },'Confirmar ação fictícia');
  return;
}
case 'native-reload':await loadNativeStudents();return;
case 'native-new':{
  if(!S.native_students_lab||u.role!=='admin')throw Error('Laboratório indisponível.');
  open('Novo aluno fictício · Firestore',
    '<p class="demo-note">Somente teste: não cria senha, login ou inscrição no CT Pulse.</p>'+
    field('name','Nome fictício','','text','required maxlength="150"')+
    field('email','E-mail fictício','','email','required maxlength="254"')+
    field('plan','Plano demonstrativo (R$)',0,'number','required min="0" max="100000" step="0.01"'),
    async form=>{
      await api('native-students/create',{
        name:form.get('name'),email:form.get('email'),
        plan_cents:Math.round(Number(form.get('plan'))*100)
      });
      await loadNativeStudents();
      toast('Aluno de teste gravado no Firestore nativo.');
    },'Criar registro de teste');
  return;
}
case 'native-edit':{
  if(!S.native_students_lab||u.role!=='admin')throw Error('Laboratório indisponível.');
  const s=nativeStudents.find(x=>x.id===id);
  if(!s)throw Error('Aluno de teste não encontrado.');
  open('Editar aluno fictício · Firestore',
    field('name','Nome fictício',s.name,'text','required maxlength="150"')+
    field('plan','Plano demonstrativo (R$)',s.plan_cents/100,'number','required min="0" max="100000" step="0.01"')+
    select('belt','Faixa', ['Branca','Amarela','Laranja','Verde','Azul','Marrom','Preta'].map(x=>[x,x]),s.belt),
    async form=>{
      await api('native-students/update',{
        id:s.id,name:form.get('name'),
        plan_cents:Math.round(Number(form.get('plan'))*100),belt:form.get('belt')
      });
      await loadNativeStudents();
      toast('Cadastro fictício atualizado.');
    },'Salvar registro de teste');
  return;
}
case 'native-toggle':{
  if(!S.native_students_lab||u.role!=='admin')throw Error('Laboratório indisponível.');
  const s=nativeStudents.find(x=>x.id===id);
  if(!s)throw Error('Aluno de teste não encontrado.');
  if(confirm((s.active?'Desativar':'Reativar')+' registro fictício '+s.name+'?')){
    await api('native-students/update',{id:s.id,active:s.active?0:1});
    await loadNativeStudents();
    toast('Situação fictícia atualizada.');
  }
  return;
}
case 'user-new':case 'user-edit':{let [role,sid]=id.split(':'),s=sid?find(role==='student'?'students':'teachers',sid):null;open(s?'Editar cadastro':'Novo '+(role==='student'?'aluno':'professor'),field('name','Nome',s?.name,'text','required maxlength="150"')+field('email','E-mail',s?.email,'email','required')+field('password',s?'Nova senha (opcional)':'Senha inicial (12+ caracteres)','','password',(s?'':'required ')+'minlength="12" maxlength="128" autocomplete="new-password"')+(role==='student'?field('plan','Mensalidade (R$)',s?s.plan_cents/100:159,'number','required min="0" max="100000" step="0.01"'):''),async f=>mutate('user/save',{id:s?.id,role,name:f.get('name'),email:f.get('email'),password:f.get('password'),plan_cents:Math.round(Number(f.get('plan')||0)*100)}));return}
case 'active':{let [role,sid]=id.split(':'),s=find(role==='student'?'students':'teachers',sid);if(confirm(`${s.active?'Desativar':'Reativar'} ${s.name}?`))await mutate('user/active',{id:s.id,active:s.active?0:1});return}
case 'class-edit':{let c=find('classes',id),teachers=S.teachers.filter(t=>t.active);if(!teachers.length)throw Error('Cadastre um professor ativo antes.');open(c?'Editar turma':'Nova turma',field('name','Nome da turma',c?.name,'text','required')+select('teacher','Professor',teachers.map(t=>[t.id,t.name]),c?.teacher_id)+field('time','Horário',c?.time||'18:00','time','required')+field('capacity','Capacidade',c?.capacity||16,'number','required min="1" max="1000"')+`<p class="label">Dias da semana</p><div class="checkboxes">${weekdays.map((d,i)=>`<label><input type="checkbox" name="days" value="${i}" ${(c?.days||[1,3,5]).includes(i)?'checked':''}>${d}</label>`).join('')}</div>`,f=>mutate('class/save',{id:c?.id,name:f.get('name'),teacher_id:Number(f.get('teacher')),time:f.get('time'),capacity:Number(f.get('capacity')),days:f.getAll('days').map(Number)}));return}
case 'enroll-admin':{let c=find('classes',id);open('Inscrições · '+c.name,select('student','Aluno',S.students.filter(s=>s.active).map(s=>[s.id,s.name]))+select('active','Ação',[[1,'Inscrever'],[0,'Cancelar inscrição']]),f=>mutate('enrollment',{class_id:c.id,student_id:Number(f.get('student')),active:Number(f.get('active'))}));return}
case 'enroll':{let cid=Number(id),en=S.enrollments.some(e=>e.class_id===cid&&e.student_id===u.id);if(!en||confirm('Cancelar inscrição e agendamentos futuros?'))await mutate('enrollment',{class_id:cid,active:en?0:1});return}
case 'book':{let c=find('classes',id);open('Agendar '+c.name,field('date','Data da aula',nextDate(c),'date',`required min="${S.today}"`),f=>mutate('booking',{class_id:c.id,date:f.get('date')}),'Agendar');return}
case 'booking-cancel':if(confirm('Cancelar este agendamento?'))await mutate('booking/cancel',{id:Number(id)});return;
case 'class-attendance':page='attendance';filter={classId:Number(id)};render();return;
case 'presence':{let [cid,sid,p]=id.split(':').map(Number);await mutate('attendance',{class_id:cid,student_id:sid,present:p,date:filter.day||S.today});return}
case 'payment-generate':open('Gerar mensalidades',field('month','Mês de referência',S.today.slice(0,7),'month','required')+field('due','Vencimento',S.today.slice(0,7)+'-20','date','required')+'<p class="muted">Gera mensalidades dos alunos ativos sem duplicar as já existentes.</p>',f=>mutate('payment/generate',{month:f.get('month'),due:f.get('due')}));return;
case 'payment-options':{
  const p=find('payments',id);
  if(!S.payments_demo)throw Error('O modo de pagamento demonstrativo está desativado.');
  if(!p||p.status!=='pending'||p.amount_cents<=0)throw Error('Não existe mensalidade pendente válida.');
  open('Escolher pagamento · DEMONSTRAÇÃO',
    '<p class="demo-note"><strong>Atenção:</strong> esta opção apenas registra uma simulação. Não emite Pix pagável, boleto bancário ou cobrança de cartão.</p>'+
    '<p>Valor da mensalidade: <strong>'+money(p.amount_cents)+'</strong></p>'+
    select('method','Forma de pagamento',[['pix','Pix (simulado)'],['boleto','Boleto (simulado)'],['card','Cartão (simulado)']]),
    async form=>{
      await mutate('payment/request',{id:p.id,method:form.get('method')});
      toast('Método demonstrativo registrado. Nenhum pagamento foi gerado.');
    },'Registrar simulação');
  return;
}
case 'payment':{let p=find('payments',id);if(confirm(p.status==='paid'?'Reverter a baixa registrada?':'Confirma que recebeu o valor fora do sistema? Nenhuma transação será efetuada.'))await mutate('payment/mark',{id:p.id,status:p.status==='paid'?'pending':'paid'});return}
case 'grade':{let s=find('students',id);open('Graduação · '+s.name,select('belt','Faixa',['Branca','Amarela','Laranja','Verde','Azul','Marrom','Preta'].map(x=>[x,x]),s.belt)+area('note','Observações da avaliação'),f=>mutate('grade',{student_id:s.id,belt:f.get('belt'),note:f.get('note')}));return}
case 'notice':open('Publicar comunicado',field('title','Título','','text','required maxlength="150"')+area('body','Mensagem')+select('class','Destinatários',[...(u.role==='admin'?[['','Todos os alunos ativos']]:[]),...S.classes.map(c=>[c.id,c.name])]),f=>mutate('notice',{title:f.get('title'),body:f.get('body'),class_id:f.get('class')?Number(f.get('class')):null}),'Publicar');return;
case 'notice-edit':{
  const n=find('notices',id);
  if(!n)throw Error('Comunicado não encontrado.');
  open('Editar comunicado',
    field('title','Título',n.title,'text','required maxlength="150"')+
    area('body','Mensagem',n.body)+
    '<p class="muted">Os destinatários do comunicado não serão alterados.</p>',
    form=>mutate('notice/update',{id:n.id,title:form.get('title'),body:form.get('body')}),'Salvar alterações');
  return;
}
case 'notice-delete':{
  const n=find('notices',id);
  if(!n)throw Error('Comunicado não encontrado.');
  if(confirm('Excluir o comunicado "'+n.title+'"? Ele também desaparecerá da caixa de entrada dos alunos. Esta ação não pode ser desfeita.')){
    await mutate('notice/delete',{id:n.id});
    toast('Comunicado excluído.');
  }
  return;
}
case 'read':await mutate('notice/read',{id:Number(id)});return;
case 'password':open('Alterar senha',field('old','Senha atual','','password','required autocomplete="current-password"')+field('new','Nova senha (12+ caracteres)','','password','required minlength="12" maxlength="128" autocomplete="new-password"'),f=>mutate('password',{old:f.get('old'),password:f.get('new')}));return;
}}
app.addEventListener('click',async e=>{let b=e.target.closest('button[data-action]');if(!b||!S||busy)return;b.disabled=true;try{await handle(b.dataset.action,b.dataset.id)}catch(err){toast(err.message)}finally{b.disabled=false}});app.addEventListener('change',e=>{if(e.target.dataset.filter){filter[e.target.dataset.filter]=e.target.value;render()}});
(async()=>{try{const config=await api('public-config');signupEnabled=Boolean(config.signup_enabled)}catch(_){}try{await refresh()}catch(e){if(!S)loginView();if(e.message&&!/login|Sessão/.test(e.message))toast(e.message)}})();
if('serviceWorker' in navigator&&window.isSecureContext)navigator.serviceWorker.register('/sw.js').catch(()=>{});
