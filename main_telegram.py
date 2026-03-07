import os
import json
import re
import base64
import logging
import threading
import urllib.request
from logging.handlers import RotatingFileHandler
import telebot
from dotenv import load_dotenv
from qwen_agent.agents import Assistant
import op_tools  # Registers: my_web_search, manage_files, get_datetime, calculate, wikipedia_search, fetch_url
               # Registra:  my_web_search, manage_files, get_datetime, calculate, wikipedia_search, fetch_url

load_dotenv()

# ---------------------------------------------------------------------------
# LOGGING
# Automatic rotation: max 2MB per file, 3 backups (8MB total on disk)
# Rotazione automatica: max 2MB per file, 3 backup (8MB totali su disco)
# ---------------------------------------------------------------------------
_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
_file_handler = RotatingFileHandler(
    'bot.log', maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8'
)
_file_handler.setFormatter(_fmt)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONFIGURATION / CONFIGURAZIONE
# ---------------------------------------------------------------------------
bot = telebot.TeleBot(os.getenv("TELEGRAM_TOKEN"))
ADMIN_ID   = int(os.getenv("ADMIN_ID"))
JSON_FILE  = "allowed_users.json"
LM_URL     = os.getenv("LM_STUDIO_URL")   # e.g. / es. http://localhost:1234/v1
MODEL_NAME = "qwen/qwen3.5-9b"            # change here to upgrade / cambia qui per aggiornare il modello

BOT_INFO     = bot.get_me()
BOT_ID       = BOT_INFO.id
BOT_USERNAME = BOT_INFO.username

llm_cfg = {
    'model': MODEL_NAME,
    'model_server': LM_URL,
    'api_key': 'lm-studio',
    'generate_cfg': {'temperature': 0.5}
}

# Tool lists by user role / Liste tool per ruolo utente
# Guest: web search + safe read-only tools (no filesystem access)
# Guest: ricerca web + tool sicuri read-only (nessun accesso al filesystem)
GUEST_TOOLS  = ['my_web_search', 'fetch_url', 'get_datetime', 'calculate', 'wikipedia_search']

# Admin: everything + file management in workspace/
# Admin: tutto + gestione file nella cartella workspace/
MASTER_TOOLS = ['manage_files'] + GUEST_TOOLS

# ---------------------------------------------------------------------------
# ALLOWED USERS CACHE / CACHE UTENTI AUTORIZZATI
# Re-reads allowed_users.json only if the file mtime has changed.
# Rilegge allowed_users.json solo se la data di modifica e' cambiata.
# ---------------------------------------------------------------------------
_users_cache: tuple = (None, None)  # (mtime, user_list) / (mtime, lista_utenti)

def get_allowed_users() -> list[int]:
    global _users_cache

    if not os.path.exists(JSON_FILE):
        log.warning("%s not found, using ADMIN_ID only.", JSON_FILE)
        return [ADMIN_ID]

    mtime = os.path.getmtime(JSON_FILE)
    if _users_cache[0] == mtime:
        return _users_cache[1]  # cache hit, no disk read / cache valida, nessuna lettura disco

    log.info("Reloading %s (mtime changed).", JSON_FILE)
    try:
        with open(JSON_FILE, 'r') as f:
            data = json.loads(f.read().strip())

        if isinstance(data, list):
            flat = []
            for item in data:
                if isinstance(item, list):
                    flat.extend(item)
                else:
                    flat.append(item)
            users = [int(u) for u in flat]
        elif isinstance(data, dict):
            raw_list = data.get("users") or data.get("allowed") or list(data.values())[0]
            users = [int(u) for u in raw_list]
        else:
            users = [int(data)]

        if ADMIN_ID not in users:
            users.append(ADMIN_ID)

        _users_cache = (mtime, users)
        log.info("Authorized users: %s", users)
        return users

    except Exception as e:
        log.error("Error reading %s: %s — using ADMIN_ID only.", JSON_FILE, e)
        return [ADMIN_ID]

# ---------------------------------------------------------------------------
# TYPING LOOP
# Keeps "typing..." indicator alive every 4s for the full duration of processing.
# Mantiene attivo "sta scrivendo..." ogni 4s per tutta la durata dell'elaborazione.
# ---------------------------------------------------------------------------
def start_typing(chat_id: int) -> threading.Event:
    stop_event = threading.Event()

    def _loop():
        while not stop_event.is_set():
            try:
                bot.send_chat_action(chat_id, 'typing')
            except Exception:
                pass
            stop_event.wait(timeout=4)

    threading.Thread(target=_loop, daemon=True).start()
    return stop_event

