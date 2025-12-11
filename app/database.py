from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite file
DB_FILE = "fiindo_challenge.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# Session maker
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base-Klasse für Models
Base = declarative_base()


def init_db():
    with engine.connect() as conn:
        print("DB-Verbindung erfolgreich:", conn)
