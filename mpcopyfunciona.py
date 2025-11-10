from flask import Flask, request, jsonify
import threading
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from escpos.printer import Usb
import os
import json
import hashlib
import random  # 👈 nuevo

# ====================================================
# CONFIGURACIÓN PRINCIPAL
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
        # Usa Arial directamente desde Windows
        font_path = "C:\\Windows\\Fonts\\arial.ttf"
        size = int(size * 3.5)  # 🔹 factor grande para compensar DPI
        return ImageFont.truetype(font_path, size)
    except Exception as e:
        print(f"⚠️ Error cargando fuente Arial: {e}")
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
# ÍCONOS ALEATORIOS
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

# ====================================================
# IMPRESIÓN DE TICKET
# ====================================================
def preparar_icono_para_ticket(icono_path, max_width=384):
    """Redimensiona y centra el icono para que se vea completo."""
    try:
        img = Image.open(icono_path).convert("L")
        w, h = img.size

        # Si es más grande que el ancho permitido, escalar proporcionalmente
        if w > max_width:
            new_h = int(h * (max_width / w))
            img = img.resize((max_width, new_h), Image.LANCZOS)
            w, h = img.size

        # Crear lienzo centrado de ancho fijo (blanco)
        canvas = Image.new("L", (512, h), 255)
        x_offset = (512 - w) // 2
        canvas.paste(img, (x_offset, 0))
        out_path = "icon_temp.bmp"
        canvas.save(out_path, format="BMP")
        return out_path

    except Exception as e:
        print(f"⚠️ Error ajustando icono: {e}")
        return icono_path

def print_payment_ticket(payer, amount, status, tipo):
    if tipo == "SORTEO":
        header = "🎟 SORTEO MXTECHNO 🎟"
        footer = "¡Estás participando del sorteo en vivo!"
    else:
        header = "$ PAGO RECIBIDO $"
        footer = "❤ Gracias por tu apoyo ❤"

    lines = [
        header,
        "-------------------------------",
        f"Mail: {payer}",
        f"Monto: ${amount}",
        "-------------------------------",
        footer,
    ]
    sizes = [34, 20, 26, 26, 24, 20, 28]

    img = render_centered_text(lines, sizes)
    img.save("mp_ticket.bmp")

    icono = elegir_icono_aleatorio()

    if printer_ready:
        p.text("\n")
        # Imprimir ícono arriba del ticket
        if icono and os.path.exists(icono):
            icono_ajustado = preparar_icono_para_ticket(icono)
            print(f"🎨 Ícono seleccionado: {os.path.basename(icono)}")
            p.image(icono_ajustado, high_density_horizontal=True, high_density_vertical=True)
        p.image("mp_ticket.bmp", high_density_horizontal=True, high_density_vertical=True)
        p.cut()
        print("🧾 Ticket impreso correctamente.")
    else:
        img.show()
        print("⚠️ Impresora no disponible (simulación).")

# ====================================================
# CREAR LINKS DE PAGO
# ====================================================
LINKS_FILE = "mp_links.json"

def crear_link_pago(titulo, descripcion, monto):
    data = {
        "items": [{
            "title": titulo,
            "description": descripcion,
            "quantity": 1,
            "currency_id": "ARS",
            "unit_price": monto
        }],
        "notification_url": f"{NGROK_URL}/mp/webhook",
        "external_reference": descripcion
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.post("https://api.mercadopago.com/checkout/preferences", headers=headers, json=data)
    r.raise_for_status()
    return r.json()["init_point"]

def generar_links_si_no_existen():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE) as f:
            links = json.load(f)
        print("🔗 Links cargados desde archivo local.")
        return links

    print("⚙️ Generando nuevos links de pago...")
    links = {
        "IMPRESION": crear_link_pago("Aparece en impresora!", "APARECER", 1),
        "SORTEO": crear_link_pago("Aparece en la impresora y participa del sorteo en vivo", "SORTEO", 1)
    }
    with open(LINKS_FILE, "w") as f:
        json.dump(links, f, indent=2)
    print("✅ Links generados y guardados en mp_links.json")
    return links

# ====================================================
# WEBHOOK
# ====================================================
@app.route("/mp/webhook", methods=["POST"])
def mp_webhook():
    data = request.get_json()
    print("📩 Notificación de Mercado Pago recibida:", data)

    try:
        if data.get("type") == "payment":
            payment_id = data["data"]["id"]
            headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
            resp = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}", headers=headers)
            payment = resp.json()

            payer = payment["payer"].get("email", "Desconocido")
            amount = payment.get("transaction_amount", 0)
            status = payment.get("status", "unknown")
            description = (payment.get("description") or "").upper()
            external_ref = (payment.get("external_reference") or "").upper()

            if "SORTEO" in (description + external_ref):
                tipo = "SORTEO"
                print(f"🎟️ Pago para SORTEO: {payer} - ${amount}")
                with open("participantes.txt", "a") as f:
                    f.write(f"{payer}\n")
            else:
                tipo = "IMPRESION"
                print(f"🖨️ Pago para IMPRESIÓN: {payer} - ${amount}")


            print_payment_ticket(payer, amount, status, tipo)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"❌ Error procesando pago: {e}")
        return jsonify({"error": str(e)}), 500

# ====================================================
# MAIN
# ====================================================
if __name__ == "__main__":
    links = generar_links_si_no_existen()
    print("🔗 LINKS DISPONIBLES:")
    for k, v in links.items():
        print(f"{k}: {v}")
    print("🚀 Esperando pagos...")
    app.run(host="0.0.0.0", port=8080)
