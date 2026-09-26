from database import get_db


def add_wardrobe_item(
    session_id: str,
    category: str,
    photo_path: str,
    description: str | None = None,
) -> int:
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO wardrobe_items (session_id, category, description, photo_path) "
            "VALUES (?, ?, ?, ?)",
            (session_id, category, description, photo_path),
        )
        return cursor.lastrowid


def get_wardrobe(session_id: str) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM wardrobe_items WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def delete_wardrobe_item(session_id: str, item_id: int) -> None:
    with get_db() as db:
        db.execute(
            "DELETE FROM wardrobe_items WHERE id = ? AND session_id = ?",
            (item_id, session_id),
        )


def save_outfit_history(
    session_id: str,
    occasion: str,
    city: str | None,
    temperature: float | None,
    weather_condition: str | None,
    item_ids: list[int],
    collage_path: str | None,
    explanation: str | None,
) -> int:
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO outfit_history "
            "(session_id, occasion, city, temperature, weather_condition, item_ids, collage_path, explanation) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                occasion,
                city,
                temperature,
                weather_condition,
                ",".join(str(i) for i in item_ids),
                collage_path,
                explanation,
            ),
        )
        return cursor.lastrowid
