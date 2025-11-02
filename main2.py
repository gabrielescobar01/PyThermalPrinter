import pyttsx3
import asyncio
from escpos.printer import Usb
from TikTokLive import TikTokLiveClient
from TikTokLive.events import GiftEvent, CommentEvent
import requests
from PIL import Image, ImageDraw, ImageFont
import os
import json
import threading
import time
from PIL import ImageEnhance, ImageOps

# ============ CONFIG ============

CONFIG_FILE = "config.json"
config = {}

def load_config():
    """Carga configuración desde config.json"""
    if not os.path.exists(CONFIG_FILE):
        default = {"gifts": True, "likes": False, "comments": False, "tts": True}
        with open(CONFIG_FILE, "w") as f:
            json.dump(default, f, indent=2)
        return default

    with open(CONFIG_FILE) as f:
        return json.load(f)


def watch_config(interval=3):
    """Monitorea config.json y recarga automáticamente si cambia."""
    global config
    last_config = None
    while True:
        try:
            with open(CONFIG_FILE) as f:
                new_config = json.load(f)
            if new_config != last_config:
                config = new_config
                last_config = new_config
                print(f"♻️ Config recargada: {config}")
        except Exception as e:
            print(f"Error leyendo config.json: {e}")
        time.sleep(interval)

def render_centered_block(
    lines,                # lista de strings a imprimir (cada string = una línea)
    font_sizes,           # lista de tamaños (misma longitud que lines)
    max_width=512,
    padding_y=10,
    line_gap=6,
    offset_x=0            # calibración horizontal en píxeles (negativo = a la izquierda)
):
    """Renderiza líneas centradas en una imagen de max_width px (grises)"""
    fonts = [_safe_font(sz) for sz in font_sizes]

    # 1) Medimos cada línea con la fuente exacta
    tmp = Image.new("L", (1, 1), 255)
    dtmp = ImageDraw.Draw(tmp)
    widths, heights = [], []
    for txt, fnt in zip(lines, fonts):
        # textbbox da alto/alto exactos; textlength (si está) sirve para ancho fino
        try:
            w = int(dtmp.textlength(txt, font=fnt))
        except Exception:
            bbox = dtmp.textbbox((0, 0), txt, font=fnt)
            w = bbox[2] - bbox[0]
        h = fnt.getbbox(txt)[3]
        widths.append(w)
        heights.append(h)

    total_h = padding_y*2 + sum(heights) + line_gap*(len(lines)-1)
    img = Image.new("L", (max_width, total_h), 255)
    draw = ImageDraw.Draw(img)

    # 2) Pintamos cada línea centrada con offset opcional
    y = padding_y
    for txt, fnt, w, h in zip(lines, fonts, widths, heights):
        x = (max_width - w) // 2 + int(offset_x)
        draw.text((x, y), txt, fill=0, font=fnt)
        y += h + line_gap

    return img

# ============ TextToSpeech ============

engine = pyttsx3.init()
engine.setProperty("rate", 180)
engine.setProperty("voice", "spanish")  # podés cambiarlo por otra voz disponible

# ============ IMPRESORA ============
try:
    p = Usb(0x067b, 0x2305, 0, profile="TM-T88III", encoding="utf-8")
    print("Printer initialized")
    printer_ready = True
except Exception as e:
    print(f"Error initializing printer: {e}")
    printer_ready = False


# ============ TIKTOK ============
client = TikTokLiveClient(unique_id="brendaesc")  # <- sin @
print("TikTokLive client initialized")

config = load_config()
print(f"Config loaded: {config}")

threading.Thread(target=watch_config, daemon=True).start()

# ============ VARIABLES ============
user_streaks = {}
user_timers = {}
last_comment = {"user_id": None, "comment_text": None}

