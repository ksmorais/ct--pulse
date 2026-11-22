# CT Pulse 2.0 — Web e celular

Versão web responsiva do CT Pulse, baseada no escopo e na identidade visual do protótipo React Native existente. É um projeto separado, que pode ser adicionado à pasta `web-v2` do repositório original. Não substitui nem modifica automaticamente o App.js original.

## 1. Instalar e executar no Windows / VS Code

1. Instale Python 3.11 ou superior e marque a opção Add Python to PATH.
2. Extraia o ZIP. No VS Code, abra a pasta `CT_Pulse_v2`, que contém `server.py`.
3. Abra Terminal > New Terminal. Rode:

```powershell
python --version
python server.py demo
python server.py serve --host 0.0.0.0 --port 8000
```

Se `python` não funcionar, tente `py -3` em vez de `python`. Não há dependências externas para executar localmente; o SQLite já acompanha Python. O comando `demo` cria o banco com dados fictícios, apenas se não houver usuários. Na próxima vez, execute somente o comando `serve`.

No computador, abra http://localhost:8000 no navegador. Mantenha o terminal aberto. Encerre o servidor com Ctrl+C.

### Contas fictícias (apenas para teste em rede confiável)

| Perfil | E-mail | Senha |
|---|---|---|
| Administrador | admin@ctpulse.com | DemoAdmin2026! |
| Professor | prof@ctpulse.com | DemoProfessor2026! |
| Aluno | aluno@ctpulse.com | DemoAluno2026! |

## 2. Acessar pelo celular Android/iPhone

Conecte o telefone e o computador ao mesmo Wi-Fi. No PowerShell, use `ipconfig` e procure o endereço IPv4 do adaptador Wi-Fi (exemplo: 192.168.1.50). No navegador do celular, abra `http://192.168.1.50:8000`, substituindo pelo IP real. Autorize a rede privada no firewall do Windows caso seja necessário. Não exponha a porta diretamente à internet.

Os dois dispositivos usam o mesmo banco no computador. Após alterações feitas por outro usuário, pressione Atualizar. A interface adapta-se ao tamanho da tela. Em uma hospedagem HTTPS, o manifesto PWA permite adicionar o site à tela inicial (Chrome: menu > Instalar aplicativo ou Adicionar à tela inicial; Safari: Compartilhar > Adicionar à Tela de Início, conforme versão). Em HTTP na rede local a instalação PWA completa pode não estar disponível. Não é APK nem IPA, e o app requer conexão com o servidor.

## 3. Banco de dados real

`data/ctpulse.sqlite3` é criado automaticamente. Não é um arquivo JSON ou localStorage. É um banco SQL com tabelas, chaves estrangeiras, transações e restrições. A API é a única via de acesso do navegador. Banco não deve ser enviado ao GitHub.

- users: usuários, perfis, cadastro, plano e graduação
- classes: turmas, professor associado, dias e capacidade
- enrollments: inscrições
- bookings: agendamentos únicos por dia
- attendance: registros de presença/ausência
- payments: mensalidades e baixa manual, valores em centavos
- grades: histórico de graduação
- notices / inbox: comunicados e leitura por aluno
- sessions / login_attempts: sessões com expiração e controle básico de tentativas de login

Para consultar no VS Code, instale uma extensão de visualização de SQLite de sua confiança ou abra o arquivo em DB Browser for SQLite. Não edite diretamente durante uso do sistema.

Para iniciar com banco vazio para uso não demonstrativo, use um arquivo diferente:

```powershell
$env:CT_DB = "$PWD/data/ctpulse_real.sqlite3"
python server.py init
python server.py admin --email gestor@seuct.com.br --name "Gestor do CT"
python server.py serve --host 0.0.0.0 --port 8000
```

O comando pede uma senha exclusiva de no mínimo 12 caracteres, sem exibi-la no terminal. Não execute `demo` no banco real. Antes de usar dados pessoais reais, configure HTTPS, backups, política de privacidade e revise as permissões e segurança. Em um novo terminal, defina CT_DB novamente para acessar esse banco.

## 4. O que testar na banca

1. No PC, entre como administrador e cadastre um aluno com e-mail fictício e senha de teste.
2. No celular (ou janela anônima), entre com o novo aluno, inscreva-se em uma turma e agende uma aula.
3. Acesse como professor, abra Chamada, marque presença do aluno e publique comunicado para a turma.
4. Volte ao celular; clique Atualizar e consulte presença e aviso.
5. Como administrador, registre a baixa de uma mensalidade; no celular o aluno consulta o novo status.
6. Feche e reabra o servidor para comprovar persistência; não recrie a base de dados.

## 5. Testes automatizados

```powershell
python -m unittest discover -s tests -v
```

Usam um banco temporário e não alteram o banco do CT. Testam autenticação, permissões, isolamento dos dados do aluno, CSRF, cadastro, inscrição, agendamento sem duplicatas, frequência, graduação, publicação, leitura, baixa de mensalidade, persistência entre sessões independentes e desativação. Também foi executado `node --check static/app.js` para verificar a sintaxe JavaScript. A navegação gráfica não pôde ser concluída neste ambiente porque o Chromium bloqueou o acesso ao servidor de teste; valide em Chrome/Safari e aparelho reais antes da defesa.

## 6. Publicar no GitHub sem apagar o projeto original

No repositório clonado, crie uma branch pelo terminal do VS Code:

```powershell
git checkout main
git pull origin main
git checkout -b feat/ctpulse-web-database
```

Copie a pasta inteira `CT_Pulse_v2` extraída para dentro do repositório e renomeie-a para `web-v2`. Então, na raiz do repositório:

```powershell
git add web-v2
git status
git commit -m "feat: adiciona CT Pulse web responsivo com SQLite e autenticação"
git push -u origin feat/ctpulse-web-database
```

Abra o pull request no GitHub. O app Expo antigo continua independente, com seus dados locais; não se sincroniza automaticamente com este novo servidor. Para migrá-lo a uma experiência nativa, seria necessário integrá-lo às rotas dessa API ou empacotar a PWA e testar builds Android/iOS.

## 7. Hospedagem futura para uso fora da rede

O servidor embutido do Python é para execução local e demonstração. Para uso público, contrate uma hospedagem que tenha disco persistente (não armazenamento efêmero), HTTPS, backups e suporte a Python. Configure `CT_DB` em um volume persistente e `CT_SECURE_COOKIE=1`. Em Linux, execute com servidor WSGI de produção, por exemplo Gunicorn (`pip install gunicorn`; `gunicorn --bind 127.0.0.1:8000 --workers 2 server:app`, após `python server.py init`), atrás de proxy HTTPS. Mantenha uma única instância/volume SQLite; para maior concorrência ou múltiplas réplicas, migre para PostgreSQL com adaptação da camada de acesso. Faça backups SQLite consistentes via API de backup, teste restauração, revise logs, proteção contra abuso e LGPD. Não publique as contas demo.

Limitações: não há gateway de pagamento, envio de e-mail, push remoto, recuperação de senha por e-mail, atualização automática em tempo real, migração de dados do protótipo, multiacademia nem publicação em lojas. A baixa financeira registra um pagamento recebido externamente, sem movimentar dinheiro. O aplicativo está pronto para demonstração funcional local, sujeito à validação visual e em dispositivos reais; não é homologado para produção.
