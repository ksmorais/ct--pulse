# Publicar o CT Pulse V2 no Render (SQLite persistente)

Esta configuração publica somente a pasta `web-v2/`, preservando a aplicação Expo da raiz.

## Modo gratuito: demonstração acadêmica (sem persistência)

O Render Free apaga arquivos locais após repouso, restart e novo deploy. **Nunca use dados reais ou o banco de produção nesta modalidade.**
A demonstração é reiniciada com dados fictícios sempre que o serviço inicia. Não requer Persistent Disk nem Shell (indisponíveis no plano Free).

1. Abra o Render Dashboard > **New > Web Service**, escolha o repositório `ksmorais/ct--pulse`.
2. Até esta PR ser mesclada, selecione a branch `feat/ctpulse-render-deploy`.
3. Selecione **Runtime Python**, **Root Directory: `web-v2`** e **Compute: Free ($0/mês)**.
4. Build Command: `pip install -r requirements.txt`.
5. Start Command: `bash start-demo.sh` (**diferente** do modo pago).
6. Em Environment, configure:
   - `CT_SECURE_COOKIE` = `1`
   - `CT_DEMO_PASSWORD` = **uma senha exclusiva com no mínimo 12 caracteres**, criada por você diretamente no painel do Render (não a inclua no GitHub, no print nem no chat).
7. Não configure `CT_DB` nem Persistent Disk; `start-demo.sh` usa um banco **descartável** em `/tmp/ctpulse-demo.sqlite3`.
8. Clique para criar/deployar o serviço, confira os logs e abra sua URL HTTPS `*.onrender.com`.
9. Entre com um destes e-mails fictícios e **a senha definida em `CT_DEMO_PASSWORD`**: `admin@ctpulse.com`, `prof@ctpulse.com` ou `aluno@ctpulse.com`. As credenciais padrão documentadas para **uso local** não funcionam na versão hospedada.
10. Use apenas dados fictícios. Cadastros, alterações e pagamentos simulados podem ser vistos/modificados pelas pessoas com acesso, e **desaparecem** quando o serviço reiniciar.

### Autocadastro de alunos na página de login

Na hospedagem demonstrativa, `start-demo.sh` define `CT_ALLOW_SIGNUP=1` automaticamente. A tela de login exibe **Criar conta de aluno**.

- O aluno informa **nome fictício, e-mail de teste e senha própria de 12+ caracteres**, confirma a senha e acessa a conta após fazer login.
- O novo cadastro recebe somente perfil `student`, sem privilégios administrativos. O plano começa com valor zero e pode ser configurado pelo administrador depois; não gera pagamento automaticamente.
- E-mails duplicados, senhas insuficientes e campos inesperados são recusados. A demonstração limita a 50 o número total de contas de aluno.
- Não há verificação de e-mail, consentimento formal, controle completo contra abuso nem banco persistente. **Não use cadastros reais**.
- Fora do modo demo, `CT_ALLOW_SIGNUP` é desativado por padrão; só ative após uma revisão específica de segurança e privacidade.
- Teste local: no PowerShell, defina `$env:CT_ALLOW_SIGNUP = '1'` **antes** de iniciar o servidor e use apenas dados fictícios.


O script recusa iniciar se a senha não foi definida, se ela tiver menos de 12 caracteres ou se `CT_SECURE_COOKIE` não estiver habilitado. Não use `python server.py demo` com senha padrão para serviço público. Considere desabilitar o auto-deploy depois da demonstração para evitar reinicializações inesperadas, sabendo que o serviço Free poderá entrar em repouso mesmo assim.

## Modo pago: banco SQLite persistente

## Antes de começar

- A hospedagem deve ter disco persistente para o SQLite. No Render, esse recurso exige instância web paga; a modalidade gratuita **não** serve para persistência local do banco.
- Configure HTTPS, backups e revise segurança/LGPD antes de cadastrar pessoas reais.
- O banco local `data/ctpulse.sqlite3` e as contas de demonstração **não** devem ser enviados ao servidor público.
- O servidor WSGI de produção é o Gunicorn (Linux); `server.py serve` é para desenvolvimento.

## Configuração manual no Render

1. Acesse https://dashboard.render.com e selecione **New > Web Service**.
2. Conecte o repositório `ksmorais/ct--pulse`; selecione a branch `main` depois que esta alteração estiver mesclada.
3. Configure:
   - **Runtime**: Python
   - **Root Directory**: `web-v2`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `bash start.sh`
   - **Instância**: uma opção **paga** que permita disco persistente
4. Adicione um **Persistent Disk**, com mount path `/var/data` (tamanho conforme necessidade, por exemplo 1 GB).
5. Defina as variáveis de ambiente:
   - `CT_DB=/var/data/ctpulse.sqlite3`
   - `CT_SECURE_COOKIE=1`
6. Confira os custos no resumo da plataforma **antes** de confirmar a criação do serviço.
7. Após o deploy, abra a **Shell** do serviço em execução e crie o primeiro administrador:
   ```bash
   python server.py admin --email seu-email@exemplo.com --name "Administrador CT Pulse"
   ```
   O comando solicitará uma senha **nova, exclusiva e de no mínimo 12 caracteres**. Não escreva a senha em comentários, comandos ou repositório. Execute apenas uma vez para cada administrador.
8. Abra a URL HTTPS do serviço (geralmente termina em `.onrender.com`) e faça login.
9. Teste pelo computador e pelo celular, ambos com contas **fictícias**, e reinicie o serviço para verificar persistência.

## Conferência e operação

- Verifique o arquivo `/var/data/ctpulse.sqlite3` e suas permissões na instância.
- Nunca execute `python server.py demo` no ambiente público.
- Antes do uso real, configure backups **consistentes** do SQLite e teste restauração. Os arquivos `-wal` e `-shm` podem existir enquanto o banco opera.
- A aplicação com SQLite em um disco deve permanecer em **uma instância**. Para escalar horizontalmente, planeje migração para PostgreSQL e adapte a camada de acesso.
- Não rode duas réplicas apontando para bancos independentes.
- O primeiro deploy pode exibir a tela de login antes de haver administrador; conclua a criação pelo Shell.
- A versão Expo permanece independente da API; o deploy web não altera ou sincroniza automaticamente o aplicativo nativo.

## Problemas frequentes

- **Erro de configuração ao iniciar**: confira `CT_DB` e `CT_SECURE_COOKIE` em Environment.
- **Application failed to respond**: confira `bash start.sh`, logs de deploy e variável `PORT` fornecida pelo Render.
- **Login 401**: antes do login é esperado; depois, confira se o administrador foi criado no banco montado.
- **Dados somem após restart**: confira se `CT_DB` aponta para o diretório do Persistent Disk; não use disco efêmero.

## Referências

- https://render.com/docs/web-services
- https://render.com/docs/disks
- https://render.com/docs/ssh
- https://render.com/docs/monorepo-support