# ============ FALLBACK ============
FALLBACK_GIFT_PATH = "logo.png"
if not os.path.exists(FALLBACK_GIFT_PATH):
    img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.rectangle([10, 10, 90, 90], outline="black", width=3)
    draw.text((30, 35), "🎁", fill="black", font=font)
    img.save(FALLBACK_GIFT_PATH)
    print("Fallback gift image created.")


# ============ FUNCIONES ============
def get_image_url(image_obj):
    """Devuelve una URL válida o None."""
    try:
        if image_obj is None:
            return None
        if isinstance(image_obj, str):
            if image_obj.startswith("//"):
                return "https:" + image_obj
            if image_obj.startswith("http"):
                return image_obj
            return "https://" + image_obj.lstrip("/")
        if hasattr(image_obj, "url_list") and image_obj.url_list:
            return image_obj.url_list[0]
        if hasattr(image_obj, "url"):
            return image_obj.url if isinstance(image_obj.url, str) else image_obj.url[0]
        if hasattr(image_obj, "uri") and image_obj.uri:
            uri = image_obj.uri
            if isinstance(uri, (list, tuple)):
                uri = uri[0]
            if uri.startswith("//"):
                return "https:" + uri
            if uri.startswith("http"):
                return uri
            return "https://" + uri.lstrip("/")
    except Exception:
        pass
    return None


def get_user_avatar_url(user):
    """Busca la mejor URL de avatar disponible."""
    candidates = ("avatar_larger", "avatar_medium", "avatar_thumb", "profile_picture")
    for attr in candidates:
        img_obj = getattr(user, attr, None)
        url = get_image_url(img_obj)
        if url:
            return url
    return None


def _safe_font(size=30):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except IOError:
        return ImageFont.load_default()


def create_rounded_profile_image(profile_img):
    """Recorta imagen circular con borde negro y fondo blanco para impresión térmica."""
    size = (350, 350)
    profile_img = profile_img.convert("RGB").resize(size, Image.LANCZOS)

    # Máscara circular
    mask = Image.new("L", size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, size[0], size[1]), fill=255)

    # Fondo blanco
    bg = Image.new("RGB", size, (255, 255, 255))
    bg.paste(profile_img, (0, 0), mask=mask)

    # ✨ Agregar borde circular negro
    border_thickness = 6
    border = ImageDraw.Draw(bg)
    border.ellipse(
        (
            border_thickness // 2,
            border_thickness // 2,
            size[0] - border_thickness // 2,
            size[1] - border_thickness // 2,
        ),
        outline="black",
        width=border_thickness,
    )

    # 🔆 Ajustar brillo/contraste para visibilidad térmica
    bg = ImageEnhance.Brightness(bg).enhance(1.15)
    bg = ImageEnhance.Contrast(bg).enhance(1.35)
    bg = ImageOps.autocontrast(bg)

    # 🎨 Escala de grises + tramado
    gray = bg.convert("L")
    dithered = gray.convert("1", dither=Image.FLOYDSTEINBERG)

    # ⚡️ Invertir bits (mejor lectura en TM-T88)
    inverted = ImageOps.invert(dithered.convert("L")).convert("1")

    # ✅ Fondo blanco final
    final = Image.new("1", size, 1)  # 1 = blanco
    final.paste(inverted, mask=mask)

    return final

