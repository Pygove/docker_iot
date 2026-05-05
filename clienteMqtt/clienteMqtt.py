import asyncio, ssl, logging, os
import aiomqtt

logging.basicConfig(
    format='%(asctime)s - %(taskName)s - %(levelname)s: %(message)s',
    level=logging.INFO,
    datefmt='%d/%m/%Y %H:%M:%S %z'
)


async def incrementar_contador(estado):
    while True:
        await asyncio.sleep(3)
        estado['contador'] += 1
        logging.info(f"Contador incrementado: {estado['contador']}")


async def publicar_contador(client, topico_pub, estado):
    while True:
        await asyncio.sleep(5)
        await client.publish(topico_pub, payload=str(estado['contador']))
        logging.info(f"Publicado contador: {estado['contador']} en {topico_pub}")


async def procesar_mensajes(cola):
    while True:
        message = await cola.get()
        logging.info(f"{message.topic}: {message.payload.decode('utf-8')}")


async def distribuidor(client, topico_1, cola_1, topico_2, cola_2):
    async for message in client.messages:
        if message.topic.matches(topico_1):
            await cola_1.put(message)
        elif message.topic.matches(topico_2):
            await cola_2.put(message)


async def main():
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    tls_context.load_default_certs()

    servidor = os.environ['SERVIDOR']
    puerto = int(os.environ['PUERTO'])
    topico_1 = os.environ['TOPICO_1']
    topico_2 = os.environ['TOPICO_2']
    topico_pub = os.environ['TOPICO_PUB']

    estado = {'contador': 0}

    async with aiomqtt.Client(servidor, port=puerto, tls_context=tls_context) as client:
        await client.subscribe(topico_1)
        await client.subscribe(topico_2)
        logging.info(f"Conectado a {servidor}:{puerto}")
        logging.info(f"Suscripto a {topico_1} y {topico_2}")
        logging.info(f"Publicando contador en {topico_pub}")

        cola_1 = asyncio.Queue()
        cola_2 = asyncio.Queue()

        tarea_distribuidor = asyncio.create_task(distribuidor(client, topico_1, cola_1, topico_2, cola_2), name="distribuidor")
        tarea_mensajes_1 = asyncio.create_task(procesar_mensajes(cola_1), name="procesar_mensajes_1")
        tarea_mensajes_2 = asyncio.create_task(procesar_mensajes(cola_2), name="procesar_mensajes_2")
        tarea_contador = asyncio.create_task(incrementar_contador(estado), name="incrementar_contador")
        tarea_publicar = asyncio.create_task(publicar_contador(client, topico_pub, estado), name="publicar_contador")

        await asyncio.gather(tarea_distribuidor, tarea_mensajes_1, tarea_mensajes_2, tarea_contador, tarea_publicar)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Se produjo una interrupción.")
        print("\nPrograma terminado")
