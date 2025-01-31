import RPi.GPIO as GPIO
import requests
import smbus
import qrcode
import time
import argparse
from heartrate_monitor import HeartRateMonitor
import socketio
import signal
import sys
import subprocess
import os

#==========================================================
# Configuration du bouton de démarrage/arrêt
GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Variables globales pour le contrôle du script
process = None
script_running = False

def button_callback(channel):
    global process, script_running
    time.sleep(0.1)  # Debounce
    if GPIO.input(16):  # Si le bouton est relâché
        if not script_running:
            # Démarrer le script
            process = subprocess.Popen(["python3", "/home/pi/baby_monitor.py"])
            script_running = True
            print("Script démarré")
        else:
            # Arrêter complètement le script
            if process:
                os.kill(process.pid, signal.SIGTERM)
                process.wait()
                script_running = False
                print("Script arrêté")

# Ajouter un détecteur d'événement pour le bouton
GPIO.add_event_detect(16, GPIO.RISING, callback=button_callback, bouncetime=300)

#==========================================================
# Configuration LED RGB
redPin = 17
greenPin = 27
bluePin = 22

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM) 
GPIO.setup(redPin, GPIO.OUT)
GPIO.setup(greenPin, GPIO.OUT)
GPIO.setup(bluePin, GPIO.OUT)

#===========================================================
# Fonctions de contrôle LED RGB
def turnOff():
    GPIO.output(redPin, GPIO.LOW)
    GPIO.output(greenPin, GPIO.LOW)
    GPIO.output(bluePin, GPIO.LOW)
    
def white():
    GPIO.output(redPin, GPIO.HIGH)
    GPIO.output(greenPin, GPIO.HIGH)
    GPIO.output(bluePin, GPIO.HIGH)
    
def red():
    GPIO.output(redPin, GPIO.HIGH)
    GPIO.output(greenPin, GPIO.LOW)
    GPIO.output(bluePin, GPIO.LOW)

def green():
    GPIO.output(redPin, GPIO.LOW)
    GPIO.output(greenPin, GPIO.HIGH)
    GPIO.output(bluePin, GPIO.LOW)
    
def blue():
    GPIO.output(redPin, GPIO.LOW)
    GPIO.output(greenPin, GPIO.LOW)
    GPIO.output(bluePin, GPIO.HIGH)
    
def yellow():
    GPIO.output(redPin, GPIO.HIGH)
    GPIO.output(greenPin, GPIO.HIGH)
    GPIO.output(bluePin, GPIO.LOW)
    
def purple():
    GPIO.output(redPin, GPIO.HIGH)
    GPIO.output(greenPin, GPIO.LOW)
    GPIO.output(bluePin, GPIO.HIGH)
    
def lightBlue():
    GPIO.output(redPin, GPIO.LOW)
    GPIO.output(greenPin, GPIO.HIGH)
    GPIO.output(bluePin, GPIO.HIGH)

def clignote():
    turnOff()
    time.sleep(0.3)
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
SOCKET_IO_SERVER_ADDRESS = "http://192.168.1.101:5000"

# Fonction pour lire la température
def read_temperature():
    try:
        ambient_temperature = bus.read_word_data(MLX90614_ADDR, 0x06)
        ambient_temperature = round(((ambient_temperature * 0.02) - 273.15), 2)
        bebe_temperature = bus.read_word_data(MLX90614_ADDR, 0x07)
        bebe_temperature = round(((bebe_temperature * 0.02) - 273.15), 2)
        return ambient_temperature, bebe_temperature
    except Exception as e:
        print("Erreur lors de la lecture du capteur MLX90614:", e)
        return None, None

# Fonction pour générer le code QR
def generate_qr_code(baby_id):
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(baby_id)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save("baby_qr_code.png")
        print("Code QR généré avec succès.")
    except Exception as e:
        print("Erreur lors de la génération du code QR:", e)

# Initialisation Socket.IO
sio = socketio.Client()

@sio.event
def connect():
    print("Connecté au serveur Socket.IO")

