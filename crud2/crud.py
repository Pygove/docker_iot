from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_mysqldb import MySQL
import os, logging, ssl
import paho.mqtt.publish as publish
import json
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

logging.basicConfig(format='%(asctime)s - CRUD2 - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config["MYSQL_USER"] = os.environ["MYSQL_USER"]
app.config["MYSQL_PASSWORD"] = os.environ["MYSQL_PASSWORD"]
app.config["MYSQL_DB"] = os.environ["MYSQL_DB"]
app.config["MYSQL_HOST"] = os.environ["MYSQL_HOST"]
app.config['PERMANENT_SESSION_LIFETIME'] = 600
mysql = MySQL(app)

MQTT_SERVER = os.environ["SERVIDOR"]
MQTT_PORT = int(os.environ["PUERTO_MQTTS"])
MQTT_USER = os.environ["MQTT_USR"]
MQTT_PASS = os.environ["MQTT_PASS"]


def publicar_mqtt(topico, payload):
    publish.single(
        topico,
        payload=json.dumps(payload),
        qos=1,
        hostname=MQTT_SERVER,
        port=MQTT_PORT,
        auth={"username": MQTT_USER, "password": MQTT_PASS},
        tls={"tls_version": ssl.PROTOCOL_TLS_CLIENT},
    )
    logging.info(f"Publicado en {topico}: {payload}")

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for('login'))
        g.usuario = session.get("user_id")
        return f(*args, **kwargs)
    return decorated_function


@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        if not request.form.get("usuario"):
            flash('El campo usuario es obligatorio')
            return redirect(url_for('registrar'))
        elif not request.form.get("password"):
            flash('El campo contraseña es obligatorio')
            return redirect(url_for('registrar'))

        passhash = generate_password_hash(request.form.get("password"), method='scrypt', salt_length=16)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO usuarios (usuario, hash) VALUES (%s,%s)",
                    (request.form.get("usuario"), passhash[17:]))
        if mysql.connection.affected_rows():
            flash('Se agregó un usuario')
            logging.info("se agregó un usuario")
        mysql.connection.commit()
        return redirect(url_for('index'))
    return render_template('registrar.html')


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not request.form.get("usuario"):
            flash('El campo usuario es obligatorio')
            return redirect(url_for('login'))
        elif not request.form.get("password"):
            flash('El campo contraseña es obligatorio')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario LIKE %s", (request.form.get("usuario"),))
        rows = cur.fetchone()
        if rows:
            if check_password_hash('scrypt:32768:8:1$' + rows[2], request.form.get("password")):
                session.permanent = True
                session["user_id"] = request.form.get("usuario")
                logging.info("se autenticó correctamente")
                return redirect(url_for('index'))
            else:
                flash('usuario o contraseña incorrecto')
                return redirect(url_for('login'))
        else:
            flash('usuario o contraseña incorrecto')
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route("/logout")
@require_login
def logout():
    session.clear()
    logging.info("el usuario {} cerró su sesión".format(g.usuario))
    return redirect(url_for('index'))

@app.route('/')
@require_login
def index():
    cur = mysql.connection.cursor()
    cur.execute('SELECT id, nombre, topico FROM raspi_disponibles')
    nodos = cur.fetchall()
    cur.close()
    return render_template('index.html', nodos=nodos)


@app.route('/agregar_nodo', methods=['POST'])
@require_login
def agregar_nodo():
    nombre = request.form.get('nombre')
    topico = request.form.get('topico')
    if not nombre or not topico:
        flash('Nombre y tópico son obligatorios')
        return redirect(url_for('index'))
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO raspi_disponibles (nombre, topico) VALUES (%s, %s)",
                    (nombre, topico))
        if mysql.connection.affected_rows():
            flash(f'Nodo "{nombre}" agregado')
            logging.info(f"se agregó el nodo {nombre} ({topico})")
        mysql.connection.commit()
    except Exception as e:
        logging.error(f"Error agregando nodo: {e}")
        flash('Error al agregar el nodo (¿tópico duplicado?)')
    return redirect(url_for('index'))


@app.route('/borrar_nodo/<id>', methods=['GET'])
@require_login
def borrar_nodo(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM raspi_disponibles WHERE id = %s", (id,))
        if mysql.connection.affected_rows():
            flash('Nodo eliminado')
            logging.info(f"se eliminó el nodo {id}")
        mysql.connection.commit()
    except Exception as e:
        logging.error(f"Error borrando nodo: {e}")
        flash('Error al eliminar el nodo')
    return redirect(url_for('index'))


@app.route('/enviar_setpoint', methods=['POST'])
@require_login
def enviar_setpoint():
    topico = request.form['nodo']
    setpoint = request.form['setpoint']
    try:
        valor = float(setpoint)
        publicar_mqtt(f"{topico}/setpoint", {"msg": valor})
        flash(f'Setpoint {valor} °C enviado a {topico}')
    except ValueError:
        flash('El setpoint debe ser un número')
    except Exception as e:
        logging.error(f"Error publicando setpoint: {e}")
        flash('Error al enviar el comando MQTT')
    return redirect(url_for('index'))


@app.route('/enviar_destello', methods=['POST'])
@require_login
def enviar_destello():
    topico = request.form['nodo']
    try:
        publicar_mqtt(f"{topico}/destello", {"msg": "destello"})
        flash(f'Orden de destello enviada a {topico}')
    except Exception as e:
        logging.error(f"Error publicando destello: {e}")
        flash('Error al enviar el comando MQTT')
    return redirect(url_for('index'))