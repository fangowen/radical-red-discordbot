import json
import re
from db.session import SessionLocal
from db.models import Trainer, TrainerEncounter, TrainerPokemon, TrainerPokemonMove, Pokemon

def parse_location_and_name(trainer_name):
    parts = trainer_name.strip().split(" ", 1)
    # format is "LOCATION NAME" e.g. "ROUTE 22 #1 RIVAL" or "GYM LEADER BROCK"
    # last word(s) after known prefixes = name, rest = location
    return trainer_name  # keep full string for now, can split later

def get_or_create_trainer(db, name, trainer_class):
    trainer = db.query(Trainer).filter_by(name=name, trainer_class=trainer_class).first()
    if not trainer:
        trainer = Trainer(name=name, trainer_class=trainer_class)
        db.add(trainer)
        db.flush()
    return trainer

def get_or_create_pokemon(db, name, stats):
    pokemon = db.query(Pokemon).filter_by(name=name).first()
    if not pokemon:
        pokemon = Pokemon(
            name=name,
            hp=stats.get("hp"),
            attack=stats.get("attack"),
            defense=stats.get("defense"),
            sp_attack=stats.get("sp_attack"),
            sp_defense=stats.get("sp_defense"),
            speed=stats.get("speed"),
        )
        db.add(pokemon)
        db.flush()
    return pokemon

def parse_level(level_str):
    if not level_str:
        return None
    if str(level_str).isdigit():
        return int(level_str)
    return None  # store "Highest Lv -1" etc as null for now

def seed():
    with open("data/parsed_encounters.json") as f:
        encounters = json.load(f)

    db = SessionLocal()
    try:
        encounter_number_tracker = {}

        for enc in encounters:
            raw_name = enc["trainer_name"]
            tab = enc["tab"]
            battle_effect = enc.get("battle_effect")
            starter_variant = enc.get("starter_variant")
            level_cap = enc.get("level_cap")

            # use tab as trainer_class
            trainer_class = tab.replace("_", " ").title()

            trainer = get_or_create_trainer(db, raw_name, trainer_class)

            # track encounter number per trainer
            key = (raw_name, starter_variant)
            encounter_number_tracker[key] = encounter_number_tracker.get(key, 0) + 1
            enc_number = encounter_number_tracker[key]

            encounter = TrainerEncounter(
                trainer_id=trainer.id,
                location=raw_name,
                encounter_number=enc_number,
                starter_variant=starter_variant,
                team_variant=None,
                level_cap=level_cap,
                battle_effect=battle_effect,
            )
            db.add(encounter)
            db.flush()

            for slot, mon in enumerate(enc["team"]):
                pokemon = get_or_create_pokemon(db, mon["pokemon"], mon["stats"])

                tp = TrainerPokemon(
                    encounter_id=encounter.id,
                    pokemon_id=pokemon.id,
                    level=str(mon.get("level")) if mon.get("level") else None,
                    nature=mon.get("nature"),
                    ability=mon.get("ability"),
                    item=mon.get("item"),
                    hp=mon["stats"].get("hp"),
                    attack=mon["stats"].get("attack"),
                    defense=mon["stats"].get("defense"),
                    sp_attack=mon["stats"].get("sp_attack"),
                    sp_defense=mon["stats"].get("sp_defense"),
                    speed=mon["stats"].get("speed"),
                    speed_at_level_cap=mon.get("speed_at_level_cap"),
                )
                db.add(tp)
                db.flush()

                for i, move in enumerate(mon.get("moves", []), start=1):
                    db.add(TrainerPokemonMove(
                        trainer_pokemon_id=tp.id,
                        move_name=move,
                        slot=i,
                    ))

        db.commit()
        print("Seeded successfully")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()