from flask import Flask, request, jsonify, render_template_string, redirect
import requests
import os
import json
import random
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
from escpos.printer import Usb
from datetime import datetime
import threading
import socket, json


# ====================================================
# CONFIG
# ====================================================
ACCESS_TOKEN = "APP_USR-4708500391203353-101921-06630c2067283d942cf41226049b5e51-340423884" #test: APP_USR-5730383643220019-110217-97d3d4394b8a9e2b9de6ca23cb88ad2e-2959448473
NGROK_URL = "https://mxtechno.ngrok.app"
app = Flask(__name__)

# ====================================================
# IMPRESORA
# ====================================================


def enviar_a_impresora(texto, tipo="texto"):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 6000))
    payload = json.dumps({"tipo": tipo, "contenido": texto})
    s.send(payload.encode("utf-8"))
    s.close()

# ====================================================
# UTILIDADES GRÁFICAS
# ====================================================
def _center_x(draw, txt, font, W):
    # ancho real del texto
    l, t, r, b = draw.textbbox((0,0), txt, font=font)
    return (W - (r - l)) // 2


def _safe_font(size=28):
    try:
        # Usa Arial directamente desde Windows
        font_path = "C:\\Windows\\Fonts\\arial.ttf"
        size = int(size * 1.1)  # 🔹 factor grande para compensar DPI
        return ImageFont.truetype(font_path, size)
    except Exception as e:
        print(f"⚠️ Error cargando fuente Arial: {e}")
        return ImageFont.load_default()


def render_centered_text(lines, sizes, width=512, padding_y=15, gap=6, bold_lines=None):
    """
    Dibuja texto centrado con opción de líneas en negrita (simulada).
    bold_lines: lista de índices de líneas que deben imprimirse en negrita
    """
    bold_lines = bold_lines or []
    fonts = [_safe_font(sz) for sz in sizes]

    tmp = Image.new("L", (1, 1), 255)
    dtmp = ImageDraw.Draw(tmp)
    widths, heights = [], []
    for line, fnt in zip(lines, fonts):
        bbox = dtmp.textbbox((0, 0), line, font=fnt)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
    total_h = padding_y * 2 + sum(heights) + gap * (len(lines) - 1)
    img = Image.new("L", (width, total_h), 255)
    draw = ImageDraw.Draw(img)

    y = padding_y
    for i, (line, fnt, w, h) in enumerate(zip(lines, fonts, widths, heights)):
        x = (width - w) // 2

        # 💪 Simulación de negrita (dibujar dos veces con desplazamiento)
        if i in bold_lines:
            draw.text((x, y), line, fill=0, font=fnt)
            draw.text((x + 1, y), line, fill=0, font=fnt)
        else:
            draw.text((x, y), line, fill=0, font=fnt)

        y += h + gap

    return img

from PIL import Image, ImageDraw, ImageFont

