# CRUD2 — Envío de comandos MQTTS a nodos Raspberry Pi Pico

- **Login** reutilizando los mismos usuarios del CRUD anterior (tabla `usuarios` de la base `agenda`).
- **Tabla nueva** `raspi_disponibles` donde se guardan los nodos (nombre + tópico MQTT).
- **ABM de nodos** desde la interfaz: agregar y borrar nodos disponibles.
- **Envío de setpoint**: se elige el nodo de un dropdown y se publica en `<topico>/setpoint`.
- **Envío de destello**: se elige el nodo de un dropdown y se publica en `<topico>/destello`.
- Publicación vía **MQTTS (TLS)** con `paho-mqtt`, reutilizando el broker Mosquitto del proyecto.
