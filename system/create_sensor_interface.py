import json
import hashlib
from datetime import datetime
from pathlib import Path

sensor_interface = {
    "block_type": "sensor_interface",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "description": "Definiert die Sensor-Kommunikationsschnittstellen, die KI_ana 2.0 mit Subminds und Geräten verwenden darf.",
    "supported_inputs": [
        "microphone",
        "camera",
        "touchscreen",
        "keyboard",
        "temperature_sensor",
        "gps",
        "lidar",
        "ultrasound",
        "infrared",
        "accelerometer"
    ],
    "communication_protocols": [
        "USB",
        "I2C",
        "SPI",
        "Bluetooth",
        "Wi-Fi",
        "WebRTC",
        "HTTP API",
        "MQTT"
    ],
    "permissions_required": True,
    "sandbox_mode": True,
    "notes": "Alle physischen Ein- und Ausgaben benötigen eine eindeutige Genehmigung durch die Instanz des Eigentümers oder gesetzlich zuständige Stellen."
}

# Speicherort
block_json = json.dumps(sensor_interface, indent=2)
block_hash = hashlib.sha256(block_json.encode()).hexdigest()

sensor_file = Path.home() / "ki_ana" / "system" / "sensor_interface.json"
sensor_file.write_text(block_json)

print(f"Sensor Interface Block gespeichert: {sensor_file}")
print(f"SHA256 Hash: {block_hash}")
