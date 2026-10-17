CT PULSE MOBILE — PROJETO INTEGRADOR III (ATIVIDADE AVALIATIVA 01)
===============================================================

OBJETIVO
Protótipo navegável para um CT de Muay Thai, com acesso do administrador,
professor e aluno, voltado ao uso em celulares Android e iPhone.

DOIS CAMINHOS PARA APRESENTAR
1) TESTAR AGORA: abra Previa_Interativa_Celular.html no navegador de um
   computador ou celular. É uma PRÉVIA MOBILE INTERATIVA, não um app instalado.
2) TESTAR COMO APP NATIVO: execute o projeto Expo/React Native disponível
   neste pacote e abra-o no Expo Go do celular.

ACESSOS FICTÍCIOS
Administrador: admin@ctpulse.com / admin123
Professor:      prof@ctpulse.com  / prof123
Aluno:          aluno@ctpulse.com / aluno123

EXECUTAR O APP REACT NATIVE / EXPO
- Instale Node.js (versão compatível com Expo SDK 57) e Expo Go no celular.
- Descompacte este arquivo e abra a pasta CT_Pulse_Mobile_Entrega_01.
- No terminal, dentro dessa pasta, execute: npm install
- Em seguida: npx expo start
- Escaneie o QR code exibido no terminal usando Expo Go.
- Se o celular não conectar, tente: npx expo start --tunnel
- Se houver incompatibilidades de dependências, rode: npx expo install --fix
  e tente novamente. Expo Go precisa ser compatível com o SDK do projeto.
- Uma instalação APK ou publicação em loja requer build separado; este
  pacote é o CÓDIGO-FONTE do app, não um APK/IPA pronto.

TESTAR OS FLUXOS PRINCIPAIS
Admin: Alunos -> Novo aluno -> Editar -> Graduação; Turmas -> Nova turma;
Chamada -> Presença; Financeiro -> Preparar lembretes; Avisos -> Publicar.
Professor: Chamada -> Registrar frequência; Avisos -> Escrever comunicado.
Aluno: Turmas -> Inscrever-se -> Agendar; Agenda -> Frequência;
Mensalidade -> Simular pagamento; Avisos -> Ler; Perfil -> Notificações.
Teste publicar aviso como professor, trocar o perfil e ler como aluno.

NOTIFICAÇÕES E E-MAIL
- Caixa de avisos interna com dados de demonstração: funciona.
- Notificações LOCAIS no app Expo: podem ser agendadas pelo aluno após
  conceder permissão. Use Perfil -> Testar notificação em 5 segundos.
- Lembretes locais: vencimento (7, 3, 1 e 0 dia) e aula (1 hora antes),
  conforme calendário e dados cadastrados na demonstração. Requer ativar
  permissão e clicar em programar alertas no perfil.
- E-mails automáticos reais: NÃO são enviados. O sistema oferece uma
  prévia/registro de mensagens de cobrança para avaliação acadêmica.
- Avisos entre celulares diferentes e e-mails automáticos precisam de
  backend, push remoto, provedor de e-mail e banco de dados centralizado.
- Dados de demonstração são salvos localmente no dispositivo/navegador;
  não há sincronização entre celulares.

ARTEFATOS DO PACOTE
- App.js: código do aplicativo React Native para Expo.
- package.json/app.json/babel.config.js: configurações do aplicativo.
- assets/: ícones de exemplo.
- Previa_Interativa_Celular.html: visualização interativa independente.
- Guia_Apresentacao_CT_Pulse_Mobile.pdf: documentação pronta para entregar.
- evidencias/: imagens da prévia para demonstrar fluxos.

IMPORTANTÍSSIMO PARA A ACE
O Termo de Anuência da pessoa física OU jurídica é OBRIGATÓRIO e deve
ser entregue separadamente, preenchido e assinado por representante do CT
aceito pela coordenação/professor. Não há termo assinado neste pacote.

USO ACADÊMICO
A autenticação é DEMONSTRATIVA e a base de dados é local e fictícia.
Não utilize dados pessoais reais ou cobranças reais nesta versão.
