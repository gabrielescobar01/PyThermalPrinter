from flask import Flask, request, jsonify, render_template_string, redirect
import requests
import os
import json
import random
from PIL import Image, ImageDraw, ImageFont, ImageOps
from escpos.printer import Usb
from datetime import datetime
import threading
import socket, json


# ====================================================
# CONFIG
# ====================================================
ACCESS_TOKEN = "APP_USR-5730383643220019-110217-97d3d4394b8a9e2b9de6ca23cb88ad2e-2959448473"
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
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    ref = "#" + str(random.randint(10000, 99999))

    # =========================================
    # 💎 Texto diferenciado por tipo
    # =========================================
    if tipo == "SORTEO":
        header = "⧫ PARTICIPANTE VIP ⧫"
        footer = [
            "✨ ¡Estás participando del sorteo en vivo! ✨",
            f"N° de participación: {random.randint(1000, 9999)}",
            "Seguime en IG: @maxii.agueroo"
        ]
        accent_line = "/ / /" * 18
    else:
        header = "$  PAGO RECIBIDO  $"
        footer = [
            "♥ Gracias por tu apoyo ♥",
            "Seguime en IG: @maxii.agueroo"
        ]
        accent_line = "=" * 30

    # =========================================
    # 🖋️ Diseño del texto
    # =========================================
    lines = [
        accent_line,
        header,
        accent_line,
        "",
        f"Usuario:",
        f"{payer}",
        "",
        f"Monto: ${amount}",
        f"Fecha: {now}",
        "",
        "-----------------------------",
        *footer,
        "-----------------------------"
    ]

    # Escalado de fuente más llamativo
    if tipo == "SORTEO":
        sizes = [28, 46, 28, 16, 26, 30, 18, 32, 28, 24, 18, 26, 22, 22]
    else:
        sizes = [24, 38, 24, 16, 26, 30, 18, 30, 26, 22, 18, 24, 22, 22]

    # 💥 Negrita en el header y separadores
    bold_indices = [1, 2]
    img = render_centered_text(lines, sizes, bold_lines=bold_indices)
    img.save("mp_ticket.bmp")

# =========================================
# 🖼️ Logo según tipo de ticket
# =========================================
    if tipo == "SORTEO":
        vip_path = os.path.join(AVATAR_CACHE_DIR, "icon_vip.png")
        logo_mp_path = os.path.join(AVATAR_CACHE_DIR, "logo_mp.png")
        if os.path.exists(vip_path):
            try:
                # VIP grande centrado
                vip = Image.open(vip_path).convert("RGBA")
                vip_w = 400
                ratio = vip_w / vip.width
                vip = vip.resize((vip_w, int(vip.height * ratio)), Image.LANCZOS)
                canvas = Image.new("RGBA", (512, vip.height + 60), (255, 255, 255, 255))
                x_offset = (512 - vip.width) // 2
                canvas.paste(vip, (x_offset, 20), vip)

                # Logo MP pequeño en esquina inferior derecha
                if os.path.exists(logo_mp_path):
                    logo = Image.open(logo_mp_path).convert("RGBA")
                    logo = logo.resize((90, int(logo.height * (90 / logo.width))), Image.LANCZOS)
                    canvas.paste(logo, (512 - logo.width - 10, canvas.height - logo.height - 10), logo)

                final_logo = canvas.convert("L")
                final_logo = ImageOps.invert(final_logo)
                final_logo.save("logo_final.bmp", "BMP")

            except Exception as e:
                print(f"⚠️ Error generando logo VIP: {e}")
    else:
        logo_path = os.path.join(AVATAR_CACHE_DIR, "logo_mp.png")
        if os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo_w = 350
                ratio = logo_w / logo.width
                logo = logo.resize((logo_w, int(logo.height * ratio)), Image.LANCZOS)

                # Fondo blanco simple, sin tablero
                fondo = Image.new("RGBA", (512, logo.height + 40), (255, 255, 255, 255))
                x_offset = (512 - logo.width) // 2
                fondo.paste(logo, (x_offset, 20), logo)

                final_logo = fondo.convert("L")
                final_logo = ImageOps.invert(final_logo)
                final_logo.save("logo_final.bmp", "BMP")

            except Exception as e:
                print(f"⚠️ Error generando logo Mercado Pago: {e}")
    # =========================================
    # 🖨️ Envío al servidor de impresión
    # =========================================
    try:
        payload = {
            "tipo": "imagen",
            "imagenes": []
        }

        # Logo
        if os.path.exists("logo_final.bmp"):
            payload["imagenes"].append("logo_final.bmp")

        # Texto del ticket
        if os.path.exists("mp_ticket.bmp"):
            payload["imagenes"].append("mp_ticket.bmp")

        # Enviar al servidor de impresión
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 6000))
        s.send(json.dumps(payload).encode("utf-8"))
        s.close()

        print(f"🧾 Ticket enviado al servidor ({tipo})")

    except Exception as e:
        print(f"⚠️ Error al enviar ticket: {e}")


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
        elif amount >= 300:
          tipo_ticket = "IMPRESION"
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