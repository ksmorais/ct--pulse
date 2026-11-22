# CT Pulse V2 — persistência demonstrativa no Firestore (ponte SQL)

**Estado:** implementação experimental na branch `feat/ctpulse-firestore-persistence`. **Não foi executado deploy no Render** e nenhuma chave privada foi recebida por esta integração.

## Como funciona

O `server.py` original contém SQL por toda a aplicação. Para oferecer persistência antes de uma migração nativa maior, foi criada uma **camada de compatibilidade de demonstração**:

1. Ao receber uma chamada de API, o backend lê o documento privado `_ct_pulse_private/sql_snapshot_v1` no Firestore.
2. Descompacta o estado SQL e o carrega num SQLite **em memória** (nenhum arquivo local usado).
3. Executa as regras atuais de autenticação, turmas, inscrições, chamada, avisos e financeiro.
4. Se houve alterações, grava um novo snapshot comprimido **dentro de uma transação Firestore**. Requisições concorrentes ao mesmo documento podem ser repetidas pelo SDK para evitar perda de atualizações.
5. No próximo acesso, mesmo após reiniciar o Render, o backend lê o snapshot remoto anterior.

**Limites importantes:** o Firestore ainda não contém coleções por aluno/turma. Todo o estado está em um documento protegido. A implementação impõe limite de **700 kB comprimidos** e **2 MB descompactados**, além do limite do Firestore de **1 MiB por documento**. Transações em um único documento podem sofrer contenção e encarecer operações. Esta ponte é **somente para demonstração pequena, com dados fictícios** — não para produção, dados pessoais reais, pagamentos bancários reais, concorrência alta ou uso multiacademia. A migração nativa por coleção continua recomendada.

## Publicação de teste: serviço Render SEPARADO

Não substitua ainda o serviço que já está no ar. Primeiro crie um novo **Web Service Free** com nome `ct-pulse-firestore-staging` e:

| Campo | Valor |
|---|---|
| Repository | `ksmorais/ct--pulse` |
| Branch | `feat/ctpulse-firestore-persistence` |
| Root Directory | `web-v2` |
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `bash start-firestore-demo.sh` |
| Compute | Free |

Em **Environment** do serviço de teste, configure as variáveis sem enviá-las a chats nem GitHub:

| Key | Valor |
|---|---|
| `FIREBASE_PROJECT_ID` | `ct-pulse` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | JSON privado da conta de serviço, armazenado como segredo no Render |
| `CT_SECURE_COOKIE` | `1` |
| `CT_DEMO_PASSWORD` | Uma senha exclusiva de 12+ caracteres para as contas aluno de demonstração |
| `CT_DEMO_ADMIN_PASSWORD` | Outra senha exclusiva de 12+ caracteres para o administrador |
| `CT_DEMO_TEACHER_PASSWORD` | Uma terceira senha exclusiva de 12+ caracteres para o professor |

O script define `CT_PERSISTENCE=firestore`, `CT_FIRESTORE_DEMO_SEED=1`, `CT_ALLOW_SIGNUP=1` e `CT_PAYMENT_DEMO=1`. Não configure `CT_DB`, não use Persistent Disk e **não execute `python server.py demo`** no serviço Firestore.

### Segurança

- Mantenha o Firestore Rules sem acesso público, por exemplo `allow read, write: if false`. O backend via Firebase Admin SDK usa IAM, não as regras de cliente.
- Restrinja o IAM da conta de serviço ao mínimo e mantenha a chave fora de `web-v2` e do GitHub.
- Não use dados reais ou pague boletos/Pix na demo; as opções financeiras são **somente simuladas**.
- Contas de admin, professor e aluno devem ter **senhas diferentes**. A senha de aluno não deve dar acesso de administrador.
- Uma chave exposta deve ser revogada imediatamente no Google Cloud.
- Habilitar autocadastro público sem verificação de e-mail é aceitável somente no teste com dados fictícios; adicione validação de e-mail e medidas contra abuso antes de qualquer uso real.

## Teste de persistência

1. Abra a nova URL HTTPS da staging e entre com `admin@ctpulse.com` e a senha de `CT_DEMO_ADMIN_PASSWORD`.
2. Cadastre um aluno com nome/e-mail **fictícios**, por exemplo `aluno.teste@example.com` (não cadastre pessoas reais).
3. Crie um aviso fictício e confira a listagem. Use também o fluxo de edição/exclusão e as opções financeiras demonstrativas.
4. No Firebase Console, veja se existe o documento **`_ct_pulse_private/sql_snapshot_v1`**. Não edite manualmente o conteúdo nem compartilhe prints dos campos (o snapshot contém hashes de senhas).
5. Reinicie **somente o serviço de staging** no Render. Depois do retorno, entre novamente e confira se o aluno e o aviso ainda estão cadastrados.
6. Abra a aplicação no celular e confira o mesmo estado.
7. Execute os testes locais: `python -m unittest discover -s tests -v`.

### Quando o Firestore estiver indisponível

O backend retorna erro **503** e não grava em SQLite local como alternativa. Isso impede apresentar dados não persistidos como se tivessem sido salvos.

## Próximo estágio de engenharia

Migrar progressivamente `users`, `classes`, `enrollments`, `bookings`, `attendance`, `grades`, `payments`, `payment_requests`, `notices`, `inbox` e `sessions` para documentos individuais/consultas nativas, com índices, transações, regras de negócio, backups, auditoria e autenticação revisada. Esta ponte não elimina tal trabalho.

Documentação de referência:
- https://firebase.google.com/docs/firestore/manage-data/transactions
- https://firebase.google.com/docs/firestore/quotas
- https://firebase.google.com/docs/admin/setup
