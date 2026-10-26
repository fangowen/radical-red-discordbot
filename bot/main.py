import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from urllib.parse import quote

from config import API_URL, BOT_TOKEN

REQUEST_TIMEOUT_SECONDS = 10

intents = discord.Intents.default()


class RadicalRedBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.api_session = None

    async def setup_hook(self):
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        self.api_session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        if self.api_session and not self.api_session.closed:
            await self.api_session.close()
        await super().close()


bot = RadicalRedBot()


async def fetch(path, params=None):
    if bot.api_session is None or bot.api_session.closed:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        bot.api_session = aiohttp.ClientSession(timeout=timeout)

    try:
        async with bot.api_session.get(f"{API_URL}{path}", params=params) as response:
            if response.status == 404:
                return None
            response.raise_for_status()
            return await response.json()
    except (aiohttp.ClientError, TimeoutError):
        return None


def missing_value(value):
    return value if value not in (None, "") else "Unknown"

class EncounterSelect(discord.ui.Select):
    def __init__(self, encounters):
        options = [
            discord.SelectOption(
                label=f"{e['location']} {('(' + e['starter_variant'] + ')') if e.get('starter_variant') else ''}".strip(),
                description=f"Level cap: {e.get('level_cap') or 'N/A'}",
                value=str(e.get('encounter_id') or e.get('id'))
            )
            for e in encounters[:25]
        ]
        super().__init__(placeholder="Choose an encounter...", options=options)

    async def callback(self, interaction: discord.Interaction):
        # Acknowledge within Discord's 3-second window before calling the API
        await interaction.response.defer()
        encounter_id = self.values[0]
        data = await fetch(f"/encounter/{encounter_id}")
        if not data:
            await interaction.followup.send("Encounter not found.", ephemeral=True)
            return
        embed = build_encounter_embed(data)
        await interaction.edit_original_response(content=None, embed=embed, view=None)

class EncounterView(discord.ui.View):
    def __init__(self, encounters):
        super().__init__()
        self.add_item(EncounterSelect(encounters))

class TrainerSelect(discord.ui.Select):
    def __init__(self, trainers):
        options = [
            discord.SelectOption(
                label=t['name'],
                description=t['trainer_class'],
                value=str(t['id'])
            )
            for t in trainers[:25]
        ]
        super().__init__(placeholder="Choose a trainer...", options=options)

    async def callback(self, interaction: discord.Interaction):
        # Acknowledge within Discord's 3-second window before calling the API
        await interaction.response.defer()
        trainer_id = self.values[0]
        encounters = await fetch(f"/trainer/{trainer_id}/encounters")

        if not encounters:
            await interaction.followup.send("No encounters found.", ephemeral=True)
            return

        if len(encounters) == 1:
            data = await fetch(f"/encounter/{encounters[0]['id']}")
            if not data:
                await interaction.followup.send("Encounter not found.", ephemeral=True)
                return
            embed = build_encounter_embed(data)
            await interaction.edit_original_response(content=None, embed=embed, view=None)
        else:
            view = EncounterView(encounters)
            await interaction.edit_original_response(
                content="Multiple encounters found — which one?",
                embed=None,
                view=view
            )

class TrainerView(discord.ui.View):
    def __init__(self, trainers):
        super().__init__()
        self.add_item(TrainerSelect(trainers))

def build_encounter_embed(data):
    embed = discord.Embed(
        title=data["location"],
        color=0xFF0000
    )

    if data.get("battle_effect"):
        embed.add_field(name="⚡ Battle Effect", value=data["battle_effect"], inline=False)

    if data.get("level_cap"):
        embed.add_field(name="📊 Level Cap", value=str(data["level_cap"]), inline=True)

    if data.get("starter_variant"):
        embed.add_field(name="🎮 Starter Variant", value=data["starter_variant"].title(), inline=True)

    for mon in data["team"]:
        moves = " / ".join(mon["moves"]) if mon["moves"] else "No moves"
        stats = mon["stats"]
        speed_info = f"\n⚡ Speed at cap: **{mon['speed_at_level_cap']}**" if mon.get("speed_at_level_cap") else ""
        value = (
            f"**{missing_value(mon['nature'])} | {missing_value(mon['ability'])}**\n"
            f"Item: {mon['item'] or 'None'}\n"
            f"Moves: {moves}\n"
            f"HP:{missing_value(stats['hp'])} ATK:{missing_value(stats['attack'])} DEF:{missing_value(stats['defense'])} "
            f"SPA:{missing_value(stats['sp_attack'])} SPD:{missing_value(stats['sp_defense'])} SPE:{missing_value(stats['speed'])}"
            f"{speed_info}"
        )
        embed.add_field(
            name=f"{mon['pokemon']} (Lv {mon['level'] or '?'})",
            value=value,
            inline=False
        )

    return embed


