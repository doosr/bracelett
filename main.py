import RPi.GPIO as GPIO
import requests
import smbus

import qrcode
import time
import argparse
from heartrate_monitor import HeartRateMonitor
import socketio
#==========================================================
#Led RGB
redPin = 17
greenPin = 27
bluePin = 22
#===========================================================
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM) 
GPIO.setup(redPin,GPIO.OUT)
GPIO.setup(greenPin,GPIO.OUT)
GPIO.setup(bluePin,GPIO.OUT)
#===========================================================
# Definition les couleur de la led
def turnOff():
    GPIO.output(redPin,GPIO.LOW)
    GPIO.output(greenPin,GPIO.LOW)
    GPIO.output(bluePin,GPIO.LOW)
    
def white():
    GPIO.output(redPin,GPIO.HIGH)
    GPIO.output(greenPin,GPIO.HIGH)
    GPIO.output(bluePin,GPIO.HIGH)
    
def red():
    GPIO.output(redPin,GPIO.HIGH)
    GPIO.output(greenPin,GPIO.LOW)
    GPIO.output(bluePin,GPIO.LOW)

def green():
    GPIO.output(redPin,GPIO.LOW)
    GPIO.output(greenPin,GPIO.HIGH)
    GPIO.output(bluePin,GPIO.LOW)
    
def blue():
    GPIO.output(redPin,GPIO.LOW)
    GPIO.output(greenPin,GPIO.LOW)
    GPIO.output(bluePin,GPIO.HIGH)
    
def yellow():
    GPIO.output(redPin,GPIO.HIGH)
    GPIO.output(greenPin,GPIO.HIGH)
    GPIO.output(bluePin,GPIO.LOW)
    
def purple():
    GPIO.output(redPin,GPIO.HIGH)
    GPIO.output(greenPin,GPIO.LOW)
    GPIO.output(bluePin,GPIO.HIGH)
    
def lightBlue():
    GPIO.output(redPin,GPIO.LOW)
    GPIO.output(greenPin,GPIO.HIGH)
    GPIO.output(bluePin,GPIO.HIGH)
def clignote():
    turnOff()
    time.sleep(0.3) #1second
    white()
    time.sleep(0.3)
    red()
    time.sleep(0.3)
    green()
    time.sleep(0.3)
    blue()
    time.sleep(0.3)
    yellow()
    time.sleep(0.3)
    purple()
    time.sleep(0.3)
    lightBlue()
    time.sleep(0.3)
    turnOff()
#=================================================================
# Configuration du capteur MLX90614
bus = smbus.SMBus(1)  
MLX90614_ADDR = 0x5A  

# Adresse du serveur Socket.IO
SOCKET_IO_SERVER_ADDRESS = "http://192.168.1.106:5000"

# Fonction pour lire la temperature du capteur MLX90614
def read_temperature():
    try:
         # Lecture de la tempÃ©rature ambiante (en degrÃ©s Celsius)
        ambient_temperature = bus.read_word_data(MLX90614_ADDR, 0x06)
        ambient_temperature = round(((ambient_temperature * 0.02) - 273.15), 2)
        # Lecture de la temperature de l'objet (en degres Celsius)
        bebe_temperature = bus.read_word_data(MLX90614_ADDR, 0x07)
        bebe_temperature = round(((bebe_temperature * 0.02) - 273.15), 2)
        return ambient_temperature,bebe_temperature
    except Exception as e:
        print("Erreur lors de la lecture du capteur MLX90614:", e)
        return None

# Fonction pour generer le code QR
def generate_qr_code(baby_id):
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(baby_id)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save("baby_qr_code.png")
        img.show()
        print("Code QR genere avec succes.")
    except Exception as e:
        print("Erreur lors de la generation du code QR:", e)

# Initialiser la connexion Socket.IO
sio = socketio.Client()

# Fonction pour se connecter au serveur Socket.IO
@sio.event
def connect():
    print("Connecte au serveur Socket.IO")

# Fonction pour envoyer les donnees de temperature au serveur
def update_temperature(baby_id, temperature,ambient):
    if temperature is not None and ambient is not None:
        data = {
            "baby_id": baby_id,
            "bebe_temperature": temperature,
            "ambient_temperature":ambient,
            
        }
        sio.emit('updateTemperature', data)
        print(f"Donnees de temperature {temperature} et temperature ambiant{ambient}envoyees au serveur pour le bebe ID: {baby_id}")

