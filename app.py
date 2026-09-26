import os
import uuid

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from config import config
from database import init_db
from repository import add_wardrobe_item, get_wardrobe, save_outfit_history
from services.collage import build_collage
from services.outfit_logic import build_outfit
from services.weather import geocode_city, get_weather

app = Flask(__name__)
app.secret_key = config.secret_key

CATEGORY_LABELS = {
    "outerwear": "Верхняя одежда",
    "top": "Верх (футболка/рубашка/свитер)",
    "bottom": "Низ (брюки/юбка)",
    "dress": "Платье/комбинезон",
    "shoes": "Обувь",
    "accessory": "Аксессуар",
}


def get_session_id() -> str:
    """Каждому браузеру — свой session_id в cookie, чтобы разделять гардеробы."""
    if "session_id" not in session:
        session["session_id"] = uuid.uuid4().hex
    return session["session_id"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/wardrobe")
def wardrobe():
    items = get_wardrobe(get_session_id())
    return render_template("wardrobe.html", items=items, category_labels=CATEGORY_LABELS)


@app.route("/wardrobe/add", methods=["GET", "POST"])
def add_item():
    if request.method == "POST":
        photo = request.files.get("photo")
        category = request.form.get("category")
        description = request.form.get("description", "").strip() or None

        if not photo or not category:
            return render_template(
                "add_item.html", category_labels=CATEGORY_LABELS, error="Нужно выбрать фото и категорию"
            )

        os.makedirs(config.upload_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}_{secure_filename(photo.filename)}"
        photo_path = os.path.join(config.upload_dir, filename)
        photo.save(photo_path)

        add_wardrobe_item(get_session_id(), category, photo_path, description)
        return redirect(url_for("wardrobe"))

    return render_template("add_item.html", category_labels=CATEGORY_LABELS)


@app.route("/outfit", methods=["GET", "POST"])
def outfit_form():
    if request.method == "POST":
        occasion = request.form.get("occasion", "").strip()
        lat = request.form.get("lat")
        lon = request.form.get("lon")
        city_name = request.form.get("city", "").strip()

        if not occasion:
            return render_template("outfit_form.html", error="Укажи повод")

        if lat and lon:
            weather = get_weather(float(lat), float(lon))
        elif city_name:
            geo = geocode_city(city_name)
            if geo is None:
                return render_template("outfit_form.html", error="Город не найден, попробуй ещё раз")
            glat, glon, full_name = geo
            weather = get_weather(glat, glon, city=full_name)
        else:
            return render_template("outfit_form.html", error="Укажи город или разреши геолокацию")

        session_id = get_session_id()
        wardrobe_items = get_wardrobe(session_id)
        result = build_outfit(occasion, weather, wardrobe_items)

        collage_url = None
        if result.item_ids:
            selected = [i for i in wardrobe_items if i["id"] in result.item_ids]
            photo_paths = [i["photo_path"] for i in selected]
            collage_path = build_collage(photo_paths)
            if collage_path:
                collage_url = "/" + collage_path.replace(os.sep, "/")

        save_outfit_history(
            session_id=session_id,
            occasion=occasion,
            city=weather.city,
            temperature=weather.temperature,
            weather_condition=weather.condition_text,
            item_ids=result.item_ids,
            collage_path=collage_path if result.item_ids else None,
            explanation=result.explanation,
        )

        return render_template(
            "outfit_result.html",
            weather=weather,
            occasion=occasion,
            explanation=result.explanation,
            collage_url=collage_url,
            recommendations=result.generic_recommendations,
        )

    return render_template("outfit_form.html")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
