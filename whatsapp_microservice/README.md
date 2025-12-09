# Node.js WhatsApp Microservice

Este repositório contém o microserviço Node.js para integração com WhatsApp, desenvolvido para trabalhar em conjunto com o WhatsApp Sales Agent em Django.

## Estrutura do Projeto

```
/
├── src/
│   ├── config/               # Configurações da aplicação
│   ├── controllers/          # Controladores da API
│   ├── middleware/           # Middlewares da aplicação
│   ├── models/               # Modelos de dados
│   ├── services/
│   │   ├── whatsapp/         # Serviços de integração WhatsApp
│   │   ├── queue/            # Sistema de filas
│   │   └── scheduler/        # Serviço de agendamento
│   ├── utils/                # Utilitários
│   └── app.js                # Ponto de entrada da aplicação
├── sessions/                 # Armazenamento de sessões WhatsApp
├── .env.example              # Exemplo de variáveis de ambiente
├── Dockerfile                # Configuração do container
└── package.json              # Dependências
```

## Requisitos

- Node.js 16+
- MongoDB
- NPM ou Yarn

## Instalação

1. Clone o repositório
2. Instale as dependências: `npm install`
3. Copie `.env.example` para `.env` e configure as variáveis
4. Inicie o servidor: `npm start`

## Configuração

Variáveis de ambiente necessárias:

- `PORT`: Porta do servidor (padrão: 3000)
- `API_KEY`: Chave de API para autenticação
- `JWT_SECRET`: Segredo para geração de tokens JWT
- `MONGODB_URI`: URI de conexão com MongoDB
- `WEBHOOK_URL`: URL do webhook para envio de notificações
- `OPERATION_START_HOUR`: Hora de início da operação (padrão: 7)
- `OPERATION_END_HOUR`: Hora de término da operação (padrão: 23)
- `CONTACT_INTERVAL_MS`: Intervalo entre mensagens para contatos diferentes em ms (padrão: 15000)
- `SAME_CONTACT_INTERVAL_MS`: Intervalo entre mensagens para o mesmo contato em ms (padrão: 2000)

## API REST

Documentação completa da API disponível em `/api/docs`

## Regras Anti-Bloqueio

O microserviço implementa as seguintes regras para evitar bloqueios:

1. **Intervalos entre mensagens:**
   - 15 segundos entre mensagens para contatos diferentes
   - 2 segundos entre mensagens para o mesmo contato

2. **Horário de operação:**
   - Funcionamento apenas das 07h às 23h
   - Mensagens fora deste horário são enfileiradas para o próximo período válido

3. **Comportamento humanizado:**
   - Simulação de digitação antes do envio
   - Variação aleatória nos tempos de resposta
   - Indicadores de leitura de mensagem

## Licença

Este projeto é licenciado sob a licença MIT.
