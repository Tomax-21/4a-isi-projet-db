"""
seed_data.py  (enregistré en .txt -> renomme-le en seed_data.py pour l'exécuter)

Génère un grand volume de données cohérentes pour remplir la base :
users, products, menus, menu_products, orders, order_products, order_menus, closed_days.

Usage :
    python seed_data.py                      # volumes par défaut
    python seed_data.py --users 5000 --orders 100000
    python seed_data.py --reset              # vide les tables avant d'insérer

Prérequis : pip install sqlmodel   (passlib[bcrypt] optionnel pour de vrais hash)

>>> ADAPTE les 2 lignes d'import "from app.models ..." et DATABASE_URL ci-dessous.
"""
import argparse
import datetime as dt
import hashlib
import random
from decimal import Decimal
import bcrypt

from sqlmodel import Session, SQLModel, create_engine, delete

# === À ADAPTER : chemin de tes modèles =====================================
from models import (  # noqa: E402
    ClosedDay, Menu, MenuProduct, Order, OrderMenu, OrderProduct, OrderStatus,
    Product, User, UserRole, utcnow,
)

DATABASE_URL = "sqlite:///./poleat.db"   # ex: "postgresql+psycopg://user:pwd@localhost/db"

# === Volumes par défaut ====================================================
DEFAULTS = dict(
    users=1000,
    products=200,
    menus=40,
    orders=20000,
    closed_days=30,
)
BATCH = 2000          # taille des lots d'insertion
DEFAULT_PASSWORD = "Password123!"   # mot de passe de tous les faux comptes

# === Jeux de données =======================================================
FIRST_NAMES = ["lucas", "emma", "hugo", "lea", "louis", "chloe", "nathan", "manon", "jules",
               "camille", "arthur", "ines", "tom", "sarah", "theo", "zoe", "adam", "lola",
               "paul", "julie", "maxime", "clara", "antoine", "eva", "enzo", "alice"]
LAST_NAMES = ["martin", "bernard", "dubois", "thomas", "robert", "richard", "petit", "durand",
              "leroy", "moreau", "simon", "laurent", "lefebvre", "michel", "garcia", "david",
              "bertrand", "roux", "vincent", "fournier", "morel", "girard", "andre", "mercier"]

BASES = ["Sandwich", "Panini", "Wrap", "Salade", "Burger", "Pizza", "Quiche", "Croque-monsieur",
         "Baguette", "Bagel", "Soupe", "Pâtes", "Riz", "Gratin", "Tarte"]
GARNISHES = ["poulet", "jambon-fromage", "thon", "végétarien", "saumon", "dinde", "chèvre-miel",
             "bacon", "crudités", "boeuf", "mozzarella", "champignons", "falafel", "kebab"]
DRINKS = ["Coca-Cola", "Orangina", "Eau plate", "Eau gazeuse", "Ice Tea", "Jus d'orange",
          "Jus de pomme", "Café", "Thé", "Limonade", "Lait chocolaté"]
DESSERTS = ["Cookie", "Brownie", "Muffin", "Éclair", "Tarte aux pommes", "Yaourt", "Salade de fruits",
            "Mousse au chocolat", "Cheesecake", "Donut", "Compote", "Fondant"]
MENU_THEMES = ["Étudiant", "Express", "Gourmand", "Léger", "Midi", "Végé", "Classique",
               "Festif", "Du jour", "Famille", "Sportif", "Automne", "Hiver", "Printemps", "Été"]
CLOSED_REASONS = ["Jour férié", "Vacances scolaires", "Inventaire", "Travaux", "Fermeture exceptionnelle",
                  "Pont", "Formation du personnel", None]


# === Utilitaires ===========================================================
def hash_password(password):
    password_bytes = password.encode()
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode()

def money(low: float, high: float) -> Decimal:
    return Decimal(str(round(random.uniform(low, high), 2))).quantize(Decimal("0.01"))


