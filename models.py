# app/models.py
import datetime as dt
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class OrderStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    PICKED_UP = "picked_up"
    CANCELLED = "cancelled"
    NOT_HONORED = "not_honored"

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

# ---------------------------------------------------------------------------
# Tables d'association (clés primaires composées)
# ---------------------------------------------------------------------------

class MenuProduct(SQLModel, table=True):
    __tablename__ = "menu_products"

    menu_id: int = Field(foreign_key="menus.id", primary_key=True)
    product_id: int = Field(foreign_key="products.id", primary_key=True)


class OrderProduct(SQLModel, table=True):
    __tablename__ = "order_products"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_products_quantity"),)

    order_id: int = Field(foreign_key="orders.id", primary_key=True)
    product_id: int = Field(foreign_key="products.id", primary_key=True)
    quantity: int
    unit_price: Decimal = Field(max_digits=8, decimal_places=2)

    order: "Order" = Relationship(back_populates="product_lines")
    product: "Product" = Relationship(back_populates="order_lines")


class OrderMenu(SQLModel, table=True):
    __tablename__ = "order_menus"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_menus_quantity"),)

    order_id: int = Field(foreign_key="orders.id", primary_key=True)
    menu_id: int = Field(foreign_key="menus.id", primary_key=True)
    quantity: int
    unit_price: Decimal = Field(max_digits=8, decimal_places=2)

    order: "Order" = Relationship(back_populates="menu_lines")
    menu: "Menu" = Relationship(back_populates="order_lines")


# ---------------------------------------------------------------------------
# Tables principales
# ---------------------------------------------------------------------------

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    role: UserRole = Field(default=UserRole.USER)
    is_blocked: bool = Field(default=False)
    must_change_password: bool = Field(default=True)
    created_at: dt.datetime = Field(default_factory=utcnow)

    orders: list["Order"] = Relationship(back_populates="user")


class Product(SQLModel, table=True):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price"),
        CheckConstraint("quantity >= 0", name="ck_products_quantity"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    description: str | None = Field(default=None)
    price: Decimal = Field(max_digits=8, decimal_places=2)
    quantity: int = Field(default=0)
    is_available: bool = Field(default=True)
    is_deleted: bool = Field(default=False)

    menus: list["Menu"] = Relationship(back_populates="products", link_model=MenuProduct)
    order_lines: list[OrderProduct] = Relationship(back_populates="product")


class Menu(SQLModel, table=True):
    __tablename__ = "menus"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_menus_price"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    description: str | None = Field(default=None)
    price: Decimal = Field(max_digits=8, decimal_places=2)
    is_available: bool = Field(default=True)
    start_date: dt.date | None = Field(default=None)
    end_date: dt.date | None = Field(default=None)
    is_deleted: bool = Field(default=False)

    products: list[Product] = Relationship(back_populates="menus", link_model=MenuProduct)
    order_lines: list[OrderMenu] = Relationship(back_populates="menu")


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    ordered_at: dt.datetime = Field(default_factory=utcnow)
    pickup_at: dt.datetime = Field(index=True)
    status: OrderStatus = Field(default=OrderStatus.PENDING)

    user: User = Relationship(back_populates="orders")
    product_lines: list[OrderProduct] = Relationship(back_populates="order")
    menu_lines: list[OrderMenu] = Relationship(back_populates="order")


class ClosedDay(SQLModel, table=True):
    __tablename__ = "closed_days"

    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(unique=True, index=True)
    reason: str | None = Field(default=None, max_length=255)