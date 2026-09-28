from database import get_db

def add_wardrobe_item(session_id: str, category: str, photo_path: str, description: str = None):
    db = get_db()
    db.execute(
        "INSERT INTO wardrobe_items (session_id, category, photo_path, description) VALUES (?, ?, ?, ?)",
        (session_id, category, photo_path, description)
    )
    db.commit()
    db.close()

def get_wardrobe(session_id: str):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM wardrobe_items WHERE session_id = ? ORDER BY created_at DESC",
        (session_id,)
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]

def delete_wardrobe_item(item_id: int, session_id: str):
    db = get_db()
    item = db.execute("SELECT * FROM wardrobe_items WHERE id = ? AND session_id = ?", (item_id, session_id)).fetchone()
    if item:
        db.execute("DELETE FROM wardrobe_items WHERE id = ? AND session_id = ?", (item_id, session_id))
        db.commit()
        db.close()
        return item["photo_path"]
    db.close()
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
    db.close()


def get_profile(session_id: str):
    db = get_db()
    row = db.execute("SELECT * FROM user_profiles WHERE session_id = ?", (session_id,)).fetchone()
    db.close()
    return dict(row) if row else None

def save_profile(session_id: str, gender, age, styles: str, notes: str):
    db = get_db()
    db.execute(
        """INSERT INTO user_profiles (session_id, gender, age, styles, notes, updated_at)
           VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(session_id) DO UPDATE SET
               gender = excluded.gender,
               age = excluded.age,
               styles = excluded.styles,
               notes = excluded.notes,
               updated_at = CURRENT_TIMESTAMP""",
        (session_id, gender, age, styles, notes),
    )
    db.commit()
    db.close()
