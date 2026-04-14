from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import joinedload
from db.session import SessionLocal
from db.models import Pokemon, Trainer, TrainerEncounter, TrainerPokemon, TrainerPokemonMove
from cache.redis import get_cache, set_cache
app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


#search trainers by name
@app.get("/trainer")
def search_trainers(name: str, db=Depends(get_db)):
    cache_key = f"trainer:search:{name.lower()}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    results = db.query(Trainer).filter(
        Trainer.name.ilike(f"%{name}%")
    ).all()

    if not results:
        raise HTTPException(status_code=404, detail="Trainer not found")

    data = [
        {
            "id": t.id,
            "name": t.name,
            "trainer_class": t.trainer_class,
            "encounter_count": len(t.encounters)
        }
        for t in results
    ]
    set_cache(cache_key, data)
    return data


@app.get("/trainer/{trainer_id}/encounters")
def get_encounters(trainer_id: int, db=Depends(get_db)):
    cache_key = f"trainer:encounters:{trainer_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    trainer = db.query(Trainer).filter_by(id=trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    data = [
        {
            "id": e.id,
            "location": e.location,
            "encounter_number": e.encounter_number,
            "starter_variant": e.starter_variant,
            "team_variant": e.team_variant,
            "level_cap": e.level_cap,
            "battle_effect": e.battle_effect,
        }
        for e in trainer.encounters
    ]
    set_cache(cache_key, data)
    return data


@app.get("/encounter/{encounter_id}")
def get_encounter(encounter_id: int, db=Depends(get_db)):
    cache_key = f"encounter:{encounter_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    encounter = db.query(TrainerEncounter).options(
        joinedload(TrainerEncounter.team).joinedload(TrainerPokemon.moves),
        joinedload(TrainerEncounter.team).joinedload(TrainerPokemon.pokemon),
    ).filter_by(id=encounter_id).first()

    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")

    data = {
        "id": encounter.id,
        "location": encounter.location,
        "level_cap": encounter.level_cap,
        "battle_effect": encounter.battle_effect,
        "starter_variant": encounter.starter_variant,
        "team": [
            {
                "pokemon": tp.pokemon.name,
                "level": tp.level,
                "nature": tp.nature,
                "ability": tp.ability,
                "item": tp.item,
                "stats": {
                    "hp": tp.hp,
                    "attack": tp.attack,
                    "defense": tp.defense,
                    "sp_attack": tp.sp_attack,
                    "sp_defense": tp.sp_defense,
                    "speed": tp.speed,
                },
                "speed_at_level_cap": tp.speed_at_level_cap,
                "moves": [m.move_name for m in sorted(tp.moves, key=lambda x: x.slot)]
            }
            for tp in encounter.team
        ]
    }
    set_cache(cache_key, data)
    return data


@app.get("/location")
def search_by_location(name: str, db=Depends(get_db)):
    cache_key = f"location:search:{name.lower()}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    results = db.query(TrainerEncounter).options(
        joinedload(TrainerEncounter.trainer)
    ).filter(
        TrainerEncounter.location.ilike(f"%{name}%")
    ).all()

    if not results:
        raise HTTPException(status_code=404, detail="No trainers found at that location")

    data = [
        {
            "encounter_id": e.id,
            "trainer_name": e.trainer.name,
            "trainer_class": e.trainer.trainer_class,
            "location": e.location,
            "starter_variant": e.starter_variant,
            "level_cap": e.level_cap,
            "battle_effect": e.battle_effect,
        }
        for e in results
    ]
    set_cache(cache_key, data)
    return data


@app.get("/pokemon/{name}")
def get_pokemon(name: str, db=Depends(get_db)):
    cache_key = f"pokemon:{name.lower()}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    pokemon = db.query(Pokemon).filter(
        Pokemon.name.ilike(f"%{name}%")
    ).all()

    if not pokemon:
        raise HTTPException(status_code=404, detail="Pokemon not found")

    data = [
        {
            "id": p.id,
            "name": p.name,
            "stats": {
                "hp": p.hp,
                "attack": p.attack,
                "defense": p.defense,
                "sp_attack": p.sp_attack,
                "sp_defense": p.sp_defense,
                "speed": p.speed,
            }
        }
        for p in pokemon
    ]
    set_cache(cache_key, data)
    return data