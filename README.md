# Radical Red Bot

A public Discord lookup bot for Pokemon Radical Red trainer data, hosted 24/7 on AWS EC2. The bot lets players quickly look up trainer teams, route encounters, battle effects, level caps, stats, items, abilities, and moves from Discord.

## Screenshots

### Trainer Encounter Lookup

![Discord embed showing a Route 9 trainer encounter lookup](docs/images/trainer-encounter.png)

### Pokemon Stat Lookup

![Discord embed showing a Mewtwo stat lookup](docs/images/pokemon-stats.png)

## Why
 
Radical Red's trainer and encounter data lives in community-maintained Google Sheets. They're comprehensive but slow to search, and players run Radical Red with Discord already open. This bot puts that data one slash command away, backed by a normalized database instead of a live sheet scrape.
 
## Features
 
- `/trainer` — search trainers by name or location text
- `/route` — list every trainer encounter on a route or in a location
- `/pokemon` — look up base stats
- Select menus to disambiguate when a search matches multiple trainers or encounters
- Team embeds showing level, nature, ability, item, moves, stats, level cap, battle effect, starter variant, and speed at level cap where available
## Architecture
 
```
Google Sheets  →  parse_sheet.py  →  parsed_encounters.json  →  seed_db.py  →  PostgreSQL
                                                                                    ↓
                                                    Discord client  ←  FastAPI  ←  Redis cache
```
 
An offline ETL step parses the sheets into normalized tables. At runtime, FastAPI serves lookups from PostgreSQL with an optional Redis cache in front, and the Discord layer handles only command parsing and embed rendering.
 
### Design decisions
 
- **Separate API from bot.** FastAPI owns data retrieval so the same trainer data can back a future web client, and so the data layer can be exercised without a Discord connection.
- **Parse ahead of time, not per command.** Scraping the sheet on every lookup would be slow and fragile. Parsing into normalized SQLAlchemy models moves that cost to a one-time seed step.
- **Cache the hot path.** Multiple players tend to ask about the same route or boss within minutes. Responses are cached for one hour, keyed by endpoint and query. If Redis is unreachable, requests fall through to the database rather than failing.
- **Select menus over exact-match search.** Players rarely remember exact trainer names, so ambiguous queries return a picker instead of an error.
## Project layout
 
```
config.py                  Environment-backed runtime settings
api/main.py                FastAPI app and HTTP lookup endpoints
bot/main.py                Discord bot, slash commands, embed builders
cache/redis.py             Redis cache helpers
db/base.py                 SQLAlchemy declarative base
db/models.py               Pokémon, trainer, encounter, team, and move models
db/session.py              Database engine and session setup
scripts/init_db.py         Creates database tables
scripts/parse_sheet.py     Fetches and parses Google Sheet tabs into JSON
scripts/seed_db.py         Seeds parsed encounter JSON into the database
data/parsed_encounters.json  Parsed trainer encounter dataset
requirements.txt           Python dependencies
```
 
## Setup
 
**Requirements:** Python 3.10+, PostgreSQL, Redis (optional), and a Discord bot token.
 
```bash
git clone https://github.com/fangowen/radical-red-discordbot.git
cd radical-red-discordbot
 
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
 
Create a `.env` file in the project root:
 
```
DISCORD_TOKEN=your_bot_token
DATABASE_URL=postgresql://user:password@localhost:5432/radical_red
REDIS_URL=redis://localhost:6379
API_BASE_URL=http://localhost:8000
```
 
Initialize and seed the database:
 
```bash
python scripts/init_db.py
python scripts/seed_db.py
```
 
Run the API and the bot in separate terminals:
 
```bash
uvicorn api.main:app --reload
python bot/main.py
```
 
Invite the bot to a server with the `bot` and `applications.commands` scopes.
 
## Commands
 
| Command | Description | Example |
|---|---|---|
| `/trainer name:<query>` | Look up a trainer by name or location | `/trainer name:Brock` |
| `/route location:<query>` | List encounters on a route | `/route location:Route 22` |
| `/pokemon name:<query>` | Look up base stats | `/pokemon name:Mewtwo` |
 
## API endpoints
 
| Endpoint | Returns |
|---|---|
| `GET /trainer?name=` | Trainer IDs, names, classes, and encounter counts for a partial name match |
| `GET /trainer/{trainer_id}/encounters` | All encounters for one trainer |
| `GET /encounter/{encounter_id}` | Full encounter details, including team, moves, and stats |
| `GET /location?name=` | Encounters matching partial location text |
| `GET /pokemon/{name}` | Base stats for a partial name match |
 
## Refreshing the dataset
 
When the upstream community sheets change:
 
```bash
python scripts/parse_sheet.py    # rewrites data/parsed_encounters.json
python scripts/seed_db.py        # reseeds the database
```
 
The parser preserves the full trainer and location labels from the source sheets, which is what the API's partial-match search expects.
 
## Roadmap
 
- Automated tests for the API endpoints and sheet parser
- Web client over the existing API
- Incremental reseeding instead of full rebuilds
 