def _draw_vip_badge(base_img, cx, y_top, badge_height=270):
    """Pega el icono VIP centrado, con espacio para el texto debajo."""
    icon_path = os.path.join("avatars", "icon_vip.png")

    if not os.path.exists(icon_path):
        print("⚠️ No se encontró icon_vip.png, usando texto.")
        draw = ImageDraw.Draw(base_img)
        font = _safe_font(150)
        txt = "VIP"
        l, t, r, b = draw.textbbox((0, 0), txt, font=font)
        draw.text((cx - (r-l)//2, y_top + (badge_height - (b-t))//2), txt, fill=0, font=font)
        return

    try:
        from PIL import ImageEnhance
        icon = Image.open(icon_path).convert("RGBA")

        # Fondo blanco
        bg = Image.new("RGBA", icon.size, (255, 255, 255, 255))
        bg.paste(icon, mask=icon.split()[-1])
        icon = bg.convert("RGB")

        # Escalar (un poco más chico para dejar espacio)
        target_w = int(base_img.width * 0.55)
        ratio = target_w / icon.width
        new_h = int(icon.height * ratio)
        icon = icon.resize((target_w, new_h), Image.LANCZOS)

        # Ajustes para térmica
        icon = ImageEnhance.Contrast(icon).enhance(2.5)
        icon = ImageEnhance.Brightness(icon).enhance(0.8)
        gray = icon.convert("L")
        bw = gray.point(lambda x: 0 if x < 200 else 255, "1")

        # Centrado — con margen superior extra para que no choque el texto
        x = (base_img.width - bw.width) // 2
        y = y_top + 20  # 👈 bajá o subí este número si querés más o menos espacio
        base_img.paste(bw, (x, y))

        print("✅ Icono VIP centrado correctamente (con margen).")

    except Exception as e:
        print(f"⚠️ Error procesando icon_vip.png: {e}")

def _draw_mp_logo(base_img, cx, y_top, max_width_ratio=0.6):
    """Pega el logo de Mercado Pago centrado, sin fondo negro ni inversión."""
    logo_path = os.path.join("avatars", "logo_mp.png")

    if not os.path.exists(logo_path):
        print("⚠️ No se encontró logo_mp.png")
        return 0

    try:
        from PIL import ImageEnhance
        logo = Image.open(logo_path).convert("RGBA")

        # Escalar
        target_w = int(base_img.width * max_width_ratio)
        ratio = target_w / logo.width
        new_h = int(logo.height * ratio)
        logo = logo.resize((target_w, new_h), Image.LANCZOS)

        # Fondo blanco (para limpiar transparencia)
        bg = Image.new("RGBA", logo.size, (255, 255, 255, 255))
        bg.paste(logo, (0, 0), logo)
        logo = bg.convert("L")

        # Aumentar contraste y brillo leve para térmica
        logo = ImageEnhance.Contrast(logo).enhance(2.0)
        logo = ImageEnhance.Brightness(logo).enhance(1.3)

        # Centrado
        x = (base_img.width - logo.width) // 2
        base_img.paste(logo, (x, y_top))
        print("✅ Logo Mercado Pago centrado correctamente.")
        return y_top + logo.height  # devolvemos la nueva posición inferior

    except Exception as e:
        print(f"⚠️ Error procesando logo_mp.png: {e}")
        return y_top + 150

# ====================================================
# ICONOS ALEATORIOS + FONDO ESTILO TABLERO
# ====================================================
AVATAR_CACHE_DIR = "avatars"
os.makedirs(AVATAR_CACHE_DIR, exist_ok=True)
ICONOS = [
    os.path.join(AVATAR_CACHE_DIR, "icon_rayo.png"),
    os.path.join(AVATAR_CACHE_DIR, "icon_corazon.png"),
    os.path.join(AVATAR_CACHE_DIR, "icon_sonrisa.png")
]


def elegir_icono_aleatorio():
    disponibles = [i for i in ICONOS if os.path.exists(i)]
    if disponibles:
        return random.choice(disponibles)
    return None


def generar_fondo_tablero(width=512, height=512, tamaño_celda=32):
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    color1, color2 = 200, 150
    for y in range(0, height, tamaño_celda):
        for x in range(0, width, tamaño_celda):
            color = color1 if (x // tamaño_celda + y //
                               tamaño_celda) % 2 == 0 else color2
            draw.rectangle(
                [x, y, x + tamaño_celda, y + tamaño_celda], fill=color)
    return img


def preparar_icono_para_ticket(icono_path, max_width=384):
    try:
        # Abrimos el ícono con transparencia
        icon = Image.open(icono_path).convert("RGBA")
        w, h = icon.size
        if w > max_width:
            new_h = int(h * (max_width / w))
            icon = icon.resize((max_width, new_h), Image.LANCZOS)
            w, h = icon.size

        # Fondo tipo tablero (escala de grises)
        fondo = generar_fondo_tablero(512, h)
        fondo = fondo.convert("RGBA")  # lo pasamos a RGBA para poder pegar

        # Centrar el ícono sobre el fondo con transparencia
        x_offset = (512 - w) // 2
        # 👈 tercer parámetro = máscara alfa
        fondo.paste(icon, (x_offset, 0), icon)

        # Convertimos todo a escala de grises antes de imprimir
        final = fondo.convert("L")
        out_path = "icon_temp.bmp"
        final.save(out_path, format="BMP")
        return out_path
    except Exception as e:
        print(f"⚠️ Error generando fondo del icono: {e}")
        return icono_path


# ====================================================
# IMPRESIÓN DE TICKET ESTILIZADA
# ====================================================
def print_payment_ticket(payer, amount, status, tipo):
    # lienzo base (512 px de ancho para 80mm; si tu impresora es 58mm usa 384)
    W, H = 512, 860
    img = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(img)

    # fuentes
    f_small  = _safe_font(26)
    f_med    = _safe_font(32)
    f_big    = _safe_font(40)
    f_label  = _safe_font(28)

    # marco
    margin = 18
    draw.rectangle([margin, margin, W-margin, H-margin], outline=0, width=3)

    # --- ENCABEZADO ---
    top_section = margin + 5

    if tipo.upper() == "SORTEO":
        # === VIP ===
        _draw_vip_badge(img, cx=W // 2, y_top=top_section, badge_height=300)
        y_band = top_section + 270
        band_h = 60
        draw.rectangle([margin, y_band, W - margin, y_band + band_h], fill=0)
        txt = "PARTICIPANTE VIP"
        x = _center_x(draw, txt, f_med, W - 2 * margin) + margin
        draw.text((x, y_band + (band_h - 32) // 2), txt, fill=255, font=f_med)
        y_band += band_h

    else:
        # === TICKET NORMAL ===
        bottom_logo = _draw_mp_logo(img, cx=W // 2, y_top=top_section)
        y_band = bottom_logo + 30
        band_h = 0  # 👈 se define igual para evitar error
        txt = "PAGO RECIBIDO"
        x = _center_x(draw, txt, f_med, W - 2 * margin) + margin
        draw.text((x, y_band), txt, fill=0, font=f_med)
        y_band += 60


    # bloque datos
    y = y_band + band_h + 30
    def center_line(text, font, y):
        x = _center_x(draw, text, font, W)  # centrado global
        draw.text((x, y), text, fill=0, font=font)
        l,t,r,b = draw.textbbox((x,y), text, font=font)
        return b

    y = center_line("Usuario:", f_small, y) + 8
    y = center_line(payer.upper(), f_big, y) + 10
    y = center_line(f"Monto: ${int(amount):,}".replace(",", "."), f_small, y) + 6
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    y = center_line(f"Fecha: {now}", f_small, y) + 18

    # línea separadora fina centrada
    draw.line([margin, y, W-margin, y], fill=0, width=2)
    y += 18

    # caja de mensaje según tipo
    box_h = 100
    draw.rectangle([margin, y, W - margin, y + box_h], outline=0, width=2)

    if tipo.upper() == "SORTEO":
        txt1 = "¡Estás participando"
        txt2 = "del sorteo en vivo!"
    else:
        txt1 = "¡Gracias por tu apoyo!"
        txt2 = "¡Tu aporte hace posible el live!"

    x1 = _center_x(draw, txt1, f_label, W - 2 * margin) + margin
    x2 = _center_x(draw, txt2, f_label, W - 2 * margin) + margin
    draw.text((x1, y + 22), txt1, fill=0, font=f_label)
    draw.text((x2, y + 22 + 30), txt2, fill=0, font=f_label)
    y += box_h + 14


    # caja IG
    box_h2 = 100
    draw.rectangle([margin, y, W-margin, y+box_h2], outline=0, width=2)
    ig1 = "Sígueme en IG:"
    ig2 = "@maxii.agueroo"
    x1 = _center_x(draw, ig1, f_label, W - 2*margin) + margin
    x2 = _center_x(draw, ig2, f_label, W - 2*margin) + margin
    draw.text((x1, y + 22), ig1, fill=0, font=f_label)
    draw.text((x2, y + 22 + 30), ig2, fill=0, font=f_label)

    # recortar alto real (opcional, por si quedó largo)
    # aquí no hace falta; la impresora corta con p.cut()

    # guardar BMP 1-bit sin invertir (python-escpos imprime el negro tal cual)
    bmp_path = "ticket_vip.bmp"
    img = ImageOps.autocontrast(img)
    img_1b = img.convert("1")  # dither por defecto
    img_1b.save(bmp_path)

    # enviar al servidor de impresión
    payload = {"tipo": "imagen", "imagenes": [os.path.abspath(bmp_path)]}
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 6000))
    s.send(json.dumps(payload).encode("utf-8"))
    s.close()
    print("🖨️ Ticket VIP centrado enviado.")
# ====================================================
# RUTA: FORMULARIO DE DONACIÓN LIBRE
# ====================================================
HTML_FORM = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Donar a MXTECHNO</title>
  <style>
    body {
      font-family: 'Helvetica Neue', Arial, sans-serif;
      background: #f9f9f9;
      margin: 0;
      padding: 0;
      text-align: center;
    }
    header {
      background: black;
      color: white;
      padding: 30px 0 10px;
    }
    header img {
      width: 70px;
      height: 70px;
      border-radius: 50%;
      margin-bottom: 10px;
    }
    h1 {
      font-size: 22px;
      margin: 5px 0;
      letter-spacing: 1px;
    }
    p {
      color: #ccc;
      font-size: 14px;
    }
    main {
      margin-top: 40px;
    }
    .card {
      background: white;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      width: 400px;
      max-width: 90%;
      margin: 0 auto;
      padding: 30px;
    }
    .card h2 {
      margin-top: 0;
      font-size: 18px;
      font-weight: 600;
    }
    .amount-input {
      font-size: 32px;
      width: 120px;
      text-align: center;
      border: none;
      border-bottom: 2px solid #ddd;
      outline: none;
      margin-top: 10px;
    }
    .suggestions {
      margin: 20px 0;
    }
    .suggestions button {
      background: #eee;
      border: none;
      padding: 10px 20px;
      border-radius: 20px;
      margin: 5px;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }
    .suggestions button:hover {
      background: #0077ff;
      color: white;
    }
    .pay-button {
      background: #00b050;
      color: white;
      border: none;
      padding: 14px 30px;
      border-radius: 8px;
      font-size: 16px;
      cursor: pointer;
      margin-top: 10px;
      transition: background 0.3s;
    }
    .pay-button:hover {
      background: #00913d;
    }
    footer {
      margin-top: 40px;
      color: #aaa;
      font-size: 14px;
    }
    .socials {
      margin-top: 15px;
    }
    .socials a {
      margin: 0 10px;
      text-decoration: none;
      color: #000;
      font-size: 20px;
    }
  </style>
</head>
<body>
  <header>
    <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/TikTok_Icon_Black.svg/768px-TikTok_Icon_Black.svg.png" alt="TikTok">
    <h1>IMPRIME TICKETS EN VIVO!</h1>
    <p>Controla la impresora y participa en sorteos en directo 🎟</p>
  </header>

  <main>
    <div class="card">
      <h2>💸 Aparecé en la impresora (mínimo $300)</h2>
      <form action="/crear_preferencia" method="POST">
        <label>Ingresá el monto que querés donar:</label><br>
        <div>
          <span style="font-size:26px;position:relative;top:-8px;">$</span>
          <input type="number" name="monto" class="amount-input" min="300" required>
        </div>

        <div class="suggestions">
          <button type="button" onclick="setMonto(300)">$300</button>
          <button type="button" onclick="setMonto(500)">$500</button>
          <button type="button" onclick="setMonto(1000)">$1000</button>
          <button type="button" onclick="setMonto(1500)">$1500</button>
        </div>

        <button type="submit" class="pay-button">Elegir medio de pago 💳</button>
      </form>
    </div>
  </main>

  <footer>
    <p>Pago seguro con Mercado Pago</p>
    <div class="socials">
      <a href="https://www.tiktok.com/" target="_blank">🎵</a>
      <a href="https://www.instagram.com/" target="_blank">📸</a>
    </div>
  </footer>

  <script>
    function setMonto(valor) {
      document.querySelector('.amount-input').value = valor;
    }
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_FORM)


@app.route("/crear_preferencia", methods=["POST"])
def crear_preferencia():
    monto = float(request.form.get("monto", 0))
    data = {
        "items": [{
            "title": f"Donación Libre MXTECHNO (${monto})",
            "quantity": 1,
            "currency_id": "ARS",
            "unit_price": monto
        }],
        "notification_url": f"{NGROK_URL}/mp/webhook",
        "external_reference": "DONACION_LIBRE",

        # 👇 ESTA ES LA CLAVE
        "back_urls": {
            "success": "https://www.tiktok.com/",
            "failure": f"{NGROK_URL}/",
            "pending": f"{NGROK_URL}/"
        },
        "auto_return": "approved"
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.post(
        "https://api.mercadopago.com/checkout/preferences", headers=headers, json=data)
    r.raise_for_status()
    init_point = r.json()["init_point"]
    print(f"✅ Donación creada: ${monto} -> {init_point}")
    return redirect(init_point)


# ====================================================
# WEBHOOK DE PAGO (con delay y mensaje previo)
# ====================================================
procesados = set()  # 👈 evita duplicados


@app.route("/mp/webhook", methods=["POST"])
def mp_webhook():
    data = request.get_json(force=True)
    print("📩 Notificación de Mercado Pago recibida:", data)

    try:
        tipo = data.get("type") or data.get("topic")
        if tipo != "payment":
            print(f"ℹ️ Ignorando evento tipo '{tipo}'.")
            return jsonify({"status": "ignored"}), 200

        # 🧠 Detectar ID correctamente, sin importar el formato del JSON
        payment_id = None
        if isinstance(data.get("data"), dict):
            payment_id = data["data"].get("id")
        elif "resource" in data:
            payment_id = str(data["resource"]).split("/")[-1]
        elif "id" in data:
            payment_id = data["id"]

        if not payment_id:
            print("⚠️ No se encontró payment_id en la notificación.")
            return jsonify({"error": "no payment_id"}), 400

        # 🚫 Evitar duplicados
        if payment_id in procesados:
            print(f"⚠️ Pago {payment_id} ya procesado, ignorando.")
            return jsonify({"status": "duplicate"}), 200
        procesados.add(payment_id)

        # 📡 Obtener detalles del pago
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        resp = requests.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}", headers=headers)

        if resp.status_code != 200:
            print(f"⚠️ Error al consultar pago {payment_id}: {resp.text}")
            return jsonify({"error": "no payment found"}), 400

        payment = resp.json()

                # --- Datos del comprador ---
        payer_data = payment.get("payer", {})
        payer_id = payer_data.get("id")
        payer_first = payer_data.get("first_name", "")
        payer_last = payer_data.get("last_name", "")
        payer_email = payer_data.get("email", "")

        # 👤 Nombre del titular de la tarjeta (por si no tiene cuenta)
        card_info = payment.get("card", {}) or {}
        cardholder = card_info.get("cardholder", {})
        holder_name = cardholder.get("name", "")

        payer = "Desconocido"

        # 🧠 Intentar obtener nombre completo desde la cuenta de MP
        if payer_id:
            try:
                headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
                user_resp = requests.get(f"https://api.mercadopago.com/users/{payer_id}", headers=headers)
                if user_resp.status_code == 200:
                    user_data = user_resp.json()
                    first_name = user_data.get("first_name", "")
                    last_name = user_data.get("last_name", "")
                    if first_name or last_name:
                        payer = f"{first_name} {last_name}".strip()
            except Exception as e:
                print(f"⚠️ Error consultando /users/{payer_id}: {e}")

        # Si sigue vacío, usar los otros campos como respaldo
        if payer == "Desconocido":
            if payer_first or payer_last:
                payer = f"{payer_first} {payer_last}".strip()
            elif holder_name:
                payer = holder_name.strip()
            elif payer_email:
                payer = payer_email.split("@")[0]

        payer = payer or "Desconocido"


        # 🔍 Si Mercado Pago nos da un ID de usuario, consultamos /users/{payer_id}
        if payer_id:
            try:
                headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
                user_info = requests.get(f"https://api.mercadopago.com/users/{payer_id}", headers=headers).json()
                first_name = user_info.get("first_name", "")
                last_name = user_info.get("last_name", "")
                if first_name or last_name:
                    payer = f"{first_name} {last_name}".strip()
            except Exception as e:
                print(f"⚠️ Error consultando datos del usuario: {e}")

        # Si no hay nombre, usamos las otras fuentes
        if payer == "Desconocido":
            if payer_first or payer_last:
                payer = f"{payer_first} {payer_last}".strip()
            elif holder_name:
                payer = holder_name.strip()
            elif payer_email:
                payer = payer_email.split("@")[0]

        amount = payment.get("transaction_amount", 0)
        status = payment.get("status", "unknown")

        print(f"💳 Estado del pago {payment_id}: {status}")

        # 🚫 Solo imprimir si está aprobado
        if status != "approved":
            print(
                f"⚠️ Pago {payment_id} con estado '{status}', no se imprime.")
            return jsonify({"status": status}), 200

        # 🎟 Clasificar tipo
        # 🎟 Clasificar tipo según monto
        if amount >= 1500:
            tipo_ticket = "SORTEO"
        elif 300 <= amount < 1500:
            tipo_ticket = "NORMAL"
        else:
            print(f"⚠️ Donación de ${amount} ignorada (menor a $300).")
            return jsonify({"status": "ignored"}), 200


        # --- 💡 IMPRESIÓN RETARDADA ---
        def delayed_print():
            try:
                print("🕒 Esperando 6s antes de imprimir...")
                threading.Timer(6.0, print_payment_ticket, args=(
                    payer, amount, status, tipo_ticket)).start()
            except Exception as e:
                print(f"⚠️ Error en impresión diferida: {e}")

        threading.Thread(target=delayed_print).start()
        print(f"🕐 Impresión programada para {payer} (${amount})")


        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"❌ Error procesando pago: {e}")
        return jsonify({"error": str(e)}), 500

    
# ====================================================
# MAIN
# ====================================================
@app.after_request
def add_ngrok_header(response):
    # Evita el mensaje de advertencia de ngrok
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


if __name__ == "__main__":
    print(f"🚀 Servidor activo en {NGROK_URL}")
    print("👉 Abrí en tu navegador: http://127.0.0.1:8080")
    app.run(host="0.0.0.0", port=8080)