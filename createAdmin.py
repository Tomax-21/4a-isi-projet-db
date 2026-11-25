"""Usage : python createAdmin.py <username> <password>"""
import argparse

from passlib.hash import bcrypt
from sqlmodel import Session, create_engine

from app.models import User, UserRole   # à adapter

DATABASE_URL = "sqlite:///./db/poleat.db"   # à adapter

parser = argparse.ArgumentParser(description="Créer un administrateur.")
parser.add_argument("username")
parser.add_argument("password")
args = parser.parse_args()

with Session(create_engine(DATABASE_URL)) as session:
    session.add(User(
        username=args.username,
        password_hash=bcrypt.hash(args.password),
        role=UserRole.ADMIN,
        must_change_password=False,
    ))
    session.commit()

print(f"Administrateur « {args.username} » créé.")