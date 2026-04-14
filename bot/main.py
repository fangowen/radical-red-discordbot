import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = "http://localhost:8000"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 404:
                return None
            return await response.json()

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
        encounter_id = self.values[0]
        data = await fetch(f"{API_URL}/encounter/{encounter_id}")
        if not data:
            await interaction.response.send_message("Encounter not found.", ephemeral=True)
            return
        embed = build_encounter_embed(data)
        await interaction.response.edit_message(content=None, embed=embed, view=None)

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
        trainer_id = self.values[0]
        encounters = await fetch(f"{API_URL}/trainer/{trainer_id}/encounters")

        if not encounters:
            await interaction.response.send_message("No encounters found.", ephemeral=True)
            return

        if len(encounters) == 1:
            data = await fetch(f"{API_URL}/encounter/{encounters[0]['id']}")
            embed = build_encounter_embed(data)
            await interaction.response.edit_message(content=None, embed=embed, view=None)
        else:
            view = EncounterView(encounters)
            await interaction.response.edit_message(
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
            f"**{mon['nature']} | {mon['ability']}**\n"
            f"Item: {mon['item'] or 'None'}\n"
            f"Moves: {moves}\n"
            f"HP:{stats['hp']} ATK:{stats['attack']} DEF:{stats['defense']} "
            f"SPA:{stats['sp_attack']} SPD:{stats['sp_defense']} SPE:{stats['speed']}"
            f"{speed_info}"
        )
        embed.add_field(
            name=f"{mon['pokemon']} (Lv {mon['level'] or '?'})",
            value=value,
            inline=False
        )

    return embed

@bot.tree.command(name="trainer", description="Look up a trainer's team")
@app_commands.describe(name="Trainer name or location")
async def trainer(interaction: discord.Interaction, name: str):
    results = await fetch(f"{API_URL}/trainer?name={name}")

    if not results:
        results = await fetch(f"{API_URL}/location?name={name}")
        if not results:
            await interaction.response.send_message(f"No trainer found for `{name}`.", ephemeral=True)
            return
        if len(results) == 1:
            data = await fetch(f"{API_URL}/encounter/{results[0]['encounter_id']}")
            embed = build_encounter_embed(data)
            await interaction.response.send_message(embed=embed)
        else:
            view = EncounterView(results)
            await interaction.response.send_message(
                f"Found {len(results)} encounters for `{name}` — pick one:",
                view=view
            )
        return

    if len(results) == 1:
        encounters = await fetch(f"{API_URL}/trainer/{results[0]['id']}/encounters")
        if len(encounters) == 1:
            data = await fetch(f"{API_URL}/encounter/{encounters[0]['id']}")
            embed = build_encounter_embed(data)
            await interaction.response.send_message(embed=embed)
        else:
            view = EncounterView(encounters)
            await interaction.response.send_message(
                f"Multiple encounters for **{results[0]['name']}** — pick one:",
                view=view
            )
    else:
        view = TrainerView(results)
        await interaction.response.send_message(
            f"Found {len(results)} trainers matching `{name}` — pick one:",
            view=view
        )

@bot.tree.command(name="route", description="Look up all trainers on a route or location")
@app_commands.describe(location="Route or location name")
async def route(interaction: discord.Interaction, location: str):
    results = await fetch(f"{API_URL}/location?name={location}")

    if not results:
        await interaction.response.send_message(f"No trainers found at `{location}`.", ephemeral=True)
        return

    if len(results) == 1:
        data = await fetch(f"{API_URL}/encounter/{results[0]['encounter_id']}")
        embed = build_encounter_embed(data)
        await interaction.response.send_message(embed=embed)
    else:
        view = EncounterView(results)
        await interaction.response.send_message(
            f"Found {len(results)} encounters at `{location}` — pick one:",
            view=view
        )

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot ready as {bot.user}")

bot.run(BOT_TOKEN)