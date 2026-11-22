# Evolução do CT Pulse — repositório nativo de alunos (isolado)

Esta etapa implementa um **repositório Firestore de estudantes**, como preparação para substituir a ponte SQL da demonstração.

**A aplicação online não foi modificada.** O código novo não está conectado ao `server.py` e não cria novas rotas HTTP. O login continua usando o snapshot SQL original.

## O que está pronto no código

Arquivo: `web-v2/native_student_repository.py`.

- `create_student(name, email, plan_cents)`: cria documento com `role=student` fixo e um índice de e-mail único **dentro do sandbox**. As duas gravações usam transação Firestore.
- `get_student(student_id)`: recupera apenas campos permitidos, sem dados de autenticação.
- `list_students()`: lista até 50 alunos fictícios, ordenados pelo nome. Não é uma consulta otimizada para produção.
- `update_student(student_id, name, plan_cents, active, belt)`: altera apenas os campos permitidos; recusa mudar e-mail, papel, senha ou identificador.
- `active=0`: desativa o cadastro no sandbox, sem excluir o documento.

## Isolamento

Os documentos são armazenados em:

```text
ct_pulse_native_sandboxes/
  <workspace_id>/
    users/
      student_<id>/
        role: student
        name: ...
        email: ...
        active: 1
        plan_cents: 0
        belt: Branca
    email_index/
      <sha256_email>/
        user_id: student_<id>
```

O `workspace_id` é um identificador hexadecimal de 24 caracteres. A camada nativa **não usa nem escreve** em:

- `_ct_pulse_private/sql_snapshot_v1` — o estado usado pela API online;
- `ct_pulse_native_previews/<export_id>` — a cópia de 19 documentos que você acabou de validar.

Os dados do sandbox não são sincronizados com a aplicação online. São independentes e servem apenas para testes.

## Como validar a implementação

No terminal do VS Code, com a branch `feat/ctpulse-native-student-repository`:

```powershell
cd C:\CT-mobile\web-v2
python -m unittest discover -s tests -v
```

Os testes funcionam **sem Internet e sem acessar o Firestore real**. A camada usa mocks que simulam transações, documentos, duplicidade e tentativas de alterar perfis.

Nenhuma conta do sandbox faz login, e **não existe criação de senhas** nessa fase.

## Próximas etapas necessárias antes de integrar à interface

1. Implementar um fluxo de autenticação seguro, com identidade verificada (por exemplo, Firebase Authentication), e autorização no backend.
2. Fazer a migração nativa dos professores e turmas.
3. Implementar índices, transações de inscrições/lotação e integridade entre coleções.
4. Configurar testes com Firebase Emulator Suite e validar erros reais de concorrência.
5. Preparar migração controlada de dados da ponte SQL, com rollback, sem expor hashes ou sessões.
6. Só depois ativar o novo backend em um serviço de staging distinto.

**Não usar com alunos reais, CPF, cobranças ou dados financeiros reais.** O SDK Admin ignora regras do Firestore; restrinja credenciais IAM e nunca as coloque no frontend ou GitHub.
