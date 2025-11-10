import threading
import subprocess

def run_tiktok():
    subprocess.run(["python", "main2.py"])

def run_mercadopago():
    subprocess.run(["python", "mercadopago_listener.py"])

def run_gui():
    subprocess.run(["python", "gui.py"])

if __name__ == "__main__":
    threading.Thread(target=run_tiktok, daemon=True).start()
    threading.Thread(target=run_mercadopago, daemon=True).start()
    threading.Thread(target=run_gui, daemon=True).start()

    print("🚀 Todos los servicios están corriendo (TikTok + MercadoPago + GUI).")
    print("Presioná Ctrl+C para detener todo.")
    threading.Event().wait()  # mantiene vivo el programa principal
