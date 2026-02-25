# pikpak-slack-bot

Bot Slack que recebe magnet links ou URLs no canal `#pikpak-downloads` e aciona o download offline via PikPak automaticamente.

## Fluxo

1. Usuário envia magnet/URL no canal `#pikpak-downloads`
2. Bot detecta e aciona PikPak offline download
3. Bot responde no canal com o status (iniciado / concluído / erro)
4. Quando o arquivo fica disponível, o bot envia o link direto no canal

## Setup rápido

```bash
pip install -r requirements.txt
cp .env.example .env
# Edite .env com suas credenciais
python bot.py
```

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `SLACK_BOT_TOKEN` | Token do bot Slack (xoxb-...) |
| `SLACK_APP_TOKEN` | Token do app Slack para Socket Mode (xapp-...) |
| `PIKPAK_USERNAME` | E-mail ou telefone da conta PikPak |
| `PIKPAK_PASSWORD` | Senha da conta PikPak |
| `PIKPAK_OFFLINE_PATH` | Pasta de destino no PikPak (ex: `/downloads`). Deixe vazio para raiz |

## Instalação do Slack App

1. Acesse https://api.slack.com/apps e crie um novo app
2. Ative **Socket Mode** e gere o `App-Level Token` (scope: `connections:write`) → `SLACK_APP_TOKEN`
3. Em **OAuth & Permissions**, adicione os scopes:
   - `channels:history`, `channels:read`
   - `chat:write`, `chat:write.public`
   - `groups:history` (para canais privados)
4. Instale o app no workspace e copie o `Bot User OAuth Token` → `SLACK_BOT_TOKEN`
5. Em **Event Subscriptions**, ative e adicione o evento `message.channels`
6. Convide o bot para o canal: `/invite @pikpak-bot`