def build_pokemon_embed(data):
    title = data["name"]
    if data.get("dex_number"):
        title = f"{title} (#{data['dex_number']})"

    embed = discord.Embed(title=title, color=0xFF0000)
    types = " / ".join(t for t in [data.get("type1"), data.get("type2")] if t)
    abilities = [data.get("ability")]
    if data.get("hidden_ability"):
        abilities.append(f"Hidden: {data['hidden_ability']}")

    if types:
        embed.add_field(name="Type", value=types, inline=True)
    if any(abilities):
        embed.add_field(name="Abilities", value="\n".join(a for a in abilities if a), inline=True)

    stats = data["stats"]
    stat_fields = [
        ("❤️ HP", "hp"),
        ("⚔️ Attack", "attack"),
        ("🛡️ Defense", "defense"),
        ("✨ Sp. Atk", "sp_attack"),
        ("🔰 Sp. Def", "sp_defense"),
        ("⚡ Speed", "speed"),
    ]
    for label, key in stat_fields:
        embed.add_field(name=label, value=str(missing_value(stats.get(key))), inline=True)

    known_stats = [value for value in stats.values() if isinstance(value, int)]
    if known_stats:
        embed.add_field(name="📊 Base Stat Total", value=str(sum(known_stats)), inline=False)

    return embed

async def send_encounter(interaction: discord.Interaction, encounter_id):
    data = await fetch(f"/encounter/{encounter_id}")
    if not data:
        await interaction.followup.send("Encounter not found.")
        return
    await interaction.followup.send(embed=build_encounter_embed(data))


# Discord fails any slash command that isn't acknowledged within 3 seconds, and a lookup
# can chain up to three API calls. Each command defers first (users see "thinking..."),
# which allows up to 15 minutes, then replies with a followup message.

@bot.tree.command(name="trainer", description="Look up a trainer's team")
@app_commands.describe(name="Trainer name or location")
async def trainer(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    results = await fetch("/trainer", params={"name": name})

    if not results:
        results = await fetch("/location", params={"name": name})
        if not results:
            await interaction.followup.send(f"No trainer found for `{name}`.")
            return
        if len(results) == 1:
            await send_encounter(interaction, results[0]["encounter_id"])
        else:
            await interaction.followup.send(
                f"Found {len(results)} encounters for `{name}` — pick one:",
                view=EncounterView(results)
            )
        return

    if len(results) == 1:
        encounters = await fetch(f"/trainer/{results[0]['id']}/encounters")
        if not encounters:
            await interaction.followup.send(f"No encounters found for **{results[0]['name']}**.")
            return
        if len(encounters) == 1:
            await send_encounter(interaction, encounters[0]["id"])
        else:
            await interaction.followup.send(
                f"Multiple encounters for **{results[0]['name']}** — pick one:",
                view=EncounterView(encounters)
            )
    else:
        await interaction.followup.send(
            f"Found {len(results)} trainers matching `{name}` — pick one:",
            view=TrainerView(results)
        )

@bot.tree.command(name="route", description="Look up all trainers on a route or location")
@app_commands.describe(location="Route or location name")
async def route(interaction: discord.Interaction, location: str):
    await interaction.response.defer(thinking=True)
    results = await fetch("/location", params={"name": location})

    if not results:
        await interaction.followup.send(f"No trainers found at `{location}`.")
        return

    if len(results) == 1:
        await send_encounter(interaction, results[0]["encounter_id"])
    else:
        await interaction.followup.send(
            f"Found {len(results)} encounters at `{location}` — pick one:",
            view=EncounterView(results)
        )


@bot.tree.command(name="pokemon", description="Look up a Pokemon's stats")
@app_commands.describe(name="Pokemon name")
async def pokemon(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    results = await fetch(f"/pokemon/{quote(name.strip(), safe='')}")

    if not results:
        await interaction.followup.send(f"No Pokemon found for `{name}`.")
        return

    if len(results) == 1:
        await interaction.followup.send(embed=build_pokemon_embed(results[0]))
        return

    matches = "\n".join(f"- {p['name']}" for p in results[:10])
    await interaction.followup.send(
        f"Found multiple Pokemon matching `{name}`:\n{matches}\nTry a more specific name."
    )


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot ready as {bot.user}")


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

bot.run(BOT_TOKEN)
