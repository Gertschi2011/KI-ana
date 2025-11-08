# 🔌 KI-ana OS - API Documentation

**Developer API Reference**

---

## 🧠 AI Engine

### **Smart Brain**

```python
from core.ai_engine.smart_brain import get_smart_brain

# Get singleton instance
brain = await get_smart_brain()

# Process command
result = await brain.process_command("user input")

# Result structure:
{
    "success": bool,
    "intent": {...},
    "result": {...},
    "response": str
}
```

---

## 🔌 Hardware

### **Hardware Scanner**

```python
from core.hardware.scanner import HardwareScanner

scanner = HardwareScanner()
hardware = await scanner.full_scan()

# Returns:
{
    "cpu": {...},
    "gpu": [...],
    "memory": {...},
    "storage": [...],
    "network": [...]
}
```

### **Hardware Optimizer**

```python
from core.hardware.optimizer import HardwareOptimizer

optimizer = HardwareOptimizer()
result = await optimizer.optimize(hardware_profile)
```

---

## 🎙️ Voice

### **Speech-to-Text**

```python
from core.voice.speech_to_text import get_stt

stt = await get_stt()
text = await stt.listen_and_transcribe(duration=5)
```

### **Text-to-Speech**

```python
from core.voice.text_to_speech import get_tts

tts = await get_tts()
await tts.speak("Hello World", play=True)
```

---

## 🔧 Drivers

### **Driver Manager**

```python
from system.drivers.manager import DriverManager

manager = DriverManager()

# Get recommendations
recommendations = await manager.get_driver_recommendations(profile)

# Auto-install
result = await manager.auto_install_drivers(profile, auto_confirm=False)
```

---

## 🏥 Monitoring

### **Health Monitor**

```python
from system.monitor.health_monitor import HealthMonitor

monitor = HealthMonitor()
report = await monitor.check_health()

# Returns health score, warnings, recommendations
```

---

## 📊 More Info

See code documentation in source files for complete API reference.
