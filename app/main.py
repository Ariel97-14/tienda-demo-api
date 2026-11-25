"""API de ventas para una tienda ficticia. Los importes se guardan en centavos."""

import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StringConstraints, model_validator


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Sku = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=30)]


class ProductInput(BaseModel):
    sku: Sku
    name: Name
    price_cents: int = Field(ge=0)
    stock: int = Field(ge=0)


class OrderItemInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class OrderInput(BaseModel):
    items: list[OrderItemInput] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_products(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Cada producto debe aparecer una sola vez por pedido")
        return self


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect(path)) as connection, connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
                stock INTEGER NOT NULL CHECK (stock >= 0)
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                total_cents INTEGER NOT NULL CHECK (total_cents >= 0)
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                product_id INTEGER NOT NULL REFERENCES products(id),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
                UNIQUE (order_id, product_id)
            );
        """)


def create_app(database_path: Path | str = "tienda.sqlite3") -> FastAPI:
    path = Path(database_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        _initialize(path)
        yield

    api = FastAPI(
        title="Tienda Demo API",
        description="Inventario y ventas de una tienda ficticia. Todos los datos de ejemplo son sintéticos.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @api.get("/health")
    def health():
        return {"status": "ok"}

    @api.post("/products", status_code=201)
    def add_product(product: ProductInput):
        try:
            with closing(_connect(path)) as connection, connection:
                cursor = connection.execute(
                    "INSERT INTO products (sku, name, price_cents, stock) VALUES (?, ?, ?, ?)",
                    (product.sku, product.name, product.price_cents, product.stock),
                )
                return {"id": cursor.lastrowid, **product.model_dump()}
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="El SKU ya existe") from error

    @api.get("/products")
    def list_products():
        with closing(_connect(path)) as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM products ORDER BY id")]

    @api.post("/orders", status_code=201)
    def add_order(order: OrderInput):
        with closing(_connect(path)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = {}
            for item in order.items:
                product = connection.execute(
                    "SELECT id, stock, price_cents FROM products WHERE id = ?", (item.product_id,)
                ).fetchone()
                if product is None:
                    raise HTTPException(status_code=404, detail=f"Producto {item.product_id} inexistente")
                if product["stock"] < item.quantity:
                    raise HTTPException(status_code=409, detail=f"Stock insuficiente para producto {item.product_id}")
                rows[item.product_id] = product

            total = sum(rows[item.product_id]["price_cents"] * item.quantity for item in order.items)
            cursor = connection.execute("INSERT INTO orders (total_cents) VALUES (?)", (total,))
            order_id = cursor.lastrowid
            details = []
            for item in order.items:
                price = rows[item.product_id]["price_cents"]
                connection.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item.quantity, item.product_id))
                connection.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents) VALUES (?, ?, ?, ?)",
                    (order_id, item.product_id, item.quantity, price),
                )
                details.append({"product_id": item.product_id, "quantity": item.quantity, "unit_price_cents": price})
            return {"id": order_id, "total_cents": total, "items": details}

    @api.get("/orders")
    def list_orders():
        with closing(_connect(path)) as connection:
            orders = [dict(row) for row in connection.execute("SELECT * FROM orders ORDER BY id")]
            for order in orders:
                order["items"] = [dict(row) for row in connection.execute(
                    "SELECT product_id, quantity, unit_price_cents FROM order_items WHERE order_id = ? ORDER BY id",
                    (order["id"],),
                )]
            return orders

    @api.get("/reports/summary")
    def summary():
        with closing(_connect(path)) as connection:
            row = connection.execute("""
                SELECT (SELECT count(*) FROM orders) AS orders,
                       COALESCE(sum(quantity), 0) AS units_sold,
                       COALESCE(sum(quantity * unit_price_cents), 0) AS revenue_cents
                FROM order_items
            """).fetchone()
            return dict(row)

    return api


app = create_app()

