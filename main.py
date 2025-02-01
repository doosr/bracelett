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

# Nettoyage initial des GPIO
try:
    GPIO.cleanup()
except:
    pass

# Configuration GPIO avec warnings désactivés
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Variables globales
script_running = False
process = None

# Configuration des pins
GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Bouton
GPIO.setup(17, GPIO.OUT)  # LED Rouge
GPIO.setup(27, GPIO.OUT)  # LED Verte
GPIO.setup(22, GPIO.OUT)  # LED Bleue

# Pins LED RGB
redPin = 17
greenPin = 27
bluePin = 22

def button_callback(channel):
    global process, script_running
    time.sleep(0.1)  # Debounce
    if not GPIO.input(16):  # Si le bouton est pressé (logique inversée avec PUD_UP)
        if not script_running:
            # Démarrer le script
            process = subprocess.Popen(["python3", "/home/pi/baby_monitor.py"])
            script_running = True
            print("Script démarré")
        else:
            # Arrêter le script
            if process:
                try:
                    os.kill(process.pid, signal.SIGTERM)
                    process.wait()
                except:
                    pass
                script_running = False
                print("Script arrêté")

# Supprimer toute détection existante et ajouter la nouvelle
try:
    GPIO.remove_event_detect(16)
except:
    pass
GPIO.add_event_detect(16, GPIO.FALLING, callback=button_callback, bouncetime=300)

# Fonctions LED
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

# Configuration MLX90614
bus = smbus.SMBus(1)  
MLX90614_ADDR = 0x5A  

# Configuration serveur
SOCKET_IO_SERVER_ADDRESS = "http://192.168.1.106:5000"

# Fonctions capteur et communication
def read_temperature():
    try:
        ambient_temperature = bus.read_word_data(MLX90614_ADDR, 0x06)
        ambient_temperature = round(((ambient_temperature * 0.02) - 273.15), 2)
        bebe_temperature = bus.read_word_data(MLX90614_ADDR, 0x07)
        bebe_temperature = round(((bebe_temperature * 0.02) - 273.15), 2)
        return ambient_temperature, bebe_temperature
    except Exception as e:
        print("Erreur lecture température:", e)
        return None, None

def generate_qr_code(baby_id):
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(baby_id)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save("baby_qr_code.png")
        print("Code QR généré")
    except Exception as e:
        print("Erreur génération QR:", e)

# Socket.IO
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
        print(f"Température: {temperature}°C, Ambiante: {ambient}°C")

def filter_bpm(bpm, min_value=60, max_value=150):
    return bpm if min_value <= bpm <= max_value else None

def send_heartbeat_data(baby_id, last_bpm, last_spo2):
    try:
        last_spo2 = int(last_spo2)
        filtered_bpm = filter_bpm(last_bpm)
        if filtered_bpm is not None:
            data = {
                "baby_id": baby_id,
                "last_spo2": last_spo2,
                "last_bpm": filtered_bpm
            }
            sio.emit('updateHeartbeat', data)
            print(f"BPM: {filtered_bpm}, SpO2: {last_spo2}%")
    except Exception as e:
        print(f"Erreur envoi données cardiaques: {e}")

def get_baby_id_from_server():
    while script_running:
        try:
            print("Attente ID bébé...")
            clignote()
            response = requests.get('http://192.168.1.101:5000/babyId')
            if response.status_code == 200:
                return response.json().get('babyId')
            print("Échec récupération ID")
            red()
            time.sleep(3)
            turnOff()
            time.sleep(5)
        except Exception as e:
            print("Erreur récupération ID:", e)
            red()
            time.sleep(3)
            turnOff()
            time.sleep(5)
    return None

def main():
    global script_running
    script_running = True
    
    try:
        baby_id = get_baby_id_from_server()
        if not baby_id:
            print("Impossible d'obtenir l'ID bébé")
            return

        print("ID bébé:", baby_id)
        green()
        time.sleep(3)
        turnOff()

        sio.connect(SOCKET_IO_SERVER_ADDRESS)
        generate_qr_code(baby_id)

        parser = argparse.ArgumentParser(description="Lecture MAX30102")
        parser.add_argument("-r", "--raw", action="store_true")
        parser.add_argument("-t", "--time", type=int, default=30)
        args = parser.parse_args()

        print('Démarrage capteur...')
        hrm = HeartRateMonitor(print_raw=args.raw, print_result=(not args.raw))
        hrm.start_sensor()

        temperature_timer = time.time()
        heartbeat_timer = time.time()

        while script_running:
            current_time = time.time()

            if current_time - temperature_timer >= 1:
                ambient, temperature = read_temperature()
                if ambient is not None:
                    update_temperature(baby_id, temperature, ambient)
                    temperature_timer = current_time
                    lightBlue()
                    time.sleep(0.1)
                    turnOff()

            if current_time - heartbeat_timer >= 1:
                send_heartbeat_data(baby_id, hrm.bpm, hrm.spo2)
                heartbeat_timer = current_time
                yellow()
                time.sleep(0.1)
                turnOff()
                purple()
                time.sleep(0.1)
                turnOff()

            time.sleep(0.1)

    except Exception as e:
        print(f"Erreur: {e}")
    finally:
        script_running = False
        try:
            hrm.stop_sensor()
            sio.disconnect()
        except:
            pass
        lightBlue()
        time.sleep(1)
        turnOff()
        GPIO.cleanup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Arrêt demandé")
    except Exception as e:
        print(f"Erreur critique: {e}")
    finally:
        script_running = False
        try:
            GPIO.cleanup()
        except:
            pass