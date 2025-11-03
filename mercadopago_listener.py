from flask import Flask, request, jsonify, render_template_string, redirect
import requests, os, json, random
from PIL import Image, ImageDraw, ImageFont, ImageOps
from escpos.printer import Usb
from datetime import datetime
import threading


# ====================================================
# CONFIG
# ====================================================
ACCESS_TOKEN = "APP_USR-5730383643220019-110217-97d3d4394b8a9e2b9de6ca23cb88ad2e-2959448473"
NGROK_URL = "https://mxtechno.ngrok.app"
app = Flask(__name__)

# ====================================================
# IMPRESORA
# ====================================================
try:
    p = Usb(0x067b, 0x2305, 0, profile="TM-T88III", encoding="utf-8")
    p.profile.media["width"]["pixel"] = 512
    printer_ready = True
    print("🖨️ Impresora lista para Mercado Pago")
except Exception as e:
    printer_ready = False
    print(f"⚠️ Error iniciando impresora: {e}")

# ====================================================
# UTILIDADES GRÁFICAS
# ====================================================
def _safe_font(size=28):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except IOError:
        return ImageFont.load_default()

def render_centered_text(lines, sizes, width=512, padding_y=15, gap=6):
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
    for line, fnt, w, h in zip(lines, fonts, widths, heights):
        x = (width - w) // 2
        draw.text((x, y), line, fill=0, font=fnt)
        y += h + gap
    return img

# ====================================================
# ICONOS ALEATORIOS
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

def preparar_icono_para_ticket(icono_path, max_width=384):
    try:
        img = Image.open(icono_path).convert("L")
        w, h = img.size
        if w > max_width:
            new_h = int(h * (max_width / w))
            img = img.resize((max_width, new_h), Image.LANCZOS)
            w, h = img.size
        canvas = Image.new("L", (512, h), 255)
        x_offset = (512 - w) // 2
        canvas.paste(img, (x_offset, 0))
        out_path = "icon_temp.bmp"
        canvas.save(out_path, format="BMP")
        return out_path
    except Exception as e:
        print(f"⚠️ Error ajustando icono: {e}")
        return icono_path

# ====================================================
# IMPRESIÓN DE TICKET
# ====================================================
def print_payment_ticket(payer, amount, status, tipo):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    ref = "#" + str(random.randint(10000, 99999))
    if tipo == "SORTEO":
        header = "🎟 PARTICIPANTE VIP 🎟"
        footer = "Estás participando del sorteo en vivo!"
    else:
        header = "💰 DONACIÓN RECIBIDA 💰"
        footer = "Gracias por tu apoyo ❤️"

    lines = [
        "================================",
        header,
        "================================",
        f"Usuario: {payer}",
        f"Monto: ${amount}",
        f"Fecha: {now}",
        f"Ref: {ref}",
        "-------------------------------",
        footer,
        "================================"
    ]
    sizes = [20, 30, 20, 26, 26, 22, 22, 22, 22]

    img = render_centered_text(lines, sizes)
    img.save("mp_ticket.bmp")

    icono = elegir_icono_aleatorio()
    if printer_ready:
        p.text("\n")
        if icono and os.path.exists(icono):
            icono_ajustado = preparar_icono_para_ticket(icono)
            p.image(icono_ajustado, high_density_horizontal=True, high_density_vertical=True)
        p.image("mp_ticket.bmp", high_density_horizontal=True, high_density_vertical=True)
        p.cut()
        print("🧾 Ticket impreso correctamente.")
    else:
        img.show()
        print("⚠️ Impresora no disponible (simulación).")

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
    r = requests.post("https://api.mercadopago.com/checkout/preferences", headers=headers, json=data)
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
        resp = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}", headers=headers)

        if resp.status_code != 200:
            print(f"⚠️ Error al consultar pago {payment_id}: {resp.text}")
            return jsonify({"error": "no payment found"}), 400

        payment = resp.json()
        payer = payment.get("payer", {}).get("email", "Desconocido")
        amount = payment.get("transaction_amount", 0)
        status = payment.get("status", "unknown")

        print(f"💳 Estado del pago {payment_id}: {status}")

        # 🚫 Solo imprimir si está aprobado
        if status != "approved":
            print(f"⚠️ Pago {payment_id} con estado '{status}', no se imprime.")
            return jsonify({"status": status}), 200

        # 🎟 Clasificar tipo
        tipo_ticket = "SORTEO" if amount >= 13 else "IMPRESION"

        # --- 💡 IMPRESIÓN RETARDADA ---
        def delayed_print():
            try:
                if printer_ready:
                    print("🕒 Esperando 6s antes de imprimir...")
                else:
                    print("⚠️ Impresora no disponible para mensaje previo.")

                threading.Timer(6.0, print_payment_ticket, args=(payer, amount, status, tipo_ticket)).start()
            except Exception as e:
                print(f"⚠️ Error en impresión diferida: {e}")

        threading.Thread(target=delayed_print).start()
        print(f"🕐 Impresión programada para {payer} (${amount})")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"❌ Error procesando pago: {e}")
        return jsonify({"error": str(e)}), 500

    data = request.get_json(force=True)
    print("📩 Notificación de Mercado Pago recibida:", data)

    try:
        tipo = data.get("type") or data.get("topic")
        if tipo == "payment":
            payment_id = data["data"]["id"]
            headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
            resp = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}", headers=headers)
            payment = resp.json()

            payer = payment["payer"].get("email", "Desconocido")
            amount = payment.get("transaction_amount", 0)
            status = payment.get("status", "unknown")

            # Clasificar tipo de pago
            if amount >= 13:
                tipo = "SORTEO"
            else:
                tipo = "IMPRESION"

            # --- 💡 IMPRESIÓN RETARDADA + MENSAJE PREVIO ---
            def delayed_print():
                try:
                    if printer_ready:
                        # Mensaje previo
                        msg = [
                            "================================",
                            "⏳ Reconectate al LIVE 🎥",
                            "Volvé a TikTok...",
                            "Tu ticket se imprimirá pronto!",
                            "================================"
                        ]
                        print("🕒 Mensaje previo impreso, esperando 6s...")
                    else:
                        print("⚠️ Impresora no disponible para mensaje previo.")

                    # Esperar 6 segundos antes del ticket real
                    threading.Timer(6.0, print_payment_ticket, args=(payer, amount, status, tipo)).start()
                except Exception as e:
                    print(f"⚠️ Error en impresión diferida: {e}")

            # Lanzar impresión en segundo plano
            threading.Thread(target=delayed_print).start()
            print(f"🕐 Impresión programada para {payer} (${amount}) con delay de 6s")

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