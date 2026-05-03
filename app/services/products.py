from __future__ import annotations

from dataclasses import dataclass

from app import db
from app.config import settings


@dataclass(slots=True)
class Product:
    id: int
    code: str
    title: str
    description: str
    price_rub: int
    price_stars: int
    stock: int
    enabled: bool
    photo: str | None
    position: int

    @property
    def stars(self) -> int:
        # Use explicit stars price when admin set it; otherwise convert from RUB.
        return self.price_stars if self.price_stars > 0 else settings.stars_for_rub(self.price_rub)


def _row_to_product(row) -> Product:
    return Product(
        id=int(row["id"]),
        code=str(row["code"]),
        title=str(row["title"]),
        description=str(row["description"] or ""),
        price_rub=int(row["price_rub"]),
        price_stars=int(row["price_stars"] or 0),
        stock=int(row["stock"]),
        enabled=bool(row["enabled"]),
        photo=(row["photo"] if row["photo"] else None),
        position=int(row["position"]),
    )


async def list_active() -> list[Product]:
    rows = await db.fetchall(
        """
        SELECT * FROM products
        WHERE enabled = 1
        ORDER BY position ASC, id ASC;
        """
    )
    return [_row_to_product(r) for r in rows]


async def list_all() -> list[Product]:
    rows = await db.fetchall("SELECT * FROM products ORDER BY position ASC, id ASC;")
    return [_row_to_product(r) for r in rows]


async def get(product_id: int) -> Product | None:
    row = await db.fetchone("SELECT * FROM products WHERE id = ?;", (product_id,))
    return _row_to_product(row) if row else None


async def create(
    *,
    code: str,
    title: str,
    description: str,
    price_rub: int,
    stock: int,
    price_stars: int = 0,
    photo: str | None = None,
    position: int = 0,
    enabled: bool = True,
) -> int:
    return await db.execute(
        """
        INSERT INTO products (code, title, description, price_rub, price_stars, stock, photo, position, enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (code, title, description, price_rub, price_stars, stock, photo, position, 1 if enabled else 0),
    )


async def update_field(product_id: int, field: str, value) -> None:
    # Whitelist of editable columns — never accept untrusted column names.
    allowed = {"title", "description", "price_rub", "price_stars", "stock", "photo", "position", "enabled"}
    if field not in allowed:
        raise ValueError(f"forbidden field: {field}")
    query = f"UPDATE products SET {field} = ? WHERE id = ?;"
    await db.execute(query, (value, product_id))


async def toggle(product_id: int) -> bool:
    row = await db.fetchone("SELECT enabled FROM products WHERE id = ?;", (product_id,))
    if not row:
        return False
    new_val = 0 if int(row["enabled"]) == 1 else 1
    await db.execute("UPDATE products SET enabled = ? WHERE id = ?;", (new_val, product_id))
    return bool(new_val)


async def delete(product_id: int) -> None:
    await db.execute("DELETE FROM products WHERE id = ?;", (product_id,))


async def decrement_stock(product_id: int) -> bool:
    """Atomic stock decrement: returns True if a unit was reserved."""
    async with db.connect() as conn:
        cur = await conn.execute(
            "UPDATE products SET stock = stock - 1 WHERE id = ? AND stock > 0;",
            (product_id,),
        )
        await conn.commit()
        return cur.rowcount > 0
