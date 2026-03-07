import os
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from qwen_agent.tools.base import BaseTool, register_tool
from tavily import TavilyClient


# ---------------------------------------------------------------------------
# TOOL 1: WEB SEARCH / RICERCA WEB
# Available to: admin + guest / Disponibile a: admin + guest
# ---------------------------------------------------------------------------
@register_tool('my_web_search')
class MyWebSearch(BaseTool):
    description = 'Cerca informazioni aggiornate sul web tramite Tavily. / Search the web for up-to-date information using Tavily.'
    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': 'La query di ricerca / The search query',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        try:
            p = json.loads(params)
        except:
            p = {'query': params}
        search_result = tavily.search(query=p['query'], search_depth="advanced")
        return str(search_result)


# ---------------------------------------------------------------------------
# TOOL 2: FILE MANAGEMENT / GESTIONE FILE
# Available to: admin only / Disponibile a: solo admin
# Sandboxed to the workspace/ folder — cannot access anything outside it.
# Limitato alla cartella workspace/ — non puo' accedere a nulla al di fuori.
# ---------------------------------------------------------------------------
@register_tool('manage_files')
class ManageFiles(BaseTool):
    description = (
        'Crea o legge file nella cartella workspace. Usa "write" per scrivere e "read" per leggere. '
        '/ Create or read files in the workspace folder. Use "write" to write and "read" to read.'
    )
    parameters = [{
        'name': 'action',
        'type': 'string',
        'description': '"write" to create a file, "read" to read it / "write" per creare, "read" per leggere',
        'required': True
    }, {
        'name': 'filename',
        'type': 'string',
        'description': 'File name with extension / Nome file con estensione (es. notes.txt)',
        'required': True
    }, {
        'name': 'content',
        'type': 'string',
        'description': 'Text content to write (only for write action) / Testo da scrivere (solo per write)',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        base_path = os.path.join(os.getcwd(), "workspace")
        if not os.path.exists(base_path):
            os.makedirs(base_path)

        try:
            p = json.loads(params)
        except:
            return "Errore: parametri non validi. / Error: invalid parameters."

        action   = p.get('action')
        filename = p.get('filename')
        content  = p.get('content', '')

        # Security: prevent path traversal outside workspace/
        # Sicurezza: impedisce path traversal fuori da workspace/
        file_path = os.path.normpath(os.path.join(base_path, filename))
        if not file_path.startswith(base_path):
            return "Errore: accesso negato fuori dalla cartella workspace. / Error: access denied outside workspace."

        if action == "write":
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"File '{filename}' creato con successo. / File '{filename}' created successfully."
        elif action == "read":
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return f"Errore: il file '{filename}' non esiste. / Error: file '{filename}' does not exist."

        return "Azione non riconosciuta. Usa 'write' o 'read'. / Unknown action. Use 'write' or 'read'."


# ---------------------------------------------------------------------------
# TOOL 3: DATE AND TIME / DATA E ORA
# Available to: admin + guest / Disponibile a: admin + guest
# ---------------------------------------------------------------------------
@register_tool('get_datetime')
class GetDatetime(BaseTool):
    description = (
        'Returns the current system date and time. Use it whenever the user asks what day or time it is. '
        '/ Restituisce la data e ora corrente del sistema. Usalo quando l\'utente chiede che giorno o che ora e\'.'
    )
    parameters = []  # No parameters required / Nessun parametro richiesto

    def call(self, params: str, **kwargs) -> str:
        now = datetime.now()
        return (
            f"Date / Data: {now.strftime('%A %d %B %Y')}\n"
            f"Time / Ora:  {now.strftime('%H:%M:%S')}"
        )


# ---------------------------------------------------------------------------
# TOOL 4: CALCULATOR / CALCOLATRICE
# Available to: admin + guest / Disponibile a: admin + guest
# Safe eval: only math.* namespace, no dangerous builtins.
# Eval sicuro: solo namespace math.*, nessun builtin pericoloso.
# ---------------------------------------------------------------------------
@register_tool('calculate')
class Calculate(BaseTool):
    description = (
        'Performs mathematical calculations. Supports arithmetic, powers, roots, logarithms, '
        'trigonometric functions and constants like pi and e. '
        'Examples: "2**10", "sqrt(144)", "sin(pi/2)", "log(100, 10)". '
        '/ Esegue calcoli matematici. Supporta aritmetica, potenze, radici, logaritmi, '
        'funzioni trigonometriche e costanti come pi ed e.'
    )
    parameters = [{
        'name': 'expression',
        'type': 'string',
        'description': 'Mathematical expression to evaluate / Espressione matematica da calcolare',
        'required': True
    }]

    _SAFE_GLOBALS = {k: getattr(math, k) for k in dir(math) if not k.startswith('_')}
    _SAFE_GLOBALS.update({'abs': abs, 'round': round})

    def call(self, params: str, **kwargs) -> str:
        try:
            p = json.loads(params)
        except:
            p = {'expression': params}

        expr = p.get('expression', '').strip()
        if not expr:
            return "Errore: nessuna espressione. / Error: no expression provided."

        try:
            result = eval(expr, {"__builtins__": {}}, self._SAFE_GLOBALS)
            return f"{expr} = {result}"
        except ZeroDivisionError:
            return "Errore: divisione per zero. / Error: division by zero."
        except Exception as e:
            return f"Errore nel calcolo / Calculation error: {e}"


# ---------------------------------------------------------------------------
# TOOL 5: WIKIPEDIA SEARCH / RICERCA WIKIPEDIA
# Available to: admin + guest / Disponibile a: admin + guest
# Uses the Italian Wikipedia REST API — no external dependencies.
# Usa le API REST di Wikipedia in italiano — nessuna dipendenza esterna.
# ---------------------------------------------------------------------------
@register_tool('wikipedia_search')
class WikipediaSearch(BaseTool):
    description = (
        'Searches Wikipedia (Italian) and returns a summary. Useful for definitions, biographies, '
        'historical events and general encyclopedic information. '
        '/ Cerca su Wikipedia in italiano e restituisce un riassunto. Utile per definizioni, '
        'biografie, eventi storici e informazioni enciclopediche.'
    )
    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': 'Topic to search / Argomento da cercare',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        try:
            p = json.loads(params)
        except:
            p = {'query': params}

        query = p.get('query', '').strip()
        if not query:
            return "Errore: nessuna query. / Error: no query provided."

        try:
            encoded = urllib.parse.quote(query)
            url = f"https://it.wikipedia.org/api/rest_v1/page/summary/{encoded}"
            req = urllib.request.Request(url, headers={'User-Agent': 'qwen-agent-bot/1.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            title   = data.get('title', query)
            extract = data.get('extract', '')

            if not extract:
                return f"Nessun risultato per '{query}'. / No results for '{query}'."

            # Limit to ~800 chars to avoid overloading context
            # Limita a ~800 chars per non sovraccaricare il contesto
            if len(extract) > 800:
                extract = extract[:800] + "..."

            return f"**{title}**\n{extract}"

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return f"Nessuna pagina Wikipedia per '{query}'. / No Wikipedia page for '{query}'."
            return f"Errore HTTP / HTTP error: {e.code}"
        except Exception as e:
            return f"Errore Wikipedia / Wikipedia error: {e}"


# ---------------------------------------------------------------------------
# TOOL 6: URL FETCHER / FETCH PAGINA WEB
# Available to: admin + guest / Disponibile a: admin + guest
# Downloads and extracts plain text from a web page.
# Scarica ed estrae il testo da una pagina web.
# No external dependencies — uses stdlib urllib + html.parser.
# Nessuna dipendenza esterna — usa stdlib urllib + html.parser.
# ---------------------------------------------------------------------------
@register_tool('fetch_url')
class FetchUrl(BaseTool):
    description = (
        'Downloads and returns the text content of a web page given its URL. '
        'Use it when the user provides a link and wants a summary or information from the page. '
        '/ Scarica e restituisce il contenuto testuale di una pagina web dato il suo URL. '
        'Usalo quando l\'utente fornisce un link e vuole un riassunto o informazioni dalla pagina.'
    )
    parameters = [{
        'name': 'url',
        'type': 'string',
        'description': 'Full URL of the page / URL completo della pagina (es. https://example.com)',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        try:
            p = json.loads(params)
        except:
            p = {'url': params}

        url = p.get('url', '').strip()
        if not url:
            return "Errore: nessun URL. / Error: no URL provided."

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw     = resp.read()
                charset = resp.headers.get_content_charset() or 'utf-8'
                html    = raw.decode(charset, errors='replace')

            # Strip HTML tags using stdlib html.parser
            # Rimuove i tag HTML usando html.parser della stdlib
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.chunks = []
                    self._skip  = False

                def handle_starttag(self, tag, attrs):
                    if tag in ('script', 'style', 'nav', 'footer'):
                        self._skip = True

                def handle_endtag(self, tag):
                    if tag in ('script', 'style', 'nav', 'footer'):
                        self._skip = False

                def handle_data(self, data):
                    if not self._skip:
                        text = data.strip()
                        if text:
                            self.chunks.append(text)

            extractor = TextExtractor()
            extractor.feed(html)
            text = '\n'.join(extractor.chunks)

            # Limit to 8000 chars to stay within model context window
            # Limita a 8000 chars per restare nel contesto del modello
            if len(text) > 8000:
                text = text[:8000] + '...'

            return text if text else "Nessun contenuto testuale trovato. / No text content found."

        except urllib.error.HTTPError as e:
            return f"Errore HTTP {e.code} / HTTP error {e.code}: cannot download page."
        except Exception as e:
            return f"Errore fetch URL / Fetch URL error: {e}"