def update_temperature(baby_id, temperature, ambient):
    if temperature is not None and ambient is not None:
        temperature += 2
        data = {
            "baby_id": baby_id,
            "bebe_temperature": temperature,
            "ambient_temperature": ambient,
        }
        sio.emit('updateTemperature', data)
        print(f"Données de température {temperature} et température ambiante {ambient} envoyées")

def filter_bpm(bpm, min_value=60, max_value=150):
    if min_value <= bpm <= max_value:
        return bpm
    else:
        print(f"Valeur de BPM {bpm} hors plage ({min_value}-{max_value}). Ignorée.")
        return None

def send_heartbeat_data(baby_id, last_bpm, last_spo2):
    last_spo2 = int(last_spo2)
    filtered_bpm = filter_bpm(last_bpm)
    if filtered_bpm is not None:
        data = {
            "baby_id": baby_id,
            "last_spo2": last_spo2,
            "last_bpm": filtered_bpm
        }
        sio.emit('updateHeartbeat', data)
        print(f"BPM: {filtered_bpm} et SpO2: {last_spo2} envoyés")

def get_baby_id_from_server():
    global script_running
    while script_running:
        try:
            print("En attente de l'ID du bébé...")
            clignote()
            response = requests.get('http://192.168.1.101:5000/babyId')
            if response.status_code == 200:
                return response.json().get('babyId')
            else:
                print("Échec de la récupération de l'ID:", response.text)
                red()
                time.sleep(3)
                turnOff()
                time.sleep(5)
        except Exception as e:
            print("Erreur lors de la récupération de l'ID:", e)
            red()
            time.sleep(3)
            turnOff()
            time.sleep(5)

def main():
    global script_running

    # Obtention de l'ID du bébé
    baby_id = get_baby_id_from_server()
    while baby_id is None and script_running:
        print("Aucun ID de bébé trouvé.")
        baby_id = get_baby_id_from_server()

    if baby_id:
        print("ID de bébé trouvé:", baby_id)
        green()
        time.sleep(3)
        turnOff()

        # Connexion Socket.IO
        sio.connect(SOCKET_IO_SERVER_ADDRESS)

        # Génération du code QR
        generate_qr_code(baby_id)

        # Configuration du moniteur cardiaque
        parser = argparse.ArgumentParser(description="Read data from MAX30102")
        parser.add_argument("-r", "--raw", action="store_true")
        parser.add_argument("-t", "--time", type=int, default=30)
        args = parser.parse_args()

        print('Démarrage du capteur...')
        hrm = HeartRateMonitor(print_raw=args.raw, print_result=(not args.raw))
        hrm.start_sensor()

        TEMPERATURE_INTERVAL = 1
        HEARTBEAT_INTERVAL = 1

        try:
            temperature_timer = time.time()
            heartbeat_timer = time.time()

            while script_running:
                current_time = time.time()

                # Lecture température
                if current_time - temperature_timer >= TEMPERATURE_INTERVAL:
                    ambient, temperature = read_temperature()
                    if temperature is not None and ambient is not None:
                        update_temperature(baby_id, temperature, ambient)
                        temperature_timer = current_time
                        lightBlue()
                        time.sleep(0.1)
                        turnOff()

                # Lecture SpO2 et BPM
                if current_time - heartbeat_timer >= HEARTBEAT_INTERVAL:
                    send_heartbeat_data(baby_id, hrm.bpm, hrm.spo2)
                    heartbeat_timer = current_time
                    yellow()
                    time.sleep(0.1)
                    turnOff()
                    purple()
                    time.sleep(0.1)
                    turnOff()

                time.sleep(0.1)

        except KeyboardInterrupt:
            print('Interruption détectée, arrêt du capteur...')
            script_running = False
            hrm.stop_sensor()
            sio.disconnect()
            lightBlue()
            time.sleep(1)
            turnOff()
            GPIO.cleanup()
            if process:
                os.kill(process.pid, signal.SIGTERM)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Erreur principale: {e}")
        GPIO.cleanup()
        if process:
            os.kill(process.pid, signal.SIGTERM)