import os
import uuid
import traceback
import urllib.parse
from datetime import timedelta

import requests
from flask import Flask, redirect, render_template, request, session, url_for, jsonify
from werkzeug.utils import secure_filename

from config import config
from database import init_db
from repository import (
    add_wardrobe_item,
    delete_wardrobe_item,
    get_profile,
    get_wardrobe,
    save_outfit_history,
    save_profile,
)
from services.collage import build_collage
from services.outfit_logic import build_outfit
from services.weather import geocode_city, get_weather

app = Flask(__name__)
app.secret_key = config.secret_key
app.permanent_session_lifetime = timedelta(days=365)

init_db()

CATEGORY_LABELS = {
    "outerwear": "Верхняя одежда",
    "top": "Верх (футболка/рубашка/свитер)",
    "bottom": "Низ (брюки/юбка)",
    "dress": "Платье/комбинезон",
    "shoes": "Обувь",
    "accessory": "Аксессуар",
}

STYLE_OPTIONS = {
    "casual": "Повседневный",
    "classic": "Классика",
    "sport": "Спортивный",
    "streetwear": "Стритвир",
    "minimal": "Минимализм",
    "business": "Деловой",
    "vintage": "Винтаж",
    "cozy": "Уютный / оверсайз",
}

SLOT_ICONS = {
    "outerwear": "🧥",
    "top": "👕",
    "bottom": "👖",
    "dress": "👗",
    "shoes": "👟",
    "accessory": "🧣",
}


def get_session_id() -> str:
    if "session_id" not in session:
        session["session_id"] = uuid.uuid4().hex
    session.permanent = True
    return session["session_id"]


def generate_imagen_look(items_list):
    """Формирует прямую URL-ссылку для Pollinations.ai.
    Загрузка происходит напрямую в браузере пользователя,
    что обходит блокировки IP-адресов Render (402/500).
    """
    if not items_list:
        return None

    items_description = ", ".join(items_list)
    prompt = (
        f"professional fashion studio lookbook photography image, "
        f"stylish full-body outfit on a model consisting of {items_description}, "
        f"clean minimalist background, high-end fashion magazine style, high resolution"
    )

    try:
        encoded_prompt = urllib.parse.quote(prompt)
        seed = uuid.uuid4().int % 100000
        
        # Возвращаем прямую ссылку для тега <img> в браузере
        return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&seed={seed}&model=flux"
    except Exception as e:
        print(f"Ошибка формирования ссылки генерации: {e}")
        return None

    except Exception as e:
        print(f"Ошибка генерации картинки через Pollinations.ai: {e}")
        return None


@app.context_processor
def inject_profile_flag():
    """Флаг для шаблонов: заполнен ли профиль (чтобы показать подсказку)."""
    sid = session.get("session_id")
    profile = get_profile(sid) if sid else None
    return {"has_profile": bool(profile and (profile.get("gender") or profile.get("age")))}


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


@app.route("/wardrobe/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    session_id = get_session_id()
    photo_path = delete_wardrobe_item(item_id, session_id)
    if photo_path and os.path.exists(photo_path):
        try:
            os.remove(photo_path)
        except Exception:
            pass
    return redirect(url_for("wardrobe"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    session_id = get_session_id()

    if request.method == "POST":
        gender = request.form.get("gender")
        if gender not in ("male", "female"):
            gender = None

        age = None
        try:
            age_value = int(request.form.get("age", "").strip())
            if 5 <= age_value <= 100:
                age = age_value
        except ValueError:
            pass

        styles = [k for k in request.form.getlist("styles") if k in STYLE_OPTIONS]
        notes = request.form.get("notes", "").strip()[:500]

        save_profile(session_id, gender, age, ",".join(styles), notes)
        return redirect(url_for("settings", saved=1))

    profile = get_profile(session_id) or {}
    selected_styles = [k for k in (profile.get("styles") or "").split(",") if k]
    return render_template(
        "settings.html",
        profile=profile,
        selected_styles=selected_styles,
        style_options=STYLE_OPTIONS,
        saved=request.args.get("saved"),
    )


@app.route("/api/generate-look", methods=["POST"])
def api_generate_look():
    """Эндпоинт для JS-асинхронного обновления картинки при клике на вещи"""
    data = request.get_json() or {}
    selected_items = data.get("items", [])

    image_url = generate_imagen_look(selected_items)
    if image_url:
        return jsonify({"success": True, "image_url": image_url})

    return jsonify({
        "success": False,
        "error": "Не удалось сгенерировать изображение, используется стандартный коллаж"
    })


@app.route("/outfit", methods=["GET", "POST"])
def outfit_form():
    if request.method == "POST":
        try:
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

            profile = get_profile(session_id)
            result = build_outfit(occasion, weather, wardrobe_items, profile)

            initial_items_desc = []
            if result.slots:
                for slot in result.slots:
                    if slot.get("options"):
                        opt = slot["options"][0]
                        if isinstance(opt, dict):
                            initial_items_desc.append(
                                opt.get("description", CATEGORY_LABELS.get(slot["category"], slot["category"]))
                            )
                        else:
                            initial_items_desc.append(str(opt))

            initial_image_url = generate_imagen_look(initial_items_desc) or ""

            collage_url = None
            collage_path = None
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
                initial_image_url=initial_image_url,
                mode=result.mode,
                slots=result.slots,
                category_labels=CATEGORY_LABELS,
                slot_icons=SLOT_ICONS,
            )
        except Exception as e:
            error_details = traceback.format_exc()
            return f"""
            <div style="padding: 30px; font-family: monospace; background: #ffe6e6; color: #990000; border: 2px solid #ff9999; margin: 40px; border-radius: 10px;">
                <h2 style="margin-top: 0;">⚠️ Ошибка при генерации образа:</h2>
                <pre style="white-space: pre-wrap; word-break: break-all; background: #fff; padding: 15px; border-radius: 5px; border: 1px solid #ffcccc;">{error_details}</pre>
            </div>
            """, 500

    return render_template("outfit_form.html")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
