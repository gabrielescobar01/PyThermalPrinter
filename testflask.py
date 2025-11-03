from flask import Flask, render_template_string

app = Flask(__name__)

@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Donar a MXTECHNO</title>
<style>
  body { font-family: 'Helvetica Neue', Arial; text-align: center; margin-top: 50px; }
  .suggestions button {
    background: #eee; border: none; padding: 10px 20px; border-radius: 20px;
    margin: 5px; cursor: pointer; font-size: 16px;
  }
  #descripcion {
    font-size: 16px; color: #333; margin-top: 10px;
    transition: opacity 0.3s ease; opacity: 0; min-height: 24px;
  }
</style>
</head>
<body>
  <h2>Seleccioná un monto</h2>
  <div class="suggestions">
    <button type="button" onclick="setMonto(300)">$300</button>
    <button type="button" onclick="setMonto(500)">$500</button>
    <button type="button" onclick="setMonto(1000)">$1000</button>
    <button type="button" onclick="setMonto(1500)">$1500</button>
  </div>

  <p id="descripcion"></p>
  <input type="hidden" id="descripcion-input">

  <script>
  function setMonto(valor) {
    console.log("Botón presionado:", valor); // 👈 debug visual
    const descripcion = document.getElementById('descripcion');
    const inputHidden = document.getElementById('descripcion-input');
    let texto = "";

    if (valor === 300) texto = "🖨️ Aparecés en la impresora con tu nombre.";
    if (valor === 500) texto = "💬 Aparecés en la impresora + tu mensaje en vivo.";
    if (valor === 1000) texto = "🎵 Tu nombre + sonido especial en la transmisión.";
    if (valor === 1500) texto = "🎟️ Aparecés en la impresora y participás del sorteo VIP!";

    descripcion.style.opacity = 0;
    setTimeout(() => {
      descripcion.textContent = texto;
      inputHidden.value = texto;
      descripcion.style.opacity = 1;
    }, 100);
  }
  </script>
</body>
</html>
""")

if __name__ == "__main__":
    app.run(port=8080)
