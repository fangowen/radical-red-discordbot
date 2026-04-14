from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from db.base import Base

class Pokemon(Base):
    __tablename__ = "pokemon"

    id = Column(Integer, primary_key=True)
    dex_number = Column(Integer)
    name = Column(String, nullable=False)
    type1 = Column(String)
    type2 = Column(String)
    ability = Column(String)
    hidden_ability = Column(String)
    hp = Column(Integer)
    attack = Column(Integer)
    defense = Column(Integer)
    sp_attack = Column(Integer)
    sp_defense = Column(Integer)
    speed = Column(Integer)


class Trainer(Base):
    __tablename__ = "trainer"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    trainer_class = Column(String)
    starter = Column(String, nullable=True)
    encounters = relationship("TrainerEncounter", back_populates="trainer")


class TrainerEncounter(Base):
    __tablename__ = "trainer_encounter"

    id = Column(Integer, primary_key=True)
    trainer_id = Column(Integer, ForeignKey("trainer.id"))
    location = Column(String)
    encounter_number = Column(Integer)
    starter_variant = Column(String, nullable=True)
    team_variant = Column(Integer, nullable=True)
    trainer = relationship("Trainer", back_populates="encounters")
    team = relationship("TrainerPokemon", back_populates="encounter")
    level_cap = Column(Integer, nullable=True)
    battle_effect = Column(String, nullable=True)


class TrainerPokemon(Base):
    __tablename__ = "trainer_pokemon"

    id = Column(Integer, primary_key=True)
    encounter_id = Column(Integer, ForeignKey("trainer_encounter.id"))
    pokemon_id = Column(Integer, ForeignKey("pokemon.id"))
    pokemon = relationship("Pokemon", backref="trainer_pokemon")
    level = Column(String, nullable=True)    
    nature = Column(String)
    ability = Column(String)
    item = Column(String)
    hp = Column(Integer)
    attack = Column(Integer)
    defense = Column(Integer)
    sp_attack = Column(Integer)
    sp_defense = Column(Integer)
    speed = Column(Integer)
    speed_at_level_cap = Column(Integer, nullable=True)
    encounter = relationship("TrainerEncounter", back_populates="team")
    moves = relationship("TrainerPokemonMove", back_populates="trainer_pokemon")


class TrainerPokemonMove(Base):
    __tablename__ = "trainer_pokemon_move"

    id = Column(Integer, primary_key=True)
    trainer_pokemon_id = Column(Integer, ForeignKey("trainer_pokemon.id"))
    move_name = Column(String)
    slot = Column(Integer)
    trainer_pokemon = relationship("TrainerPokemon", back_populates="moves")