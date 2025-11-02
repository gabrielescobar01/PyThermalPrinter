import pyttsx3
import asyncio
from escpos.printer import Usb
from TikTokLive import TikTokLiveClient
from TikTokLive.events import GiftEvent, CommentEvent, FollowEvent, LikeEvent
import requests
from PIL import Image, ImageDraw, ImageFont



# Initialize printer
p = Usb(0x067b, 0x2305, 0, profile="TM-T88III")

# Initialize TikTokLive client
client = TikTokLiveClient(unique_id="@eugeniaruiz2024")

# Diccionario para rastrear los diamantes por usuario y temporizador
user_streaks = {}
user_timers = {}

def remove_black_background(img):
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for item in data:
        if item[:3] == (0, 0, 0):
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

def create_rounded_profile_image(profile_img):
    size = (400, 400)
    profile_img = profile_img.resize(size, Image.LANCZOS)

    # Crear una máscara para la imagen redonda
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)

    # Aplicar la máscara a la imagen de perfil
    rounded_profile = Image.new('RGBA', size)
    rounded_profile.paste(profile_img, (0, 0), mask)

    # Añadir borde negro de 2px
    border_size = 2
    border = Image.new('L', (size[0] + border_size * 2, size[1] + border_size * 2), 0)
    draw = ImageDraw.Draw(border)
    draw.ellipse((0, 0, border.width, border.height), fill=255)

    rounded_profile_with_border = Image.new('RGBA', (border.width, border.height))
    rounded_profile_with_border.paste('black', (0, 0), border)
    rounded_profile_with_border.paste(rounded_profile, (border_size, border_size), rounded_profile)

    return rounded_profile_with_border