# Fonction pour envoyer les dernieres donnees de BPM et SpO2 au serveur Socket.IO
def send_heartbeat_data(baby_id, last_bpm, last_spo2):
    last_spo2 = int(last_spo2)  # Convert last_spo2 to an integer
    last_bpm = int(last_bpm)  # Convert last_spo2 to an integer

    data = {
        "baby_id": baby_id,
        "last_spo2": last_spo2,
        "last_bpm": last_bpm
    }
    sio.emit('updateHeartbeat', data)
    print(f"Dernieres donnees de BPM: {last_bpm} et SpO2: {last_spo2} envoyees au serveur pour le bebe ID: {baby_id}")
# Fonction pour recuperer l'ID du bebe e partir du serveur Node.js
def get_baby_id_from_server():
    while True:
        try:
            print("En attente de l'ID du bebe...")
            clignote()
            response = requests.get('http://192.168.1.106:5000/babyId')
            if response.status_code == 200:
                return response.json().get('babyId')
            else:
                print("echec de la recuperation de l'ID du bebe:", response.text)
                red()
                time.sleep(3)
                turnOff()
                time.sleep(5)  # Attendre 5 secondes avant de reessayer
        except Exception as e:
            print("Erreur lors de la recuperation de l'ID du bebe:", e)
            red()
            time.sleep(3)
            turnOff()
            time.sleep(5)  # Attendre 5 secondes avant de reessayer

# Obtention de l'ID du bebe
baby_id = get_baby_id_from_server()

# Verification si l'ID du bebe existe
while baby_id is None:
    
    print("Aucun ID de bebe trouve.")
    

    baby_id = get_baby_id_from_server()

print("ID de bebe existant trouve:", baby_id)
green()
time.sleep(3)
turnOff()

# Connexion au serveur Socket.IO
sio.connect(SOCKET_IO_SERVER_ADDRESS)

# Generation du code QR
generate_qr_code(baby_id)

# Initialisation du moniteur de frequence cardiaque
parser = argparse.ArgumentParser(description="Read and print data from MAX30102")
parser.add_argument("-r", "--raw", action="store_true", help="print raw data instead of calculation result")
parser.add_argument("-t", "--time", type=int, default=30, help="duration in seconds to read from sensor, default 30")
args = parser.parse_args()

print('Demarrage du capteur...')
hrm = HeartRateMonitor(print_raw=args.raw, print_result=(not args.raw))
hrm.start_sensor()
TEMPERATURE_INTERVAL = 1  # 30 minutes
HEARTBEAT_INTERVAL = 1  # 15 minutes
# ecouter l'evenement pour mettre a jour les intervalles de lecture
@sio.event
def update_intervals_event(data):
    global TEMPERATURE_INTERVAL, HEARTBEAT_INTERVAL
    temperature_interval = data.get('temperature_interval')
    heartbeat_interval = data.get('heartbeat_interval')
    
    if temperature_interval is not None:
        TEMPERATURE_INTERVAL = temperature_interval
    if heartbeat_interval is not None:
        HEARTBEAT_INTERVAL = heartbeat_interval
    
    print(f"Intervalles de lecture mis a jour : Temperature = {TEMPERATURE_INTERVAL} secondes, BPM/SpO2 = {HEARTBEAT_INTERVAL} secondes")

try:
    temperature_timer = time.time()
    heartbeat_timer = time.time()

    while True:

        # Lecture et envoi de la temperature toutes les TEMPERATURE_INTERVAL secondes
        current_time = time.time()
        if current_time - temperature_timer >= TEMPERATURE_INTERVAL:
            ambient, temperature = read_temperature()
            if temperature is not None and ambient is not None:
                update_temperature(baby_id, temperature, ambient)
                temperature_timer = current_time
                lightBlue()
                time.sleep(0.1)
                turnOff()

        # Lecture et envoi des donnees de SpO2 et BPM toutes les HEARTBEAT_INTERVAL secondes
        if current_time - heartbeat_timer >= HEARTBEAT_INTERVAL:
            last_bpm = hrm.bpm
            last_spo2 = hrm.spo2
            send_heartbeat_data(baby_id, last_bpm, last_spo2)
            heartbeat_timer = current_time
            yellow()
            time.sleep(0.1)
            turnOff()
            purple()
            time.sleep(0.1)
            turnOff()

        # Delai pour eviter une consommation excessive de ressources
        sio.sleep(0.1)  # Assurez-vous que la boucle s'arrete de maniere non bloquante pour traiter les evenements
        sio.on('updateIntervals', update_intervals_event)  # Ajout du gestionnaire d'evenements pour la mise a jour des intervalles

except KeyboardInterrupt:
    print('Interruption clavier detectee, arret du capteur...')
    hrm.stop_sensor()
    print('Capteur arrete!')
    sio.disconnect()
    lightBlue()
    time.sleep(1 )
    turnOff()