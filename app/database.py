from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# SQLite file
DB_FILE = "fiindo_challenge.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Engine & session
engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(bind=engine)

# Initialize DB (conn test only)
def init_db():
    with engine.connect() as conn:
        print("Verbindung zur DB erfolgreich:", conn)
