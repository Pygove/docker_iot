from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    MessageHandler, filters, ConversationHandler
)
import logging, os, asyncio, ssl, aiomqtt, json

token = os.environ["TB_TOKEN"]

logging.basicConfig(
    format='%(asctime)s - TelegramBot - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOPICO = os.environ["TOPICO"]          # e6614c311b912b31
SERVIDOR = os.environ["SERVIDOR"]
MQTT_USR = os.environ["MQTT_USR"]
MQTT_PASS = os.environ["MQTT_PASS"]
PUERTO_MQTTS = int(os.environ["PUERTO_MQTTS"])

ESPERANDO_SETPOINT, ESPERANDO_PERIODO = range(2)

KB_PRINCIPAL = ReplyKeyboardMarkup(
    [
        ["Setpoint", "Periodo"],
        ["Destello", "Modo", "Relé"],
    ],
    resize_keyboard=True,
)

KB_MODO = ReplyKeyboardMarkup(
    [["AUTO", "MANUAL"], ["Volver"]],
    resize_keyboard=True,
)

KB_RELE = ReplyKeyboardMarkup(
    [["Activar", "Desactivar"], ["Volver"]],
    resize_keyboard=True,
)

KB_VOLVER = ReplyKeyboardMarkup(
    [["Volver"]],
    resize_keyboard=True,
)


async def publicar_mqtt(subtopico: str, payload: dict):
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    tls_context.load_default_certs()

    async with aiomqtt.Client(
        SERVIDOR,
        username=MQTT_USR,
        password=MQTT_PASS,
        port=PUERTO_MQTTS,
        tls_context=tls_context,
    ) as client:
        topico_completo = f"{TOPICO}/{subtopico}"
        await client.publish(topico_completo, json.dumps(payload), qos=1)
        logging.info(f"Publicado en {topico_completo}: {payload}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.from_user.first_name or ""
    logging.info(f"Conectado: {update.message.from_user.id} ({nombre})")
    await update.message.reply_text(
        f"Hola {nombre}. Bot de Gonzalo Veron \nSeleccioná una acción:",
        reply_markup=KB_PRINCIPAL,
    )
    return ConversationHandler.END


async def pedir_setpoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ingresá el nuevo setpoint en °C (ej: 25.5):",
        reply_markup=KB_VOLVER,
    )
    return ESPERANDO_SETPOINT


async def recibir_setpoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace(",", ".")
    try:
        valor = float(texto)
        await publicar_mqtt("setpoint", {"msg": valor})
        await update.message.reply_text(
            f"Setpoint actualizado a {valor} °C.",
            reply_markup=KB_PRINCIPAL,
        )
    except ValueError:
        await update.message.reply_text(
            "Valor inválido. Ingresá un número (ej: 25.5):",
            reply_markup=KB_VOLVER,
        )
        return ESPERANDO_SETPOINT
    return ConversationHandler.END



async def pedir_periodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ingresá el nuevo periodo en segundos (ej: 10):",
        reply_markup=KB_VOLVER,
    )
    return ESPERANDO_PERIODO


async def recibir_periodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    try:
        valor = int(texto)
        if valor <= 0:
            raise ValueError
        await publicar_mqtt("periodo", {"msg": valor})
        await update.message.reply_text(
            f"Periodo actualizado a {valor} segundos.",
            reply_markup=KB_PRINCIPAL,
        )
    except ValueError:
        await update.message.reply_text(
            "Valor inválido. Ingresá un entero mayor a 0 (ej: 10):",
            reply_markup=KB_VOLVER,
        )
        return ESPERANDO_PERIODO
    return ConversationHandler.END


async def destello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await publicar_mqtt("destello", {"msg": "destello"})
    await update.message.reply_text(
        "Destello activado",
        reply_markup=KB_PRINCIPAL,
    )


async def menu_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Seleccioná el modo de operación:",
        reply_markup=KB_MODO,
    )


async def recibir_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valor = update.message.text.strip()  # "AUTO" o "MANUAL"
    await publicar_mqtt("modo", {"msg": valor})
    await update.message.reply_text(
        f"Modo cambiado a {valor}.",
        reply_markup=KB_PRINCIPAL,
    )


async def menu_rele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Seleccioná el estado del relé:",
        reply_markup=KB_RELE,
    )


async def recibir_rele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    valor = "True" if texto == "Activar" else "False"
    await publicar_mqtt("rele", {"msg": valor})
    estado = "activado" if valor == "True" else "desactivado"
    await update.message.reply_text(
        f"Relé {estado}.",
        reply_markup=KB_PRINCIPAL,
    )


async def volver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Menú principal:",
        reply_markup=KB_PRINCIPAL,
    )
    return ConversationHandler.END


def main():
    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Setpoint$"), pedir_setpoint),
            MessageHandler(filters.Regex("^Periodo$"), pedir_periodo),
        ],
        states={
            ESPERANDO_SETPOINT: [
                MessageHandler(filters.Regex("^Volver$"), volver),
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_setpoint),
            ],
            ESPERANDO_PERIODO: [
                MessageHandler(filters.Regex("^Volver$"), volver),
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_periodo),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^Volver$"), volver),
        ],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    application.add_handler(MessageHandler(filters.Regex("^Destello$"), destello))
    application.add_handler(MessageHandler(filters.Regex("^Modo$"), menu_modo))
    application.add_handler(MessageHandler(filters.Regex("^Relé$"), menu_rele))
    application.add_handler(MessageHandler(filters.Regex("^(AUTO|MANUAL)$"), recibir_modo))
    application.add_handler(MessageHandler(filters.Regex("^(Activar|Desactivar)$"), recibir_rele))
    application.add_handler(MessageHandler(filters.Regex("^Volver$"), volver))

    application.run_polling()


if __name__ == "__main__":
    main()