# ---------------------------------------------------------------------------
# MESSAGE SPLITTER / SPLIT MESSAGGIO
# Telegram has a 4096 character limit per message.
# Telegram ha un limite di 4096 caratteri per messaggio.
# ---------------------------------------------------------------------------
def split_message(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        # Try to split on newline to avoid cutting mid-sentence
        # Cerca di spezzare su newline per non troncare frasi a meta'
        split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks

# ---------------------------------------------------------------------------
# THINKING TAG CLEANER / PULIZIA THINKING TAGS
# Removes <think>...</think> blocks (including incomplete ones) from model output.
# Rimuove blocchi <think>...</think> (anche incompleti) dall'output del modello.
# ---------------------------------------------------------------------------
def clean_think(text: str) -> str:
    return re.sub(r'(<think>)?.*?</think>', '', text, flags=re.DOTALL).strip()

# ---------------------------------------------------------------------------
# REPLY CONTEXT HELPERS / HELPER CONTESTO DA CITAZIONE
# ---------------------------------------------------------------------------
def get_reply_context(message) -> str | None:
    """Returns the bot's previous response if the user quoted it, else None.
    / Restituisce la risposta citata se e' del bot, altrimenti None."""
    if (
        message.reply_to_message and
        message.reply_to_message.from_user.id == BOT_ID and
        message.reply_to_message.text
    ):
        return message.reply_to_message.text
    return None

def get_reply_photo(message) -> bytes | None:
    """Downloads and returns image bytes if the user tagged the bot
    in reply to another user's photo.
    / Scarica e restituisce i bytes se il bot viene taggato
    in risposta a una foto di un altro utente."""
    if (
        message.reply_to_message and
        message.reply_to_message.from_user.id != BOT_ID and
        message.reply_to_message.photo
    ):
        file_id   = message.reply_to_message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_url  = f"https://api.telegram.org/file/bot{os.getenv('TELEGRAM_TOKEN')}/{file_info.file_path}"
        with urllib.request.urlopen(file_url, timeout=15) as resp:
            return resp.read()
    return None

# ---------------------------------------------------------------------------
# TEXT AGENT (qwen-agent) — with optional conversation history
# AGENTE TESTUALE (qwen-agent) — con history opzionale
# ---------------------------------------------------------------------------
def ask_agent(user_query: str, is_master: bool, reply_context: str | None = None) -> str:
    if is_master:
        system_msg = (
            "Sei un assistente italiano. Rispondi in modo chiaro e cordiale. "
            "Sei il Master. Puoi gestire file nel workspace, cercare sul web, "
            "fare calcoli e cercare su Wikipedia."
        )
        tools = MASTER_TOOLS
    else:
        system_msg = (
            "Sei un assistente italiano. Rispondi in modo chiaro e cordiale. "
            "Sei in modalita' ospite. Puoi cercare sul web, fare calcoli, "
            "cercare su Wikipedia e consultare data/ora."
        )
        tools = GUEST_TOOLS

    agent = Assistant(
        llm=llm_cfg,
        system_message=system_msg,
        function_list=tools
    )

    # Inject previous bot reply as conversation history if present.
    # LM Studio requires history to always start with a user turn.
    # Inietta la risposta citata come history. LM Studio richiede
    # che la history inizi sempre con un turno user.
    messages = []
    if reply_context:
        messages.append({'role': 'user',      'content': '...'})
        messages.append({'role': 'assistant', 'content': reply_context})
    messages.append({'role': 'user', 'content': user_query})

    response_text = ""
    for response in agent.run(messages):
        response_text = response[-1]['content']

    return clean_think(response_text)

# ---------------------------------------------------------------------------
# VISION — direct LM Studio call, bypasses qwen-agent (no image support there)
# VISION — chiamata diretta a LM Studio, bypassa qwen-agent (non supporta immagini)
# Supports optional text + optional reply context.
# Supporta testo opzionale + contesto da citazione opzionale.
# Images are kept in RAM only, never written to disk.
# Le immagini restano solo in RAM, non vengono mai scritte su disco.
# ---------------------------------------------------------------------------
def ask_vision(image_bytes: bytes, user_text: str, reply_context: str | None = None) -> str:
    b64 = base64.b64encode(image_bytes).decode('utf-8')

    # Build user message: text + image / Costruisce il messaggio: testo + immagine
    user_content = []
    if user_text:
        user_content.append({"type": "text", "text": user_text})
    user_content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
    })

    messages = [
        {
            "role": "system",
            "content": (
                "Sei un assistente italiano. Rispondi in modo chiaro e cordiale. "
                "Analizza le immagini che ti vengono fornite e descrivi o rispondi "
                "alle domande in italiano."
            )
        }
    ]

    if reply_context:
        messages.append({"role": "assistant", "content": reply_context})

    messages.append({"role": "user", "content": user_content})

    payload = json.dumps({
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.5,
        "stream": False,
    }).encode('utf-8')

    req = urllib.request.Request(
        f"{LM_URL}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))

    raw = data['choices'][0]['message']['content']
    return clean_think(raw)

# ---------------------------------------------------------------------------
# TEXT MESSAGE HANDLER / HANDLER MESSAGGI DI TESTO
# ---------------------------------------------------------------------------
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    if user_id not in get_allowed_users():
        return

    is_private      = message.chat.type == 'private'
    is_mention      = f"@{BOT_USERNAME}" in message.text
    is_reply_to_bot = bool(
        message.reply_to_message and
        message.reply_to_message.from_user.id == BOT_ID
    )

    # In groups, only respond if mentioned or replied to
    # Nei gruppi, risponde solo se taggato o se e' una reply al bot
    if not is_private and not (is_mention or is_reply_to_bot):
        return

    log.info("Text from user_id=%s | chat_type=%s", user_id, message.chat.type)

    clean_text = message.text.replace(f"@{BOT_USERNAME}", "").strip()
    is_master  = (user_id == ADMIN_ID)

    # Auto-summarize if message is just a URL (with up to 3 chars tolerance for typos)
    # Riassunto automatico se il messaggio e' solo un URL (tolleranza 3 chars per typo)
    url_match = re.search(r'https?://\S+', clean_text)
    if url_match:
        testo_extra = clean_text.replace(url_match.group(), '').strip()
        if len(testo_extra) <= 3:
            clean_text = f"Riassumi il contenuto di questa pagina web: {url_match.group()}"

    reply_context = get_reply_context(message)
    reply_photo   = get_reply_photo(message)

    if reply_context:
        log.info("  -> with reply context (%d chars)", len(reply_context))
    if reply_photo:
        log.info("  -> photo quoted from another user, routing to vision")

    stop_typing = start_typing(message.chat.id)
    try:
        if reply_photo:
            # User tagged bot in reply to someone else's photo
            # L'utente ha taggato il bot in risposta a una foto altrui
            answer = ask_vision(reply_photo, clean_text, reply_context)
        else:
            answer = ask_agent(clean_text, is_master, reply_context)
        stop_typing.set()
        for i, chunk in enumerate(split_message(answer)):
            bot.reply_to(message, chunk) if i == 0 else bot.send_message(message.chat.id, chunk)
    except Exception as e:
        stop_typing.set()
        log.error("Error in handle_text: %s", e, exc_info=True)
        bot.reply_to(message, "⚠️ Si e' verificato un errore, riprova.")

# ---------------------------------------------------------------------------
# PHOTO HANDLER / HANDLER FOTO
# ---------------------------------------------------------------------------
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if user_id not in get_allowed_users():
        return

    is_private      = message.chat.type == 'private'
    is_mention      = bool(message.caption and f"@{BOT_USERNAME}" in message.caption)
    is_reply_to_bot = bool(
        message.reply_to_message and
        message.reply_to_message.from_user.id == BOT_ID
    )

    if not is_private and not (is_mention or is_reply_to_bot):
        return

    log.info("Photo from user_id=%s | chat_type=%s", user_id, message.chat.type)

    # Always use highest resolution available / Usa sempre la risoluzione piu' alta disponibile
    file_id   = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    file_url  = f"https://api.telegram.org/file/bot{os.getenv('TELEGRAM_TOKEN')}/{file_info.file_path}"

    # Optional caption + optional reply context
    # Caption opzionale + contesto da citazione opzionale
    user_text = (message.caption or "").replace(f"@{BOT_USERNAME}", "").strip()
    if not user_text:
        user_text = "Descrivi questa immagine."
    reply_context = get_reply_context(message)

    if reply_context:
        log.info("  -> photo with reply context (%d chars)", len(reply_context))

    stop_typing = start_typing(message.chat.id)
    try:
        with urllib.request.urlopen(file_url, timeout=15) as resp:
            image_bytes = resp.read()

        answer = ask_vision(image_bytes, user_text, reply_context)
        stop_typing.set()
        for i, chunk in enumerate(split_message(answer)):
            bot.reply_to(message, chunk) if i == 0 else bot.send_message(message.chat.id, chunk)
    except Exception as e:
        stop_typing.set()
        log.error("Error in handle_photo: %s", e, exc_info=True)
        bot.reply_to(message, "⚠️ Errore con l'immagine, riprova.")


log.info("Bot ONLINE — Qwen-Agent + Vision.")
bot.infinity_polling()