def create_combined_image(profile_img, gift_img, text, streak_text):
    profile_img = create_rounded_profile_image(profile_img)  # Hacer perfil redondo
    gift_img = gift_img.resize((50, 50), Image.LANCZOS)  # Cambiar tamaño del icono del gift

    # Definir el ancho total
    combined_width = max(profile_img.width, 512)
    combined_height = profile_img.height + 150  # Altura total

    combined_img = Image.new('RGBA', (combined_width, combined_height), (255, 255, 255, 255))

    # Pegar la imagen de perfil centrada
    profile_x = (combined_width - profile_img.width) // 2
    combined_img.paste(profile_img, (profile_x, 0))

    # Calcular el tamaño del texto y dividir en líneas si es necesario
    draw = ImageDraw.Draw(combined_img)
    try:
        font = ImageFont.truetype("impact.ttf", 30)
    except IOError:
        font = ImageFont.load_default()

    # Dividir el texto en líneas
    lines = []
    max_text_width = combined_width - (gift_img.width * 2 + 40)  # Ancho máximo disponible
    words = text.split()
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        test_width = draw.textbbox((0, 0), test_line, font=font)[2]
        if test_width <= max_text_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)  # Añadir la última línea

    # Dibujar el texto en la imagen
    y_text = profile_img.height + 15  # Padding de 15px
    for line in lines:
        draw.text(((combined_width - draw.textbbox((0, 0), line, font=font)[2]) // 2, y_text), line, fill="black", font=font)
        y_text += draw.textbbox((0, 0), line, font=font)[3]  # Ajustar la posición vertical

    # Pegar el icono del gift a la izquierda
    combined_img.paste(gift_img, (50, profile_img.height + 15), gift_img)

    # Pegar el icono del gift a la derecha
    combined_img.paste(gift_img, (combined_width - 50 - gift_img.width, profile_img.height + 15), gift_img)

    # Dibujar el streak de diamantes
    streak_y = y_text + 10  # Espaciado entre el texto y el streak
    draw.text(((combined_width - draw.textbbox((0, 0), streak_text, font=font)[2]) // 2, streak_y), streak_text, fill="black", font=font)

    return combined_img

async def handle_gift_end(user_id):
    await asyncio.sleep(5)
    if user_id in user_streaks:
        streak = user_streaks[user_id]['streak']

        try:
            response = requests.get(user_streaks[user_id]['gift_image'])
            response.raise_for_status()

            with Image.open(requests.get(user_streaks[user_id]['gift_image'], stream=True).raw) as gift_img:
                gift_img = remove_black_background(gift_img)

                if user_streaks[user_id]['profile_picture']:
                    profile_picture_url = user_streaks[user_id]['profile_picture']
                    profile_picture_response = requests.get(profile_picture_url, stream=True)
                    profile_picture_response.raise_for_status()

                    with Image.open(profile_picture_response.raw) as profile_img:
                        text = f"{user_id} sent \"{user_streaks[user_id]['gift_name']}\""
                        streak_text = f"Racha de: {streak} diamantes"

                        combined_img = create_combined_image(profile_img, gift_img, text, streak_text)
                        p.set(align="center")
                        p.image(combined_img)

        except Exception as e:
            print(f"Error handling gift: {e}")

        del user_streaks[user_id]

# Inicializar el motor de texto a voz
engine = pyttsx3.init()

@client.on(FollowEvent)
async def on_follow(event):
    username = event.user.unique_id
    message = f"¡Gracias por tu Follow: {username}!"
    print(message)

    # Reproducir la voz
    engine.say(message)
    engine.runAndWait()



@client.on(GiftEvent)
async def on_gift(event: GiftEvent):
    try:
        user_id = event.user.unique_id
        diamonds = event.gift.diamond_count


        if user_id in user_streaks:
            user_streaks[user_id]['streak'] += diamonds
        else:
            user_streaks[user_id] = {
                'streak': diamonds,
                'gift_name': event.gift.name,
                'gift_image': event.gift.image.url_list[0],
                'profile_picture': event.user.avatar_thumb.url_list[0] if event.user.avatar_thumb.url_list else None
            }

        if user_id in user_timers:
            user_timers[user_id].cancel()

        user_timers[user_id] = asyncio.create_task(handle_gift_end(user_id))

    except Exception as e:
        print(f"Error: {e}")


last_comment = {"user_id": None, "comment_text": None}

@client.on(CommentEvent)
async def on_comment(event: CommentEvent):
    global last_comment
    try:
        with open(CONFIG_FILE, "r") as f:
            current_config = json.load(f)
    except Exception as e:
        print(f"⚠️ Error leyendo config.json en tiempo real: {e}")
        current_config = config  # fallback

    if not current_config.get("gifts", True):
        print("🎁 Gifts desactivados por configuración.")
        return

        user_id = event.user.unique_id
        comment_text = event.comment

        # Comprobar si el comentario es idéntico al último
    if last_comment["user_id"] == user_id and last_comment["comment_text"] == comment_text:
            return  # Omitir si es un duplicado

        # Actualizar el último comentario recibido
    last_comment = {"user_id": user_id, "comment_text": comment_text}

    # Aquí puedes decidir cómo manejar los comentarios. Por ejemplo, imprimirlos.
    print(f"{user_id}: {comment_text}")
    p.set(align="center", bold=True) # Centrar y poner en negrita el texto

        # También puedes imprimirlos en la impresora si es necesario
        p.set(align="center", bold=True, width=2, height=2)  # Cambia 'width' y 'height' según el tamaño deseado
        p.text(f"{user_id}:\n")
        p.set(align="center", bold=False, width=1, height=1)  # Restablece el tamaño de texto al valor normal si es necesario
        p.text(f"{comment_text}\n")
        # Imprime la línea de separación
        p.text("-" * 32 + "\n")  # Línea de guiones (ajusta el número para el ancho de tu impresora)
        p.set(align="left")  # Reinicia alineación y negrita

    except Exception as e:
        print(f"Error handling comment: {e}")


# Inicializar el motor de texto a voz
engine = pyttsx3.init()


@client.on(LikeEvent)
async def on_like(event):
    username = event.user.unique_id
    message = f"{username} ha dado un like!"
    print(message)

    # Reproducir la voz
    engine.say(message)
    engine.runAndWait()

if __name__ == '__main__':
    print('Running...')
    client.run()