import csv
import json
import re
import urllib.request

SHEET_ID = "1jDbKFA30xo8csPHZNLtsmqs781bW_Xb9mKoPYyE6KK8"

TABS = {
    "kanto_leaders": "1410111071",
    "kanto_rematch": "2075653688",
    "johto_leaders": "2145471124",
    "rivals": "1150799580",
    "team_rocket": "1998272076",
    "mini_bosses": "739017967",
    "optional_bosses": "1411568458",
    "indigo_league": "2140479091",
    "postgame": "1752505021",
}

POKEMON_COLS = [4, 9, 14, 19, 24, 29]  # col E, J, O, T, Y, AD (0-indexed)

def fetch_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        return list(csv.reader(line.decode("utf-8") for line in r))

def clean(val):
    return val.strip().replace("\n", " ") if val else None

def parse_level(val):
    val = clean(val)
    if not val:
        return None
    # extract offset like "Highest Lv -2" -> store as string, or numeric
    return val

def parse_trainer_block(rows, start_row, starter_variant, battle_effect, tab_name):
    """Parse one trainer block starting at the trainer name row."""
    r = start_row
    row = rows[r]

    # trainer name is col 2 (C)
    trainer_raw = clean(row[2]) if len(row) > 2 else None
    if not trainer_raw:
        return None

    # split "ROUTE 22 #1\nRIVAL" -> location and name
    parts = trainer_raw.split(" ")
    # last word is usually the name/class
    trainer_name = trainer_raw  # keep full for now, can split later

    # level cap from col 1 (B) in the speed stat row (r + 22 approx)
    level_cap = None
    team = []

    # pokemon names row = start_row
    # level row = start_row + 1
    # nature row = start_row + 4
    # ability row = start_row + 5
    # item row = start_row + 6
    # moves rows = start_row + 7 to +10
    # stats start = start_row + 13 (HP row)

    def get_cell(row_offset, col):
        target = r + row_offset
        if target >= len(rows):
            return None
        row_data = rows[target]
        return clean(row_data[col]) if col < len(row_data) else None

    # find level cap — scan next 25 rows for "IF YOU'RE" in col 1
    for offset in range(5, 28):
        b_cell = get_cell(offset, 2)
        if b_cell and "LEVEL" in b_cell.upper() and "->>" in b_cell:
            match = re.search(r"LEVEL\s+(\d+)", b_cell.upper())
            if match:
                level_cap = int(match.group(1))
            break

    for col in POKEMON_COLS:
        name = get_cell(0, col)
        if not name or name.upper() in ("BASE STATS", ""):
            continue

        level = get_cell(1, col)
        nature = get_cell(4, col)
        ability = get_cell(5, col)
        item = get_cell(6, col)

        moves = []
        for move_offset in range(7, 11):
            move = get_cell(move_offset, col)
            if move and move != "-":
                moves.append(move)

        # stats at offsets 13-18 (HP ATK DEF SPA SPD SPE)
        # format: "HP" in col, value in col+1
        def stat(offset):
            val = get_cell(offset, col + 1)
            try:
                return int(val) if val else None
            except ValueError:
                return None

        hp  = stat(13)
        atk = stat(14)
        dfn = stat(15)
        spa = stat(16)
        spd = stat(17)
        spe = stat(18)

        # speed stat at level cap (offset 19, col+2 has the value)
        speed_at_cap = None
        for offset in range(15, 25):
            sc_data = rows[r + offset] if r + offset < len(rows) else []
            for check_col in range(col, col + 4):
                cell_val = clean(sc_data[check_col]) if check_col < len(sc_data) else None
                if cell_val and "SPEED STAT" in cell_val.upper():
                    # value is always 3 cols to the right of "SPEED STAT:" label
                    val_col = check_col + 3
                    raw = clean(sc_data[val_col]) if val_col < len(sc_data) else None
                    try:
                        speed_at_cap = int(raw)
                    except (ValueError, TypeError):
                        pass
                    break

        team.append({
            "pokemon": name,
            "level": level,
            "nature": nature,
            "ability": ability,
            "item": item,
            "moves": moves,
            "stats": {
                "hp": hp, "attack": atk, "defense": dfn,
                "sp_attack": spa, "sp_defense": spd, "speed": spe
            },
            "speed_at_level_cap": speed_at_cap
        })

    if not team:
        return None

    return {
        "trainer_name": trainer_name,
        "tab": tab_name,
        "battle_effect": battle_effect,
        "starter_variant": starter_variant,
        "level_cap": level_cap,
        "team": team
    }

def parse_tab(rows, tab_name):
    encounters = []
    current_battle_effect = None
    current_starter_variant = None
    i = 0

    while i < len(rows):
        row = rows[i]
        col4 = clean(row[4]) if len(row) > 4 else None
        col2 = clean(row[2]) if len(row) > 2 else None

        # detect battle effect
        if col4 and "BATTLE EFFECT" in col4.upper():
            current_battle_effect = col4
            i += 1
            continue

        # detect starter variant hint
        if col4 and "IF RIVAL HAS" in col4.upper():
            match = re.search(r"IF RIVAL HAS (\w+)", col4.upper())
            current_starter_variant = match.group(1).lower() if match else None
            i += 1
            continue

        # detect trainer block — col2 has trainer name and col4 has first pokemon
        if col2 and col4 and col4.upper() not in ("BASE STATS", "BATTLE EFFECT") and "IF YOU'RE" not in col4.upper():
            # check that next row has level info
            next_row = rows[i + 1] if i + 1 < len(rows) else []
            next_col4 = clean(next_row[4]) if len(next_row) > 4 else ""
            if next_col4 and ("LV" in next_col4.upper() or next_col4.isdigit() or "PLAYER" in next_col4.upper()):
                block = parse_trainer_block(rows, i, current_starter_variant, current_battle_effect, tab_name)
                if block:
                    encounters.append(block)
                    current_starter_variant = None
                i += 1
                continue

        i += 1

    return encounters

def main():
    all_encounters = []

    for tab_name, gid in TABS.items():
        print(f"Fetching {tab_name}...")
        try:
            rows = fetch_csv(gid)
            encounters = parse_tab(rows, tab_name)
            print(f"  Found {len(encounters)} encounters")
            all_encounters.extend(encounters)
        except Exception as e:
            print(f"  Error: {e}")

    with open("data/parsed_encounters.json", "w") as f:
        json.dump(all_encounters, f, indent=2)

    print(f"\nDone. Total encounters: {len(all_encounters)}")
    print("Output: data/parsed_encounters.json")

if __name__ == "__main__":
    main()