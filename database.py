# app/database.py
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.db import models  # noqa: F401  (charge les classes pour que SQLModel connaisse les tables)
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_URL = f"sqlite:///{ROOT_DIR / 'poleat.db'}"

# check_same_thread=False : FastAPI peut utiliser la base depuis plusieurs threads
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite n'applique pas les clés étrangères par défaut : on les active."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_and_tables() -> None:
    """Crée le fichier poleat.db et toutes les tables si elles n'existent pas déjà."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dépendance FastAPI : ouvre une session par requête, la ferme à la fin."""
    with Session(engine) as session:
        yield session