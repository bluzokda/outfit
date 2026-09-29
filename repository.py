from config import config
from supabase import create_client, Client

# Инициализация клиента Supabase
supabase: Client = create_client(config.supabase_url, config.supabase_key)


def add_wardrobe_item(session_id: str, category: str, photo_path: str, description: str = None):
    data = {
        "user_id": session_id,
        "category": category,
        "photo_path": photo_path,
        "description": description
    }
    supabase.table("wardrobe_items").insert(data).execute()


def get_wardrobe(session_id: str):
    res = supabase.table("wardrobe_items")\
        .select("*")\
        .eq("user_id", session_id)\
        .order("created_at", desc=True)\
        .execute()
    return res.data or []


def delete_wardrobe_item(item_id: str, session_id: str):
    res = supabase.table("wardrobe_items")\
        .select("photo_path")\
        .eq("id", item_id)\
        .eq("user_id", session_id)\
        .execute()
    
    if res.data:
        photo_path = res.data[0]["photo_path"]
        supabase.table("wardrobe_items")\
            .delete()\
            .eq("id", item_id)\
            .eq("user_id", session_id)\
            .execute()
        return photo_path
    return None


def save_outfit_history(session_id, occasion, city, temperature, weather_condition, item_ids, collage_path, explanation):
    data = {
        "user_id": session_id,
        "occasion": occasion,
        "city": city,
        "weather": {
            "temperature": temperature,
            "condition": weather_condition
        },
        "explanation": explanation,
        "slots": {"item_ids": item_ids, "collage_path": collage_path}
    }
    supabase.table("outfits").insert(data).execute()


def get_profile(session_id: str):
    res = supabase.table("profiles")\
        .select("*")\
        .eq("id", session_id)\
        .execute()
    if res.data:
        row = res.data[0]
        if isinstance(row.get("styles"), list):
            row["styles"] = ",".join(row["styles"])
        return row
    return None


def save_profile(session_id: str, gender, age, styles: str, notes: str):
    styles_list = [s.strip() for s in styles.split(",") if s.strip()] if styles else []
    data = {
        "id": session_id,
        "gender": gender,
        "age": age,
        "styles": styles_list,
        "notes": notes
    }
    supabase.table("profiles").upsert(data).execute()
