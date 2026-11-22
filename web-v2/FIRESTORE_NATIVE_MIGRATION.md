# CT Pulse — Prévia de dados em coleções nativas Firestore

**Etapa 1 da migração nativa:** separar os dados da demonstração em documentos Firestore, sem mudar a API que já funciona no Render.

## Objetivo

O serviço `ct-pulse-firestore-staging` hoje salva a demonstração em um único documento:
`_ct_pulse_private/sql_snapshot_v1`. Isso já preserva dados entre reinícios, mas não é uma estrutura nativa de coleções.

O novo script `firestore_native_preview.py` lê esse snapshot **sem editá-lo**, valida integridade referencial e cria uma **cópia isolada** de registros em subcoleções individuais:

```text
ct_pulse_native_previews/
  <export_id>/
    schema_version: 1
    status: incomplete | complete
    ready_for_runtime: false
    users/
    classes/
    enrollments/
    bookings/
    attendance/
    payments/
    payment_requests/
    grades/
    notices/
    inbox/
```

Nessa prévia:
- Cada aluno, professor, turma, aviso ou mensalidade aparece como documento próprio.
- **Não** são exportados `password_hash`, `sessions`, `login_attempts`, tokens ou CSRF.
- O campo `ready_for_runtime` permanece `false`: não é um banco preparado para autenticar usuários.
- Cada execução tem um novo `export_id` e não sobrescreve cópias anteriores.
- A fonte original permanece intacta; o serviço Render **continua usando o documento SQL original**.
- O manifesto começa como `incomplete` e muda para `complete` apenas se todas as escritas terminarem.

## Teste seguro: primeiro somente leitura

Na branch `feat/ctpulse-firestore-native-preview`, com as credenciais Firebase **já configuradas localmente**:

```powershell
cd C:\CT-mobile
git fetch origin
git switch feat/ctpulse-firestore-native-preview
git pull --ff-only origin feat/ctpulse-firestore-native-preview
cd web-v2
python -m unittest discover -s tests -v
python firestore_native_preview.py
```

O comando sem parâmetros **não grava nada** no Firestore. Ele apresenta somente as quantidades por coleção para revisão. Não exibe nomes, e-mails nem hashes.

## Exportar uma prévia: operação opcional

**Somente se o banco tiver dados 100% fictícios**, execute:

```powershell
python firestore_native_preview.py --apply --ack-demo-only
```

O script grava os documentos isolados e mostra o caminho:

```text
ct_pulse_native_previews/<export_id>
```

Abra Firebase Console → Firestore Database → Data. Confirme o manifesto `status: complete` e consulte as subcoleções. **Não compartilhe prints de dados privados**. Se houver interrupção, o manifesto pode ficar `incomplete`; ignore esse lote e não o conecte à aplicação.

### Limitações

- Essa é uma **exportação pontual**, não uma sincronização contínua. Novos cadastros/edições na aplicação depois da exportação não atualizam a cópia.
- Não há alteração do `server.py`, do script de inicialização Render nem do banco em uso. Não mude a branch nem as variáveis do serviço publicado.
- Nenhuma conta exportada consegue fazer login com esses documentos; a autenticação continua no snapshot original.
- Existem limites de volume (máximo 1.500 documentos nessa prévia) e lotes para operações de gravação. A exportação tem custo em leituras/escritas dentro das cotas aplicáveis ao Firestore.
- Contas e e-mails fictícios apenas. **Não utilizar para dados de pessoas reais, CPF, dados bancários ou cobranças reais**.
- O manifesto `complete` confirma o processo de cópia; não equivale a validar uma API nativa.
- Os registros exportados possuem campos referenciais, mas o Firestore não aplica automaticamente restrições de chave estrangeira. A futura API nativa precisará validar referências e operações concorrentes.
- Não execute exportações repetidas sem necessidade, para evitar acúmulo de documentos e consumo de cota.

## Próximos marcos de desenvolvimento

1. Construir repositórios nativos para `users` e `classes`, com filtros e validações, sem salvar senhas em documentos públicos.
2. Migrar autenticação, sessões e permissões para uma implementação segura baseada em Firebase Authentication ou autenticação de servidor revisada.
3. Implementar inscrições e agendamentos com **transações**, validação de lotação e consistência de referências.
4. Migrar avisos, frequências, mensalidades e demais áreas, com testes end-to-end.
5. Executar uma migração de corte, com congelamento de alterações, verificação de contagem/checksum, backups e rollback, antes de alterar o Render.
6. Descontinuar a ponte SQL comprimida **somente após** validar o sistema nativo.

Esta branch é um marco de migração e deve permanecer como **Pull Request em rascunho** até aprovação dos testes e revisão.

Referências: https://firebase.google.com/docs/firestore/manage-data/add-data e https://firebase.google.com/docs/firestore/quotas
