# CT Pulse V2 — Laboratório de Alunos com Firestore Nativo

Esta branch introduz **rotas HTTP protegidas** e uma **seção de interface** para administrar **alunos fictícios** armazenados em documentos Firestore separados.

**Não é a migração definitiva:** os dados cadastrados no laboratório não aparecem na lista principal de alunos, não criam conta de login, não se inscrevem em turmas e não geram mensalidades. O CT Pulse principal continua usando o snapshot SQL original. A implementação não foi implantada no Render.

## Proteções

- Padrão: desativado; ativa apenas com `CT_PERSISTENCE=firestore`, `CT_NATIVE_STUDENTS_LAB=1` e `CT_NATIVE_STUDENT_WORKSPACE_ID` de 24 caracteres hexadecimais.
- Antes de ler ou escrever no sandbox, verifica sessão existente e papel **admin** no snapshot original do Firestore.
- Operações POST exigem **CSRF** e JSON válido.
- Rotas de laboratório usam as permissões do administrador, sem permitir criação com papel `admin` ou `teacher`.
- Não compartilha nem edita `_ct_pulse_private/sql_snapshot_v1` ou `ct_pulse_native_previews`.
- O namespace `ct_pulse_native_sandboxes/<workspace_id>/users` e o índice de e-mail são isolados e persistentes.
- O backend aplica allow-list de campos e transações para a unicidade do e-mail.
- **Não processar dados pessoais reais, passwords, CPF ou cobranças.** Sem verificação de titularidade de e-mail, a experiência é destinada apenas a testes fictícios.
- A conta de serviço do Firebase usa IAM e ignora regras do Firestore; mantenha os segredos somente no backend Render.

## Configuração para avaliar (somente ambiente isolado)

Crie um **novo Web Service de testes** (não modifique `ct-pulse-firestore-staging` que já funciona):

| Campo | Valor |
|---|---|
| Branch | `feat/ctpulse-native-students-api-ui` |
| Root Directory | `web-v2` |
| Build | `pip install -r requirements.txt` |
| Start | `bash start-firestore-demo.sh` |
| Compute | Free |

Além das variáveis seguras já necessárias ao `start-firestore-demo.sh`, configure:

| Key | Valor |
|---|---|
| `CT_NATIVE_STUDENTS_LAB` | `1` |
| `CT_NATIVE_STUDENT_WORKSPACE_ID` | ID hexadecimal aleatório de **24 caracteres**, exclusivo para esta demonstração (por exemplo, gere localmente com `python -c "import secrets; print(secrets.token_hex(12))"`) |

**Importante:** se usar o mesmo projeto Firebase, as sessões e dados demonstrativos normais continuarão compartilhados entre serviços no snapshot original; para isolamento completo, prefira um **projeto Firebase separado de staging** antes de testes extensos. Não rode comandos que redefinam o snapshot e não altere o Render principal. Crie contas fictícias e senhas exclusivas; não compartilhe prints de variáveis.

## Teste de ponta a ponta

1. Entre como administrador no serviço de teste.
2. No menu **Alunos**, localize **Laboratório Firestore — alunos fictícios**, abaixo da lista principal.
3. Clique em **+ Aluno de teste** e cadastre um nome fictício e e-mail de teste.
4. Clique em **Editar** para alterar o nome e a mensalidade demonstrativa ou mudar a faixa.
5. Use **Desativar/Reativar** para validar atualização do cadastro.
6. Reinicie somente o serviço de teste e retorne ao laboratório. Confirme que o registro continua lá.
7. Faça login como professor ou aluno e confira que o laboratório não aparece.
8. Verifique em Firebase Console → Firestore → Data `ct_pulse_native_sandboxes/<workspace_id>/users`.
9. Execute localmente `python -m unittest discover -s tests -v`.

## Próximos trabalhos

1. Integrar repositórios de turmas e professores com autorização e relacionamentos.
2. Integrar cadastro real de alunos com uma identidade verificável (Firebase Authentication ou solução de servidor equivalente), com migração de perfis e sessões.
3. Planejar migração com congelamento de escrita, idempotência, reprocessamento e rollback, para evitar duplicatas e perda de dados.
4. Testar regras de negócio e transações distribuídas com Firebase Emulator Suite.
5. Migrar avisos, inscrições, presenças e financeiro para coleções nativas e retirar a ponte SQL somente após testes integrados.

O recurso está restrito ao laboratório; **não efetue merge para a main nem uso com dados reais nesta etapa**.
