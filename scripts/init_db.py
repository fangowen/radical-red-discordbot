# run this once from the project root as a quick test
from db.base import Base
from db.models import Pokemon, Trainer, TrainerEncounter, TrainerPokemon, TrainerPokemonMove
from db.session import engine

Base.metadata.create_all(bind=engine)
print("tables created successfully")