# 📖 KI-ana OS - User Guide

**Complete guide to using KI-ana OS**

---

## 🎯 Overview

KI-ana OS is an intelligent operating system that:
- Understands natural language
- Manages hardware automatically
- Optimizes performance
- Speaks with you

---

## 🗣️ Talking to KI-ana

### **Text Commands**

```bash
python core/ai_engine/smart_main.py
```

**System Information:**
- "Zeige System Info"
- "Wie viel RAM habe ich?"
- "Welche CPU habe ich?"

**Optimization:**
- "Optimiere mein System"
- "Mein Computer ist langsam"
- "Mache meinen PC schneller"

**Hardware:**
- "Scanne Hardware"
- "Welche GPU habe ich?"
- "Zeige alle Geräte"

**Drivers:**
- "Welche Treiber brauche ich?"
- "Installiere Treiber"
- "Zeige Treiber Status"

---

### **Voice Commands**

```bash
python core/ai_engine/voice_brain.py
```

Same commands, just speak them!

**Tips:**
- Speak clearly
- Wait for the beep
- Natural language works best

---

## 🔧 Hardware Management

### **Automatic Detection**

KI-ana automatically detects:
- CPU (cores, speed, usage)
- GPU (NVIDIA, AMD, Intel)
- RAM (size, usage)
- Storage (disks, usage)
- Network devices

### **Driver Installation**

```python
"Installiere Treiber"
```

KI-ana will:
1. Detect your hardware
2. Find optimal drivers
3. Install safely
4. Verify installation

---

## 🏥 Health Monitoring

```bash
python examples/test_monitor.py
```

Check:
- System health score
- CPU/RAM/Disk status
- Temperature (if available)
- Performance metrics
- Warnings & recommendations

---

## ⚙️ Configuration

### **LLM Settings**

Edit `core/nlp/llm_client.py`:
```python
model = "llama3.1:8b"  # Change model
temperature = 0.7      # Creativity (0-1)
```

### **Voice Settings**

Edit `core/voice/speech_to_text.py`:
```python
model_size = "base"    # tiny, base, small, medium
language = "de"        # de, en, etc.
```

---

## 🐛 Troubleshooting

### **LLM not working**

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull llama3.1:8b

# Start Ollama
ollama serve
```

### **Voice not working**

```bash
# Install voice dependencies
pip install openai-whisper TTS sounddevice soundfile

# Test microphone
python -c "import sounddevice; print(sounddevice.query_devices())"
```

### **Permission errors**

```bash
# Add user to necessary groups
sudo usermod -aG audio,video $USER

# Reboot
sudo reboot
```

---

## 💡 Tips & Tricks

1. **Natural Language:** Don't use commands, just talk naturally
2. **Context:** KI-ana remembers your conversation
3. **Voice:** Works better in quiet environment
4. **Offline:** Most features work without internet
5. **Learning:** The more you use it, the better it gets

---

## 🚀 Advanced Usage

### **Python API**

```python
from core.ai_engine.smart_brain import get_smart_brain

# Initialize
brain = await get_smart_brain()

# Process command
result = await brain.process_command("Optimiere System")

# Voice interaction
from core.voice.voice_controller import VoiceController
voice = VoiceController()
await voice.initialize()
text = await voice.listen(duration=5)
```

---

## 📚 More Resources

- [API Documentation](API.md)
- [Architecture](ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)

---

**Questions? Ask KI-ana!** 😊
