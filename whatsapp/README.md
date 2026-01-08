# WhatsApp Bridge (Baileys)

This Node.js service connects WhatsApp (via Baileys) to the Flask chatbot API.

## Prerequisites
- Node.js 18+
- QR pairing with the WhatsApp account you want to use.
- Flask API reachable (default `http://127.0.0.1:5000/api/chat`).

## Setup
```bash
cd whatsapp
npm install
```

## Environment
Reads the root `.env` by default. You can override:
```
CHATBOT_API_URL=http://127.0.0.1:5000/api/chat
CHATBOT_LANG=en             # ar for Arabic
WHATSAPP_DEVICE_NAME=YouLearnt Bot
WHATSAPP_AUTH_DIR=./auth_info
WHATSAPP_LOG_LEVEL=info
WHATSAPP_API_TIMEOUT=20000  # ms
```

## Run
```bash
cd whatsapp
npm start
```
- Scan the QR shown in the terminal with the target WhatsApp account.
- Incoming messages are forwarded to the chatbot and replies are sent back.

## Notes
- Auth files are stored under `whatsapp/auth_info/` and are git-ignored.
- To re-link, delete the `auth_info` folder and restart to get a new QR.
- Keep the Flask app running; this service just bridges WhatsApp <-> chatbot.