def random_pickup(now: dt.datetime, past_ratio: float = 0.8) -> dt.datetime:
    """Heure de retrait entre 11h30 et 14h00 (créneaux de 15 min), surtout dans le passé."""
    if random.random() < past_ratio:
        day_offset = -random.randint(1, 365)
    else:
        day_offset = random.randint(0, 14)
    slot = random.choice([(11, 30), (11, 45), (12, 0), (12, 15), (12, 30), (12, 45), (13, 0), (13, 15), (13, 30), (13, 45)])
    d = now + dt.timedelta(days=day_offset)
    return d.replace(hour=slot[0], minute=slot[1], second=0, microsecond=0)


def pick_status(pickup_at: dt.datetime, now: dt.datetime) -> OrderStatus:
    if pickup_at < now:   # commande passée
        return random.choices(
            [OrderStatus.PICKED_UP, OrderStatus.NOT_HONORED, OrderStatus.CANCELLED],
            weights=[85, 8, 7],
        )[0]
    return random.choices(   # commande à venir
        [OrderStatus.PENDING, OrderStatus.READY, OrderStatus.CANCELLED],
        weights=[75, 15, 10],
    )[0]


def batched(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


# === Générateurs ===========================================================
def gen_users(session: Session, n: int) -> list[int]:
    pwd_hash = hash_password(DEFAULT_PASSWORD)
    users = [User(username="admin", password_hash=pwd_hash, role=UserRole.ADMIN,
                  must_change_password=False)]
    seen = {"admin"}
    while len(users) < n:
        username = f"{random.choice(FIRST_NAMES)}.{random.choice(LAST_NAMES)}{random.randint(1, 9999)}"[:50]
        if username in seen:
            continue
        seen.add(username)
        users.append(User(
            username=username,
            password_hash=pwd_hash,
            role=UserRole.USER,
            is_blocked=random.random() < 0.02,
            must_change_password=random.random() < 0.1,
            created_at=utcnow() - dt.timedelta(days=random.randint(0, 700)),
        ))
    for chunk in batched(users, BATCH):
        session.add_all(chunk)
        session.flush()
    session.commit()
    return [u.id for u in users if not u.is_blocked and u.role == UserRole.USER]


def gen_products(session: Session, n: int) -> dict[int, Decimal]:
    products, seen = [], set()
    # 1) produits "plats", 2) boissons, 3) desserts
    pools = (
        [(f"{b} {g}", (3.5, 9.0)) for b in BASES for g in GARNISHES],
        [(d, (1.0, 3.0)) for d in DRINKS],
        [(d, (1.5, 4.0)) for d in DESSERTS],
    )
    weights = [0.6, 0.2, 0.2]
    while len(products) < n:
        pool = random.choices(pools, weights=weights)[0]
        name, (lo, hi) = random.choice(pool)
        if name in seen:
            name = f"{name} {random.randint(2, 99)}"
            if name in seen:
                continue
        seen.add(name)
        deleted = random.random() < 0.03
        products.append(Product(
            name=name[:100],
            description=f"{name} préparé frais chaque jour." if random.random() < 0.7 else None,
            price=money(lo, hi),
            quantity=random.randint(0, 150),
            is_available=(not deleted) and random.random() < 0.92,
            is_deleted=deleted,
        ))
    session.add_all(products)
    session.flush()
    session.commit()
    return {p.id: p.price for p in products if p.is_available and not p.is_deleted}


def gen_menus(session: Session, n: int, all_product_ids: list[int]) -> dict[int, Decimal]:
    menus = []
    today = utcnow().date()
    for i in range(n):
        has_dates = random.random() < 0.4
        start = today - dt.timedelta(days=random.randint(0, 60)) if has_dates else None
        end = start + dt.timedelta(days=random.randint(7, 120)) if start else None
        deleted = random.random() < 0.05
        menus.append(Menu(
            name=f"Menu {random.choice(MENU_THEMES)} #{i + 1}"[:100],
            description="Plat + boisson + dessert" if random.random() < 0.7 else None,
            price=money(6.0, 14.0),
            is_available=(not deleted) and random.random() < 0.9,
            start_date=start,
            end_date=end,
            is_deleted=deleted,
        ))
    session.add_all(menus)
    session.flush()

    links = []
    for m in menus:
        for pid in random.sample(all_product_ids, k=min(random.randint(2, 5), len(all_product_ids))):
            links.append(MenuProduct(menu_id=m.id, product_id=pid))
    for chunk in batched(links, BATCH):
        session.add_all(chunk)
        session.flush()
    session.commit()
    return {m.id: m.price for m in menus if m.is_available and not m.is_deleted}


def gen_closed_days(session: Session, n: int) -> None:
    today = utcnow().date()
    candidates = [today + dt.timedelta(days=d) for d in range(-365, 366)]
    candidates = [d for d in candidates if d.weekday() < 5]   # jours ouvrés uniquement
    for d in random.sample(candidates, k=min(n, len(candidates))):
        session.add(ClosedDay(date=d, reason=random.choice(CLOSED_REASONS)))
    session.commit()


def gen_orders(session: Session, n: int, user_ids: list[int],
               product_prices: dict[int, Decimal], menu_prices: dict[int, Decimal]) -> None:
    now = utcnow()
    prod_ids, menu_ids = list(product_prices), list(menu_prices)

    for start in range(0, n, BATCH):
        count = min(BATCH, n - start)
        orders = []
        for _ in range(count):
            pickup = random_pickup(now)
            orders.append(Order(
                user_id=random.choice(user_ids),
                ordered_at=pickup - dt.timedelta(hours=random.randint(1, 72), minutes=random.randint(0, 59)),
                pickup_at=pickup,
                status=pick_status(pickup, now),
            ))
        session.add_all(orders)
        session.flush()   # récupère les ids

        lines = []
        for o in orders:
            # Au moins 1 ligne (produit ou menu) par commande
            nb_prod = random.randint(0, 3) if menu_ids else random.randint(1, 3)
            nb_menu = random.randint(0, 2) if menu_ids else 0
            if nb_prod == 0 and nb_menu == 0:
                nb_prod = 1
            for pid in random.sample(prod_ids, k=min(nb_prod, len(prod_ids))):
                lines.append(OrderProduct(order_id=o.id, product_id=pid,
                                          quantity=random.choices([1, 2, 3, 4], weights=[70, 20, 7, 3])[0],
                                          unit_price=product_prices[pid]))
            for mid in random.sample(menu_ids, k=min(nb_menu, len(menu_ids))):
                lines.append(OrderMenu(order_id=o.id, menu_id=mid,
                                       quantity=random.choices([1, 2, 3], weights=[80, 15, 5])[0],
                                       unit_price=menu_prices[mid]))
        session.add_all(lines)
        session.commit()
        print(f"  commandes : {start + count}/{n}")


# === Main ==================================================================
def main() -> None:
    ap = argparse.ArgumentParser(description="Remplit la DB avec des données de test.")
    for key, val in DEFAULTS.items():
        ap.add_argument(f"--{key.replace('_', '-')}", type=int, default=val)
    ap.add_argument("--seed", type=int, default=None, help="graine aléatoire (reproductibilité)")
    ap.add_argument("--reset", action="store_true", help="vide les tables avant insertion")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    engine = create_engine(DATABASE_URL, echo=False)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        if args.reset:
            print("Reset des tables...")
            for model in (OrderMenu, OrderProduct, Order, MenuProduct, Menu, Product, ClosedDay, User):
                session.exec(delete(model))
            session.commit()

        print("Users...")
        user_ids = gen_users(session, args.users)
        print("Products...")
        product_prices = gen_products(session, args.products)
        print("Menus...")
        menu_prices = gen_menus(session, args.menus, list(product_prices))
        print("Closed days...")
        gen_closed_days(session, args.closed_days)
        print("Orders...")
        gen_orders(session, args.orders, user_ids, product_prices, menu_prices)

    print(f"Terminé. Compte admin : admin / {DEFAULT_PASSWORD}")


if __name__ == "__main__":
    main()