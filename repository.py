from database import get_db

def add_wardrobe_item(session_id: str, category: str, photo_path: str, description: str = None):
    db = get_db()
    db.execute(
        "INSERT INTO wardrobe_items (session_id, category, photo_path, description) VALUES (?, ?, ?, ?)",
        (session_id, category, photo_path, description)
    )
    db.commit()

def get_wardrobe(session_id: str):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM wardrobe_items WHERE session_id = ? ORDER BY created_at DESC",
        (session_id,)
    ).fetchall()
    return [dict(row) for row in rows]

def delete_wardrobe_item(item_id: int, session_id: str):
    """Удаляет вещь из базы данных по id и проверяет принадлежность сессии."""
    db = get_db()
    item = db.execute("SELECT * FROM wardrobe_items WHERE id = ? AND session_id = ?", (item_id, session_id)).fetchone()
    if item:
        db.execute("DELETE FROM wardrobe_items WHERE id = ? AND session_id = ?", (item_id, session_id))
        db.commit()
        return item["photo_path"]
    return None

def save_outfit_history(session_id, occasion, city, temperature, weather_condition, item_ids, collage_path, explanation):
    db = get_db()
    db.execute(
        """INSERT INTO outfit_history 
           (session_id, occasion, city, temperature, weather_condition, item_ids, collage_path, explanation) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, occasion, city, temperature, weather_condition, ",".join(map(str, item_ids)) if item_ids else "", collage_path, explanation)
    )
    db.commit()