def create_combined_image(profile_img, gift_img, user_name, gift_name, streak_text, total_gifts=1):
    """Estilo MXTechno: circular + contador + etiqueta + thank you"""
    # Perfil ya viene optimizado en B/N
    profile_img = create_rounded_profile_image(profile_img)

    # Fondo blanco para el ícono del regalo
    gift_img = gift_img.convert("RGBA")
    white_bg = Image.new("RGB", gift_img.size, (255, 255, 255))
    white_bg.paste(gift_img, mask=gift_img.split()[-1] if gift_img.mode == "RGBA" else None)
    gift_img = white_bg.convert("L").resize((70, 70), Image.LANCZOS)

    # Fuentes
    font_label = _safe_font(36)      # nombre con fondo negro
    font_thanks = _safe_font(28)     # "Thank you for..."
    font_streak = _safe_font(26)
    font_counter = _safe_font(42)    # x120
    spacing = 15
    max_width = 512

    # Crear lienzo
    total_height = profile_img.height + 230
    canvas = Image.new("L", (max_width, total_height), 255)
    draw = ImageDraw.Draw(canvas)

    y = spacing

    # 1️⃣ Imagen circular centrada
    x_profile = (max_width - profile_img.width) // 2
    canvas.paste(profile_img, (x_profile, y))

    # 2️⃣ Texto sobre la imagen (contador del gift)
    counter_text = f"x{total_gifts}"
    bbox = draw.textbbox((0, 0), counter_text, font=font_counter)
    text_x = x_profile + profile_img.width - bbox[2] - 15
    text_y = y + profile_img.height - bbox[3] - 15
    draw.text((text_x, text_y), counter_text, fill=0, font=font_counter)

    # 3️⃣ (Opcional) Ícono del regalo al lado del contador
    gift_resized = gift_img.resize((50, 50), Image.LANCZOS)
    canvas.paste(gift_resized, (text_x - 55, text_y + 5))

    y += profile_img.height + spacing

    # 4️⃣ Etiqueta del usuario (nombre con fondo negro)
    username_bbox = draw.textbbox((0, 0), user_name, font=font_label)
    label_w = username_bbox[2] + 40
    label_h = username_bbox[3] + 10
    label_x = (max_width - label_w) // 2
    label_y = y
    draw.rectangle([label_x, label_y, label_x + label_w, label_y + label_h], fill=0)
    draw.text((label_x + 20, label_y + 5), user_name, fill=255, font=font_label)
    y += label_h + spacing

    # 5️⃣ Línea "Thank you for Xx Gift"
    thank_text = f"Thank you for {total_gifts}x {gift_name}"
    bbox2 = draw.textbbox((0, 0), thank_text, font=font_thanks)
    draw.text(((max_width - bbox2[2]) // 2, y), thank_text, fill=0, font=font_thanks)
    y += 50

    # 6️⃣ Línea punteada de separación
    sep_text = "-" * 30
    bbox_sep = draw.textbbox((0, 0), sep_text, font=font_streak)
    draw.text(((max_width - bbox_sep[2]) // 2, y), sep_text, fill=0, font=font_streak)

    return canvas

# ============ HANDLERS ============

async def handle_gift_end(user_id):
    print(f"handle_gift_end called for user_id: {user_id}")
    await asyncio.sleep(5)
    if user_id not in user_streaks:
        return

    streak = user_streaks[user_id]["streak"]
    gift_name = user_streaks[user_id]["gift_name"]
    print(f"Procesando impresión para {user_id}...")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}

        # ---------- DESCARGAR GIFT ----------
        gift_url = user_streaks[user_id]["gift_image"]
        gift_img = None
        if gift_url:
            try:
                r = requests.get(gift_url, timeout=10, headers=headers)
                r.raise_for_status()
                with open("tmp_gift.webp", "wb") as f:
                    f.write(r.content)
                gift_img = Image.open("tmp_gift.webp")
            except Exception as e:
                print(f"⚠️ Error al bajar gift ({e}), usando fallback.")
        if gift_img is None:
            gift_img = Image.open(FALLBACK_GIFT_PATH)

        # --- Asegurar fondo blanco sin negro ---
        if gift_img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", gift_img.size, (255, 255, 255))
            bg.paste(gift_img, mask=gift_img.split()[-1])
            gift_img = bg
        else:
            gift_img = gift_img.convert("RGB")

        # ---------- DESCARGAR AVATAR ----------
        profile_url = user_streaks[user_id]["profile_picture"]
        if profile_url:
            try:
                r = requests.get(profile_url, timeout=10, headers=headers)
                r.raise_for_status()
                with open("tmp_avatar.webp", "wb") as f:
                    f.write(r.content)
                profile_img = Image.open("tmp_avatar.webp")
            except Exception as e:
                print(f"⚠️ Error al bajar avatar ({e}), usando gris.")
                profile_img = Image.new("RGB", (350, 350))
        else:
            profile_img = Image.new("RGB", (350, 350), "gray")

            print(f"🖼️ Guardando avatar temporal: {profile_url}")
            profile_img.save("debug_avatar_original.jpg")
            profile_img.show()

        # --- Convertir RGBA -> fondo blanco y mejorar visibilidad ---
        if profile_img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", profile_img.size, (255, 255, 255))
            bg.paste(profile_img, mask=profile_img.split()[-1])
            profile_img = bg
        else:
            profile_img = profile_img.convert("RGB")

        # --- Mejorar brillo/contraste para térmica ---
        profile_img = ImageEnhance.Brightness(profile_img).enhance(1.3)
        profile_img = ImageEnhance.Contrast(profile_img).enhance(1.5)
        profile_img = ImageOps.autocontrast(profile_img)

        # ---------- TEXTO Y COMPOSICIÓN ----------
        combined_img = create_combined_image(
            profile_img,
            gift_img,
            user_id,
            gift_name,
            f"Racha de: {streak}",
            total_gifts=streak
        )

        bw_img = combined_img.convert("1")
        bw_img.save("gift_ticket.bmp")

        # ---------- IMPRESIÓN ----------
        if printer_ready:
            p.text("\n")
            p.image("gift_ticket.bmp", high_density_vertical=True, high_density_horizontal=True)
            p.cut()
            print("✅ Gift impreso correctamente, con imagen visible y sin fondo negro.")
        else:
            bw_img.show()
            print("⚠️ Impresora no disponible, simulación en pantalla.")

    except Exception as e:
        print(f"❌ Error al manejar gift: {e}")

    finally:
        del user_streaks[user_id]



@client.on(GiftEvent)
async def on_gift(event: GiftEvent):
    try:
        # === Leer config en tiempo real ===
        with open(CONFIG_FILE, "r") as f:
            current_config = json.load(f)
    except Exception as e:
        print(f"⚠️ Error leyendo config.json: {e}")
        current_config = config

    if not current_config.get("gifts", True):
        print("🎁 Gifts desactivados por configuración.")
        return

    # === Datos base ===
    user_id = event.user.unique_id
    gift_name = event.gift.name
    diamonds = event.gift.diamond_count
    print(f"💎 Gift recibido de {user_id}: {gift_name} ({diamonds} diamonds)")

    # === Extracción correcta del avatar usando m_urls ===
    avatar_url = None
    try:
        avatar_thumb = getattr(event.user, "avatar_thumb", None)
        if avatar_thumb and hasattr(avatar_thumb, "m_urls"):
            urls = getattr(avatar_thumb, "m_urls", [])
            if urls and isinstance(urls, list):
                avatar_url = urls[0]

        if avatar_url and avatar_url.startswith("//"):
            avatar_url = "https:" + avatar_url

        if avatar_url:
            print(f"🖼️ Avatar encontrado para {event.user.unique_id}: {avatar_url}")
        else:
            print(f"⚠️ {event.user.unique_id} sin avatar, usando gris.")
    except Exception as e:
        print(f"❌ Error extrayendo avatar: {e}")
        avatar_url = None



    # === Imagen del gift ===
    gift_image_url = get_image_url(event.gift.image)

    # === Actualizar streaks ===
    if user_id in user_streaks:
        user_streaks[user_id]["streak"] += diamonds
    else:
        user_streaks[user_id] = {
            "streak": diamonds,
            "gift_name": gift_name,
            "gift_image": gift_image_url,
            "profile_picture": avatar_url,
        }

    # === Reiniciar temporizador ===
    if user_id in user_timers:
        user_timers[user_id].cancel()

    user_timers[user_id] = asyncio.create_task(handle_gift_end(user_id))





@client.on(CommentEvent)
async def on_comment(event: CommentEvent):
    global last_comment

    try:
        with open(CONFIG_FILE, "r") as f:
            current_config = json.load(f)
    except Exception as e:
        print(f"⚠️ Error leyendo config.json en tiempo real: {e}")
        current_config = config  # fallback

    if not current_config.get("comments", True):
        print("💬 Comentarios desactivados por configuración.")
        return

    user_id = event.user.unique_id
    comment_text = event.comment

    if last_comment["user_id"] == user_id and last_comment["comment_text"] == comment_text:
        return  # Omitir duplicado

    last_comment = {"user_id": user_id, "comment_text": comment_text}
    print(f"{user_id}: {comment_text}")

    if printer_ready:
        p.set(align="center", bold=True)
        p.text(f"{user_id}:\n")
        p.set(align="center", bold=False)
        p.text(f"{comment_text}\n")
        p.text("-" * 32 + "\n")
        p.set(align="left")


# ====== likes =========
from TikTokLive.events import LikeEvent

last_like = {"user_id": None, "count": 0}

@client.on(LikeEvent)
async def on_like(event: LikeEvent):
    global last_like

    # Leer config en tiempo real
    try:
        with open(CONFIG_FILE, "r") as f:
            current_config = json.load(f)
    except Exception as e:
        print(f"⚠️ Error leyendo config.json: {e}")
        current_config = config  # fallback

    if not current_config.get("likes", True):
        print("❤️ Likes desactivados por configuración.")
        return

    user_id = event.user.unique_id
    like_count = getattr(event, "likes", 0)
    total_likes = getattr(event, "total_likes", 0)

    # Evitar duplicados
    if last_like["user_id"] == user_id and last_like["count"] == total_likes:
        return
    last_like = {"user_id": user_id, "count": total_likes}

    print(f"❤ {user_id} dio {like_count} likes (total {total_likes})")

    if printer_ready:
        try:
            # 1) Bloque principal (corazón + like + usuario) centrado
            main_text = f"❤ LIKE de {user_id} ❤"
            offset_px = current_config.get("center_offset_px", 0)  # calibra acá si hace falta
            main_img = render_centered_block(
                lines=[main_text],
                font_sizes=[26],     # más chico que antes, como pediste
                max_width=512,
                padding_y=10,
                line_gap=6,
                offset_x=offset_px
            )

            # 2) Línea separadora como imagen (no con p.text)
            sep_text  = "-------------------------------"
            sep_img = render_centered_block(
                lines=[sep_text],
                font_sizes=[18],
                max_width=512,
                padding_y=6,
                line_gap=0,
                offset_x=offset_px
            )

            # 3) (Opcional) Total de likes como segunda línea centrada
            total_line = f"Total likes: {total_likes}"
            total_img = render_centered_block(
                lines=[total_line],
                font_sizes=[20],
                max_width=512,
                padding_y=6,
                line_gap=0,
                offset_x=offset_px
            )

            # 4) Imprimir todo
            main_img.save("like_main.bmp")
            sep_img.save("like_sep.bmp")
            total_img.save("like_total.bmp")

            p.image("like_main.bmp")
            p.image("like_sep.bmp")
            p.image("like_total.bmp")


            print("🖨️ Like impreso centrado de forma precisa ❤")
        except Exception as e:
            print(f"Error imprimiendo like: {e}")

# ============ MAIN ============

if __name__ == "__main__":
    print("Running...")
    try:
        client.run()
    except Exception as e:
        print(f"❌ Error conectando a TikTokLive: {e}")
        print("Modo local de prueba activo...")

        user_id = "test_user"
        user_streaks[user_id] = {
            "streak": 3,
            "gift_name": "Rose",
            "gift_image": None,
            "profile_picture": None,
        }
        asyncio.run(handle_gift_end(user_id))

