# 🤖 Qwen-Agent Telegram Bot

> A privacy-first, fully local AI assistant for Telegram, powered by [LM Studio](https://lmstudio.ai) and [qwen-agent](https://github.com/QwenLM/qwen-agent).
>
> Un assistente AI locale e privacy-first per Telegram, basato su [LM Studio](https://lmstudio.ai) e [qwen-agent](https://github.com/QwenLM/qwen-agent).


Note: System prompts are in Italian by default. To use a different language, edit the system_msg strings in ask_agent() and ask_vision() in main_telegram.py
Nota: i messaggi di sistema sono in italiano per impostazione predefinita. Per utilizzare una lingua diversa, modificare le stringhe system_msg in ask_agent() e ask_vision() in main_telegram.py.


---

## ✨ Features / Funzionalità

| Feature | Description / Descrizione |
|---|---|
| 🧠 **Local LLM** | Runs entirely on your machine via LM Studio — no cloud, no data leaving your network. / Gira interamente sul tuo PC tramite LM Studio — nessun cloud, nessun dato esce dalla rete. |
| 🔍 **Web Search** | Real-time web search via [Tavily](https://tavily.com). / Ricerca web in tempo reale via Tavily. |
| 🌐 **URL Summarizer** | Send any link and get an automatic summary. Add text for custom instructions. / Invia un link e ottieni un riassunto automatico. Aggiungi testo per istruzioni personalizzate. |
| 🖼️ **Vision** | Send or quote images — the bot analyzes them using the model's multimodal capabilities. / Invia o cita immagini — il bot le analizza grazie alle capacità multimodali del modello. |
| 🧮 **Calculator** | Safe mathematical expression evaluator. / Valutatore sicuro di espressioni matematiche. |
| 📖 **Wikipedia** | Searches Italian Wikipedia without any external dependency. / Cerca su Wikipedia in italiano senza dipendenze esterne. |
| 🗂️ **File Manager** | Admin-only: read/write files in a sandboxed `workspace/` folder. / Solo admin: leggi/scrivi file in una cartella `workspace/` isolata. |
| 💬 **Reply Context** | Quote a bot reply to continue the conversation with full context. / Cita una risposta del bot per continuare la conversazione con contesto. |
| 👥 **Multi-user** | Admin + guest roles with different tool access. Users managed via `allowed_users.json`. / Ruoli admin + guest con accesso differenziato ai tool. Utenti gestiti via `allowed_users.json`. |
| 🔒 **Privacy** | Images are never saved to disk — processed in RAM only. / Le immagini non vengono mai salvate su disco — elaborate solo in RAM. |

---

## 🚀 Quick Start / Avvio Rapido

### 1. Prerequisites / Prerequisiti

- Python 3.10+
- [LM Studio](https://lmstudio.ai) with a **multimodal model** loaded (e.g. `Qwen2.5-VL`, `Qwen3.5`)
  and the local server running on `http://localhost:1234`
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A [Tavily](https://tavily.com) API key (free tier available)

### 2. Install / Installazione

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
pip install -r requirements.txt
```

### 3. Configure / Configurazione

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_user_id        # find it via @userinfobot
LM_STUDIO_URL=http://localhost:1234/v1
TAVILY_API_KEY=your_tavily_api_key
```

### 4. Add allowed users / Aggiungi utenti autorizzati

Create `allowed_users.json` with the Telegram user IDs you want to allow:

```json
[123456789, 987654321]
```

The admin ID is always included automatically. / L'admin è sempre incluso automaticamente.

### 5. Run / Avvio

```bash
python main_telegram.py
```

---

## 📁 Project Structure / Struttura del Progetto

```
├── main_telegram.py       # Bot logic / Logica del bot
├── op_tools.py            # qwen-agent tools / Tool per qwen-agent
├── allowed_users.json     # Authorized user IDs (NOT in repo) / ID utenti autorizzati (NON nel repo)
├── .env                   # Secrets (NOT in repo) / Segreti (NON nel repo)
├── .env.example           # Config template / Template configurazione
├── requirements.txt       # Python dependencies / Dipendenze Python
└── workspace/             # Agent file sandbox (auto-created) / Sandbox file agente (creata automaticamente)
```

---

## 🛠️ Tool Access by Role / Accesso ai Tool per Ruolo

| Tool | Guest | Admin |
|---|:---:|:---:|
| `my_web_search` — Tavily web search | ✅ | ✅ |
| `fetch_url` — Download & summarize any URL | ✅ | ✅ |
| `wikipedia_search` — Italian Wikipedia | ✅ | ✅ |
| `calculate` — Math expressions | ✅ | ✅ |
| `get_datetime` — Current date/time | ✅ | ✅ |
| `manage_files` — Read/write `workspace/` | ❌ | ✅ |

---

## 💡 Usage Examples / Esempi d'Uso

| Action / Azione | How / Come |
|---|---|
| Ask a question / Fai una domanda | Send a message in private, or `@bot` in a group |
| Summarize a URL / Riassumi un link | Send just the URL — summary is automatic |
| Custom URL instruction / Istruzione su URL | `@bot what are the prices on https://example.com` |
| Analyze an image / Analizza un'immagine | Send a photo (private), or send with `@bot` caption in a group |
| Analyze someone else's photo / Analizza foto altrui | Reply to the photo with `@bot what's in this image?` |
| Continue a conversation / Continua una conversazione | Quote a bot reply and ask a follow-up |

---

## ⚙️ Configuration Notes / Note di Configurazione

- **Model**: Change `MODEL_NAME` in `main_telegram.py` to use a different model.
  / Cambia `MODEL_NAME` in `main_telegram.py` per usare un modello diverso.
- **Context limit**: `fetch_url` returns up to 8000 chars. Adjust in `op_tools.py` based on your model's context window.
  / `fetch_url` restituisce fino a 8000 caratteri. Regola in `op_tools.py` in base al contesto del modello.
- **Logs**: Stored in `bot.log` with automatic rotation (2MB × 3 files = 8MB max).
  / Salvati in `bot.log` con rotazione automatica (2MB × 3 file = 8MB max).

---

## 🔮 Planned Features / Sviluppi Futuri

- [ ] Document support (PDF, Word, txt) via Telegram file handler
- [ ] Response streaming via `sendMessageDraft` (Telegram Bot API 9.5)
- [ ] Persistent conversation memory

---

## 🔮 Test Suite
| RTX 4060ti 16gb
| Context window: 25115 token 
| Offload GPU : 32
| LM Studio 0.4.2


## 📄 License

MIT
