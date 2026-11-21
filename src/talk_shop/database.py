"""SQLite storage for Talk Shop products."""

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class Product:
    name: str
    price: float
    stock: int


class ProductDatabase:
    def __init__(self, path: str | Path = "talk_shop.db") -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        if self.path.parent != Path("."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    name TEXT PRIMARY KEY COLLATE NOCASE,
                    price REAL NOT NULL CHECK (price >= 0),
                    stock INTEGER NOT NULL CHECK (stock >= 0)
                )
                """
            )

    def list_products(self) -> list[Product]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name, price, stock FROM products "
                "ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [Product(row["name"], row["price"], row["stock"]) for row in rows]

    def find_product(self, name: str) -> Product | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT name, price, stock FROM products WHERE name = ?",
                (name.strip(),),
            ).fetchone()
        if row is None:
            return None
        return Product(row["name"], row["price"], row["stock"])

    def add_product(self, name: str, price: float, stock: int) -> None:
        self._validate(name, price, stock)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                (name.strip(), price, stock),
            )

    def update_product(
        self, old_name: str, new_name: str, price: float, stock: int
    ) -> bool:
        self._validate(new_name, price, stock)
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE products SET name = ?, price = ?, stock = ? "
                "WHERE name = ?",
                (new_name.strip(), price, stock, old_name.strip()),
            )
        return cursor.rowcount > 0

    def delete_product(self, name: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM products WHERE name = ?", (name.strip(),)
            )
        return cursor.rowcount > 0

    def clear_products(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM products")

    @staticmethod
    def _validate(name: str, price: float, stock: int) -> None:
        if not name.strip():
            raise ValueError("Product name cannot be empty.")
        if price < 0:
            raise ValueError("Price cannot be negative.")
        if stock < 0:
            raise ValueError("Stock cannot be negative.")