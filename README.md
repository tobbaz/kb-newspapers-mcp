# KB Gamla Tidningar MCP Server

En [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)-server som ger AI-assistenter (t.ex. Antigravity, Claude Desktop, Cursor) direkt tillgång till Kungliga bibliotekets (KB) digitaliserade historiska dagstidningar från 1600-talet fram till ca 1908–1910.

Byggd i Python med **FastMCP** och **uv**.

---

## Egenskaper

- 🔍 **Fulltextsökning (OCR):** Sök i över 2,2 miljoner historiska tidningssidor med automatiska textutdrag (*snippets*) där söktermerna markeras.
- 📅 **Filtrering & Sortering:** Sök inom specifika tidsperioder (t.ex. `1850` till `1880` eller exakta datum), filtrera på specifika tidningar (t.ex. *Aftonbladet*, *Dagens Nyheter*, *Post- och Inrikes Tidningar*), och sortera efter relevans eller datum.
- 📈 **Tidslinje & Statistik:** Se hur ofta ett ord, namn eller företeelse förekommer över decennier och mellan olika tidningar.
- 🖼️ **Högupplösta bilder (IIIF):** Direktgenerering av länkar till tidningssidor i valfri upplösning via KB:s IIIF Image API (både tumnaglar och helsidesbilder).
- 🔗 **Webblänkar:** Automatisk koppling till [tidningar.kb.se](https://tidningar.kb.se) och [digitalt.kb.se](https://digitalt.kb.se).
- 🕊️ **Fair Use:** Inbyggd exponential backoff vid rate limits (`HTTP 429`/`503`) och identifierande `User-Agent`.

---

## Förutsättningar

- [uv](https://docs.astral.sh/uv/) installerat:
  ```bash
  brew install uv
  ```

---

## Installation & Snabbstart

1. Klona repot:
   ```bash
   git clone https://github.com/tobbaz/kb-tidningar-mcp.git
   cd kb-tidningar-mcp
   ```

2. Testa att köra servern lokalt:
   ```bash
   uv run kb-tidningar-mcp
   ```

3. Kör testerna för att verifiera anslutningen till KB:s API:
   ```bash
   uv run python test_server.py
   ```

---

## Konfiguration

### I Antigravity / Gemini CLI (`~/.gemini/config/mcp_config.json`)
Lägg till under `mcpServers`:

```json
{
  "mcpServers": {
    "kb-tidningar": {
      "command": "/usr/local/bin/uv",
      "args": [
        "run",
        "--directory",
        "/Users/tobbe/Genealogy/AI/mcp/kb-tidningar-mcp",
        "kb-tidningar-mcp"
      ]
    }
  }
}
```

### I Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "kb-tidningar": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolut/sokvag/till/kb-tidningar-mcp",
        "kb-tidningar-mcp"
      ]
    }
  }
}
```

---

## Tillgängliga Verktyg (Tools)

### 1. `search_newspapers`
Huvudverktyg för att söka i tidningsartiklar och sidor.
- `query` *(sträng, obligatorisk)*: Sökord eller fras (t.ex. `"ångfartyg"`, `"Carl von Linné"`, `"August Strindberg"`).
- `from_date` *(valfritt)*: Startdatum (t.ex. `'1850'` eller `'1850-01-01'`).
- `to_date` *(valfritt)*: Slutdatum (t.ex. `'1899'` eller `'1899-12-31'`).
- `newspaper` *(valfritt)*: Begränsa till specifik tidning (t.ex. `'Aftonbladet'`, `'Post- och inrikes tidningar'`).
- `sort_by` *(valfritt)*: `'relevance'` (standard), `'date_asc'` eller `'date_desc'`.
- `limit` *(int, default 20, max 100)*: Antal träffar per sida.
- `offset` *(int, default 0)*: Pagineringsoffset.
- `max_snippets` *(int, default 5)*: Antal textutdrag per tidningssida.

### 2. `get_newspaper_timeline`
Hämtar historisk frekvens eller fördelning mellan tidningar för ett sökord.
- `query` *(sträng, obligatorisk)*: Sökord (t.ex. `'kolera'`).
- `field` *(valfritt)*: `'datePublished'` (fördelning över årtal) eller `'isPartOf'` (fördelning över tidningar).

### 3. `search_in_issue`
Söker inom ett enskilt tidningsnummer med IIIF Content Search och returnerar alla träffar med exakta citat och koordinater.
- `package_id` *(sträng, obligatorisk)*: Tidningsnumrets paket-ID (t.ex. `'dark-37858'`).
- `query` *(sträng, obligatorisk)*: Sökord.

### 4. `get_newspaper_page_image`
Genererar IIIF-bildlänkar och webblänkar för en tidningssida.
- `image_service_id` *(valfritt)*: IIIF Service URL från sökträff.
- `package_id` *(valfritt)*: Paket-ID (t.ex. `'dark-30466'`).
- `page_number` *(int, default 1)*: Sidnummer.
- `width` *(int, default 1200)*: Bildbredd i pixlar.

### 5. `lookup_newspaper_id`
Konverterar dubbelriktat mellan `data.kb.se`-paket-ID och webbadress på `tidningar.kb.se`.
- `id_or_url` *(sträng, obligatorisk)*: T.ex. `'dark-37858'` eller `'https://tidningar.kb.se/dxqth86q2n2zwg9'`.

---

## Om materialet och upphovsrätt

Kungliga bibliotekets digitaliserade tidningar före ca 1908–1910 är fria från upphovsrätt (Public Domain) och tillhandahålls som öppna data via [data.kb.se](https://data.kb.se). Moderna tidningar omfattas av upphovsrätt och ingår därför inte i detta öppna API.

## Licens

MIT License.
Metadata och digitaliserat material tillhandahålls av [Kungliga biblioteket (KB)](https://www.kb.se).
