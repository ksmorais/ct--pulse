# CT Pulse V2 — Preparação do Cloud Firestore

**Project ID:** `ct-pulse`  
**Database ID:** `(default)`  
**Status:** cliente Python e testes de configuração preparados. **A migração dos dados ainda não foi implementada.** Não substitua a inicialização SQLite no Render por esta preparação.

## 1. Segurança no Firebase

Em Firestore Database > Rules, mantenha acesso direto pelo navegador fechado, pois o backend Python é o único cliente do Firestore planejado:

```text
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

O Firebase Admin SDK usa IAM e **não é limitado por Firestore Security Rules**. Proteja as credenciais e restrinja os papéis da conta de serviço; evite permissões administrativas excessivas.

## 2. Credencial privada de serviço

No Firebase Console > engrenagem > Project settings > **Service accounts**, obtenha uma credencial de serviço autorizada para acessar o Firestore. Se for necessário gerar uma chave JSON, armazene-a em local seguro, fora do repositório.

**Não envie a chave em chats, issues, PRs, arquivos públicos, imagens ou commits.** Se a chave for exposta, revogue-a no Google Cloud IAM e gere outra.

No Render, em **Environment**, planeje adicionar:

| Key | Value |
|---|---|
| `FIREBASE_PROJECT_ID` | `ct-pulse` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | conteúdo completo e privado do JSON da conta de serviço |

Armazene a variável como segredo no Render, sem copiar para logs. Para desenvolvimento local, também é possível definir `GOOGLE_APPLICATION_CREDENTIALS` para apontar ao arquivo JSON privado no próprio computador.

**Não mude as variáveis do serviço que já está online antes da migração ser aprovada e testada.** Primeiro use serviço de staging ou valide localmente.

## 3. Testar apenas a conexão (sem migrar)

Em ambiente isolado e com as credenciais configuradas:

```powershell
cd C:\CT-mobile\web-v2
pip install -r requirements.txt
python firebase_store.py
python -m unittest discover -s tests -v
```

Se a autenticação e permissão de leitura estiverem corretas, o primeiro comando Python reportará `Conexão com o Cloud Firestore validada.` O teste não cria coleções nem escreve dados. A leitura de diagnóstico pode contar para a cota do Firestore.

Os testes unitários verificam apenas validação de configuração com credenciais artificiais. **Não comprovam persistência real**.

## 4. Migração que ainda falta

O arquivo `server.py` atual usa `sqlite3` e consultas SQL para autenticação, sessões, permissões, turmas, inscrições, agendamentos, presenças, mensalidades, graduação, avisos e métodos demonstrativos de pagamento.

Para que esses dados sejam realmente persistentes, será preciso implementar um repositório de dados Firestore para cada domínio, definir chaves e índices, converter consultas e integridade referencial para documentos/transações, testar autorização sob concorrência, substituir o script de inicialização temporária e **só então** atualizar o Render.

Coleções planejadas: `users`, `sessions`, `login_attempts`, `classes`, `enrollments`, `bookings`, `attendance`, `payments`, `payment_requests`, `grades`, `notices`, `inbox`. Os documentos devem ter IDs estáveis e controles de acesso executados no backend.

A migração não deve importar senhas de demonstração para contas reais e precisa respeitar a LGPD. O plano Spark oferece cota gratuita; monitore leituras, gravações e armazenamento. Firestore persistente não elimina a necessidade de backups e auditoria.

## Referências

- https://firebase.google.com/docs/firestore/quickstart-server
- https://firebase.google.com/docs/admin/setup
- https://firebase.google.com/docs/firestore/security/insecure-rules
- https://firebase.google.com/docs/firestore/pricing
- https://render.com/docs/configure-environment-variables
