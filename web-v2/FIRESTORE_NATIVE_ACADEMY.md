# CT Pulse — Evolução Firestore: professores, turmas e inscrições

**Implementação experimental**, em `feat/ctpulse-native-classes-enrollments`. Trabalha apenas com dados **fictícios** em `ct_pulse_native_sandboxes/<workspace_id>`. Não integra o sistema principal de alunos e não cria conta de acesso.

## O que foi implementado

- `native_academy_repository.py`: cria professores de demonstração (sem senha/login), cria/edita turmas, inscreve/cancela inscrições em documentos separados.
- `native_academy_api.py`: operações HTTP acessíveis somente a administradores autenticados com token CSRF nos POSTs.
- `firestore_sql_bridge.py`: direciona `/api/native-academy` para o Firestore nativo; o snapshot SQL original permanece como fonte de autenticação para o laboratório.
- `static/app.js`: nova área **Laboratório Firestore** nas páginas Professores e Turmas, com botões para gerenciar dados fictícios.
- Testes isolados e de API verificam permissões, duplicidade de e-mail, formatos de dias/horários e controle de lotação.

## Estrutura de documentos

```text
ct_pulse_native_sandboxes/
  <workspace_id>/
    users/
      student_<id>             # aluno fictício existente
      teacher_<id>             # professor fictício, SEM senha
    email_index/
      <sha256_email>           # índice único por workspace e perfil
    classes/
      class_<id>               # teacher_id, days, time, capacity, enrolled_count, active
    enrollments/
      <sha256(student|class)>  # student_id, class_id, created_at
```

**Transações:** ao inscrever um aluno, o sistema verifica os documentos de aluno, turma e inscrição, confirma matrícula ativa e vagas disponíveis, e grava inscrição + incrementa `enrolled_count` na mesma transação. Cancelamento diminui a contagem de forma transacional. Repetir inscrição/cancelamento não duplica registros.

A capacidade de turma não pode ser reduzida abaixo da quantidade já inscrita. O laboratório tem limites pequenos e não foi projetado para escala.

## Proteções

- Ativação exige `CT_PERSISTENCE=firestore` e `CT_NATIVE_STUDENTS_LAB=1`, com `CT_NATIVE_STUDENT_WORKSPACE_ID` de 24 caracteres hexadecimais.
- Sessão e CSRF são verificados no backend antes de qualquer leitura/escrita. Papel `admin` é obrigatório.
- Estudantes e professores do laboratório **não têm credenciais**, não conseguem fazer login e **não aparecem na listagem principal**.
- O snapshot `_ct_pulse_private/sql_snapshot_v1` e as cópias `ct_pulse_native_previews` não são modificados pelas operações de laboratório.
- Não há processamento bancário real. A mensalidade fictícia não é gerada automaticamente por uma inscrição.
- Firebase Admin SDK usa IAM e ignora regras de cliente: mantenha as credenciais privadas no Render.
- Não use dados pessoais reais, CPF, dados de cartão, boletos ou cobranças.
- Ainda faltam Firebase Emulator, testes multi-instância e revisão de segurança antes de produção.

## Como testar sem alterar serviços existentes

No VS Code, a partir de `C:\CT-mobile`:

```powershell
git fetch origin
git switch --track origin/feat/ctpulse-native-classes-enrollments
cd web-v2
python -m unittest discover -s tests -v
```

Se a branch já existir localmente, execute `git switch feat/ctpulse-native-classes-enrollments`.

**Antes de publicar**: verifique os testes GitHub Actions, revise este PR e faça backup dos dados de demonstração se desejar mantê-los. Para experimentar, pode criar um novo serviço isolado no Render ou selecionar essa branch no **ct-pulse-native-lab** existente, com consciência de que haverá um novo deploy. Não altere `ct-pulse` ou `ct-pulse-firestore-staging`.

No `ct-pulse-native-lab`, mantenha o script `bash start-firestore-demo.sh` e as mesmas variáveis privadas e de laboratório. O recurso nativo usa o **mesmo workspace ID**, preservando os registros fictícios de alunos; não reinicie nem recrie a fonte SQL manualmente.

Quando estiver online e tiver feito login como administrador:

1. Abra **Professores** e crie um professor fictício em **Laboratório Firestore**.
2. Abra **Turmas** e crie turma de teste selecionando o professor nativo, dias, horário e capacidade.
3. Na mesma seção, clique **Gerenciar inscrições**, selecione um aluno criado no laboratório de alunos e inscreva-o.
4. Confirme o número de inscritos. Teste capacidade limitada, inscrição repetida e cancelamento.
5. Reinicie apenas o serviço de laboratório e verifique se professores, turmas e inscrições continuam salvos.
6. Confira os documentos nas subcoleções `users`, `classes` e `enrollments` do Firestore (nunca compartilhe os segredos).

## O que ainda falta para o CT Pulse completo

Esta etapa **não migra os usuários e turmas do snapshot atual** para o fluxo de login, nem integra financeiro, presença, graduação ou avisos ao banco nativo. Próximas fases: autenticação com perfis verificados, migração dos dados existentes sem duplicação, controle de permissão por aluno/professor, agendamentos, presenças, financeiro, integração com pagamento real, testes de concorrência e plano de rollback.
