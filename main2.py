import pyttsx3
import asyncio
from escpos.printer import Usb
from TikTokLive import TikTokLiveClient
from TikTokLive.events import GiftEvent, CommentEvent, ShareEvent
import requests
from PIL import Image, ImageDraw, ImageFont
import os
import json
import threading
import time
import socket
from PIL import ImageEnhance, ImageOps

# =========================================
# 🖨️ CLIENTE → SERVIDOR DE IMPRESIÓN
# =========================================


def enviar_a_impresora(payload):
    """Envía un diccionario JSON al servidor de impresión"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 6000))
        s.send(json.dumps(payload).encode("utf-8"))
        s.close()
        print(f"📨 Enviado a servidor de impresión ({payload.get('tipo', 'N/A')})")
    except Exception as e:
        print(f"⚠️ Error al conectar con servidor de impresión: {e}")


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


# ============ TIKTOK ============
client = TikTokLiveClient(unique_id="s1mple.god")  # <- sin @
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


def _safe_font(size=20):
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

def _pick_bold_font(size):
    # Windows
    if os.name == "nt":
        for path in [
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
        ]:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    # Linux
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def create_combined_image(profile_img, gift_img, user_name, gift_name, streak_text, total_gifts=1):
    """🎨 Estética del código USB, adaptada al servidor de impresión"""
    profile_img = create_rounded_profile_image(profile_img)
    W = 512
    spacing = 15

    # 🟢 Avatar grande y balanceado
    profile_img = profile_img.resize((370, 370), Image.LANCZOS)

    # 🟢 Ícono del regalo con fondo blanco y tamaño correcto
    gift_img = gift_img.convert("RGBA")
    white_bg = Image.new("RGB", gift_img.size, (255, 255, 255))
    white_bg.paste(gift_img, mask=gift_img.split()[-1] if gift_img.mode == "RGBA" else None)
    gift_img = white_bg.convert("L").resize((65, 65), Image.LANCZOS)

    # 🟢 Fuentes
    font_counter = _pick_bold_font(68)
    font_user = _pick_bold_font(46)
    font_thanks = _pick_bold_font(42)
    font_streak = _pick_bold_font(38)
    font_sep = _pick_bold_font(26)

    # 🟢 Lienzo general
    total_height = profile_img.height + 300
    canvas = Image.new("L", (W, total_height), 255)
    draw = ImageDraw.Draw(canvas)
    y = spacing

    # 🔸 Avatar centrado
    x_profile = (W - profile_img.width) // 2
    canvas.paste(profile_img, (x_profile, y))
    y += profile_img.height - 25

    # 🔸 Contador y gift a la derecha (ajustados)
    counter_text = f"x{total_gifts}"
    bbox = draw.textbbox((0, 0), counter_text, font=font_counter)
    cx = x_profile + profile_img.width - bbox[2] + 15
    cy = y - bbox[3] - 5
    draw.text((cx, cy), counter_text, fill=0, font=font_counter)
    canvas.paste(gift_img, (cx - 60, cy + 5))

    # 🔸 Texto debajo del avatar
    y = profile_img.height + spacing + 10

    # Bloque negro con usuario en blanco
    bbox_user = draw.textbbox((0, 0), user_name, font=font_user)
    label_w = bbox_user[2] + 40
    label_h = bbox_user[3] + 14
    label_x = (W - label_w) // 2
    label_y = y
    draw.rectangle([label_x, label_y, label_x + label_w, label_y + label_h], fill=0)
    draw.text((label_x + 20, label_y + 7), user_name, fill=255, font=font_user)
    y += label_h + 14

    # Línea “Gift xN”
    thanks_text = f"{gift_name} x{total_gifts}"
    bbox_thanks = draw.textbbox((0, 0), thanks_text, font=font_thanks)
    draw.text(((W - bbox_thanks[2]) // 2, y), thanks_text, fill=0, font=font_thanks)
    y += bbox_thanks[3] + 10

    # Línea “Racha de: N”
    bbox_streak = draw.textbbox((0, 0), streak_text, font=font_streak)
    draw.text(((W - bbox_streak[2]) // 2, y), streak_text, fill=0, font=font_streak)
    y += bbox_streak[3] + 10

    # Línea separadora
    sep = "-" * 32
    bbox_sep = draw.textbbox((0, 0), sep, font=font_sep)
    draw.text(((W - bbox_sep[2]) // 2, y), sep, fill=0, font=font_sep)

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

        # Fondo blanco si trae alpha
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
                profile_img = Image.new("RGB", (350, 350), "gray")
        else:
            profile_img = Image.new("RGB", (350, 350), "gray")

        # Mejoras para térmica
        if profile_img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", profile_img.size, (255, 255, 255))
            bg.paste(profile_img, mask=profile_img.split()[-1])
            profile_img = bg
        else:
            profile_img = profile_img.convert("RGB")

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

        # Guardar como BMP 1-bit, ruta absoluta
        bw_img = combined_img.convert("1")
        gift_path = os.path.abspath("gift_ticket.bmp")
        bw_img.save(gift_path)
        bw_img.close()
        time.sleep(0.3)

        if os.path.exists(gift_path) and os.path.getsize(gift_path) > 0:
            enviar_a_impresora({
                "tipo": "imagen",
                "imagenes": [gift_path]
            })
            print(f"🖨️ Gift enviado al servidor (imagen): {gift_path}")
        else:
            print("⚠️ Archivo gift_ticket.bmp no generado correctamente.")
            return

        enviar_a_impresora({
            "tipo": "texto",
            "contenido": texto,
            "modo_directo": True
        })

        print("✅ Gift enviado al servidor (imagen + texto térmico grande).")

    except Exception as e:
        print(f"⚠️ Error al enviar gift al servidor: {e}")
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

    texto = f"{user_id}:\n{comment_text}\n{'-'*32}\n"
    payload = {"tipo": "texto", "contenido": texto}
    enviar_a_impresora(payload)


# ====== likes =========
from TikTokLive.events import LikeEvent

last_like = {"user_id": None, "count": 0}

@client.on(LikeEvent)
async def on_like(event: LikeEvent):
    global last_like

    try:
        with open(CONFIG_FILE, "r") as f:
            current_config = json.load(f)
    except Exception as e:
        print(f"⚠️ Error leyendo config.json: {e}")
        current_config = config

    if not current_config.get("likes", True):
        print("❤️ Likes desactivados por configuración.")
        return

    user_id = event.user.unique_id
    like_count = getattr(event, "likes", 0)
    total_likes = getattr(event, "total_likes", 0)

    if last_like["user_id"] == user_id and last_like["count"] == total_likes:
        return
    last_like = {"user_id": user_id, "count": total_likes}

    print(f"❤ {user_id} dio {like_count} likes (total {total_likes})")

    # 💬 Enviar texto nativo al servidor
    texto = (
        f"\n\n  LIKE de {user_id}  \n"
        f"{'-'*32}\n\n"
    )

    payload = {
        "tipo": "texto",
        "contenido": texto
    }
    enviar_a_impresora(payload)
    print("🖨️ Like enviado al servidor (tamaño igual al de comentarios).")


@client.on(ShareEvent)
async def on_share(event: ShareEvent):
    try:
        with open(CONFIG_FILE, "r") as f:
            current_config = json.load(f)
    except Exception as e:
        print(f"⚠️ Error leyendo config.json en share: {e}")
        current_config = config

    if not current_config.get("shares", True):
        print("🔄 Compartir desactivado por configuración.")
        return

    user_id = event.user.unique_id
    print(f"🔄 {user_id} compartió el stream")

    texto = (
        f"\n\n  {user_id} compartio el LIVE!  \n"
        f"{'-'*32}\n\n"
    )
    payload = {
        "tipo": "texto",
        "contenido": texto
    }
    enviar_a_impresora(payload)
    print("🖨️ Share enviado al servidor (igual estilo que like).")

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

