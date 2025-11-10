import socket
import json
import os
from escpos.printer import Usb

# ---------- Inicialización ----------
try:
    p = Usb(0x067b, 0x2305)
    print("🖨️ Impresora lista")
except Exception as e:
    print(f"⚠️ No se pudo conectar con la impresora: {e}")
    p = None

# ---------- Servidor ----------
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", 6000))
s.listen(5)
print("📡 Servidor de impresión escuchando en puerto 6000...")

def recv_all(conn):
    """Recibe todo el contenido enviado (soporta payloads grandes)."""
    buffer = b""
    while True:
        data = conn.recv(4096)
        if not data:
            break
        buffer += data
        if len(data) < 4096:
            break
    return buffer

while True:
    conn, addr = s.accept()
    try:
        data = recv_all(conn)
        if not data:
            conn.close()
            continue

        msg = json.loads(data.decode("utf-8"))
        tipo = msg.get("tipo", "texto")

        # ---------- TEXTO ----------
        if tipo == "texto":
            contenido = msg.get("contenido", "").strip()
            modo_directo = msg.get("modo_directo", False)

            if not contenido:
                print("⚠️ Mensaje vacío, no se imprime.")
            elif p:
                if modo_directo:
                    # Texto grande (para gifts)
                    p.set(align="center", double_height=True, double_width=True)
                else:
                    # Texto normal (likes / comentarios)
                    p.set(align="center", double_height=False, double_width=False)

                p.text(contenido + "\n")
                print(f"🖨️ Texto impreso: {contenido[:40]}...")
            else:
                print("⚠️ Impresora no inicializada.")

        # ---------- IMAGEN ----------
        elif tipo == "imagen":
            imagenes = msg.get("imagenes", [])
            if p and imagenes:
                for path in imagenes:
                    if os.path.exists(path):
                        try:
                            p.image(path, high_density_horizontal=True, high_density_vertical=True)
                            p.text("\n")
                        except Exception as e:
                            print(f"⚠️ Error al imprimir imagen {path}: {e}")
                    else:
                        print(f"⚠️ Imagen no encontrada: {path}")
                p.cut()  # <-- importante, fuerza impresión
                print(f"🖨️ Imágenes impresas correctamente ({len(imagenes)} archivo/s).")
            else:
                print("⚠️ No se encontraron imágenes o impresora no lista.")

        else:
            print(f"⚠️ Tipo de mensaje desconocido: {tipo}")

    except Exception as e:
        print(f"⚠️ Error al imprimir: {e}")
    finally:
        conn.close()
