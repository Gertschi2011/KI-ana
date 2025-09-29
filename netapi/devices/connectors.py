from __future__ import annotations

"""
Connectors for device execution. Keep dependencies optional and fail soft.
Supported:
  - http: generic GET/POST/PUT/DELETE with JSON
  - webhook: simple POST JSON event
Skeleton:
  - mqtt: publish (only if paho-mqtt present)
"""

from typing import Dict, Any, Tuple, List
import os
import json

import requests


def _timeout() -> int:
    try:
        return int(os.getenv("DEVICE_HTTP_TIMEOUT", "8"))
    except Exception:
        return 8


def exec_http(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    cfg = device.get("config") or {}
    base = str(cfg.get("base_url") or cfg.get("url") or "").rstrip("/")
    headers = dict(cfg.get("headers") or {})
    if not base:
        return False, {"error": "missing_base_url"}

    # action mapping
    method = str(args.get("method") or "").upper()
    if not method:
        method = {
            "read": "GET",
            "write": "POST",
            "toggle": "POST",
            "notify": "POST",
        }.get(action, "POST")

    path = str(args.get("path") or cfg.get("path") or "").strip()
    url = base + (path if path.startswith("/") else ("/" + path)) if path else base
    payload = args.get("json")
    params = args.get("params")
    try:
        r = requests.request(method, url, headers=headers, json=payload, params=params, timeout=_timeout())
        data: Any
        try:
            data = r.json()
        except Exception:
            data = r.text
        return r.ok, {"status": r.status_code, "data": data}
    except Exception as e:
        return False, {"error": str(e)}


def exec_webhook(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    cfg = device.get("config") or {}
    url = str(cfg.get("url") or "").strip()
    headers = dict(cfg.get("headers") or {})
    if not url:
        return False, {"error": "missing_webhook_url"}
    payload = {
        "device": device.get("id"),
        "action": action,
        "args": args,
    }
    try:
        r = requests.post(url, headers=headers or {"Content-Type": "application/json"}, json=payload, timeout=_timeout())
        return r.ok, {"status": r.status_code, "data": (r.json() if r.headers.get("content-type"," ").startswith("application/json") else r.text)}
    except Exception as e:
        return False, {"error": str(e)}


def exec_mqtt(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except Exception:
        return False, {"error": "mqtt_not_available"}
    cfg = device.get("config") or {}
    host = cfg.get("host") or "localhost"
    port = int(cfg.get("port") or 1883)
    topic = args.get("topic") or cfg.get("topic")
    message = args.get("message")
    if topic is None:
        return False, {"error": "missing_topic"}
    client = mqtt.Client()
    try:
        if cfg.get("username"):
            client.username_pw_set(cfg.get("username"), cfg.get("password") or None)
        client.connect(host, port, keepalive=10)
        payload = message if isinstance(message, (str, bytes)) else json.dumps(message)
        res = client.publish(str(topic), payload=payload, qos=int(cfg.get("qos") or 0), retain=bool(cfg.get("retain") or False))
        res.wait_for_publish()
        client.disconnect()
        return True, {"published": True}
    except Exception as e:
        return False, {"error": str(e)}


def exec_device(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    if not bool(device.get("enabled", True)):
        return False, {"error": "device_disabled"}
    allowed = set((device.get("allowed_actions") or []))
    if allowed and action not in allowed:
        return False, {"error": "action_not_allowed", "allowed": sorted(allowed)}
    proto = (device.get("protocol") or device.get("kind") or "").lower()
    # Emergency stop gate (file): if KI_ROOT/emergency_stop exists, block non-read
    try:
        from pathlib import Path
        es_file = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))) / "emergency_stop"
        if es_file.exists() and action.lower() not in {"read", "status", "list"}:
            return False, {"error": "emergency_stop_active"}
    except Exception:
        pass

    if proto == "http":
        return exec_http(device, action, args)
    if proto == "webhook":
        return exec_webhook(device, action, args)
    if proto == "mqtt":
        return exec_mqtt(device, action, args)
    if proto in {"zigbee", "zigbee2mqtt"}:
        return exec_zigbee2mqtt(device, action, args)
    if proto == "homeassistant":
        return exec_homeassistant(device, action, args)
    if proto == "ssh":
        return exec_ssh(device, action, args)
    if proto == "serial":
        return exec_serial(device, action, args)
    if proto == "modbus_tcp":
        return exec_modbus_tcp(device, action, args)
    if proto == "opcua":
        return exec_opcua(device, action, args)
    if proto == "can":
        return exec_can(device, action, args)
    if proto == "ble":
        return exec_ble(device, action, args)
    if proto == "smtp":
        return exec_smtp(device, action, args)
    if proto == "imap":
        return exec_imap(device, action, args)
    if proto == "knx":
        return exec_knx(device, action, args)
    return False, {"error": "unsupported_protocol", "protocol": proto}


# ---------------- Specialized connectors ------------------------------------

def exec_homeassistant(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Call Home Assistant REST API services. Config:
    { "base_url": "http://ha.local:8123", "token": "<long-lived-token>" }
    Args:
      - action: domain.service (e.g., "light.toggle")
      - args: { "entity_id": "light.living_room", ... }
    """
    cfg = device.get("config") or {}
    base = str(cfg.get("base_url") or "").rstrip("/")
    token = cfg.get("token")
    if not base or not token:
        return False, {"error": "missing_base_or_token"}
    if "." not in action:
        return False, {"error": "action_must_be_domain_dot_service"}
    domain, service = action.split(".", 1)
    url = f"{base}/api/services/{domain}/{service}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type":"application/json"}
    try:
        r = requests.post(url, headers=headers, json=args or {}, timeout=_timeout())
        ok = r.ok
        try:
            data = r.json()
        except Exception:
            data = r.text
        return ok, {"status": r.status_code, "data": data}
    except Exception as e:
        return False, {"error": str(e)}


def exec_zigbee2mqtt(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Control Zigbee2MQTT via MQTT or HTTP. Config supports either:
      - MQTT: { protocol: "zigbee2mqtt", config: { host, port, username?, password?, topic_prefix: "zigbee2mqtt" } }
      - HTTP: { base_url: "http://z2m.local:8080/api" } (if frontend API enabled)
    Common args:
      { device: "lamp_1", payload: {"state":"ON"} }
    """
    cfg = device.get("config") or {}
    dev = args.get("device")
    payload = args.get("payload") or {}
    # Try HTTP first if base_url provided
    base = str(cfg.get("base_url") or "").rstrip("/")
    if base:
        try:
            r = requests.post(f"{base}/devices/{dev}/set", json=payload, timeout=_timeout())
            ok = r.ok
            try:
                data = r.json()
            except Exception:
                data = r.text
            return ok, {"status": r.status_code, "data": data}
        except Exception as e:
            return False, {"error": str(e)}
    # Fallback to MQTT
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except Exception:
        return False, {"error": "mqtt_not_available"}
    host = cfg.get("host") or "localhost"
    port = int(cfg.get("port") or 1883)
    prefix = cfg.get("topic_prefix") or "zigbee2mqtt"
    topic = f"{prefix}/{dev}/set"
    client = mqtt.Client()
    try:
        if cfg.get("username"):
            client.username_pw_set(cfg.get("username"), cfg.get("password") or None)
        client.connect(host, port, keepalive=10)
        import json as _json
        res = client.publish(topic, _json.dumps(payload), qos=int(cfg.get("qos") or 0), retain=False)
        res.wait_for_publish(); client.disconnect()
        return True, {"published": True}
    except Exception as e:
        return False, {"error": str(e)}


def exec_ssh(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Execute a command via SSH. Config: { host, port?, username, password? or key_file? }
    Action: "run"; Args: { cmd: "echo hi" }
    """
    try:
        import paramiko  # type: ignore
    except Exception:
        return False, {"error": "paramiko_not_available"}
    cfg = device.get("config") or {}
    host = cfg.get("host"); user = cfg.get("username")
    if not host or not user:
        return False, {"error": "missing_host_or_username"}
    port = int(cfg.get("port") or 22)
    cmd = (args.get("cmd") or "").strip()
    if not cmd:
        return False, {"error": "missing_cmd"}
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if cfg.get("password"):
            client.connect(host, port=port, username=user, password=cfg.get("password"), timeout=_timeout())
        else:
            pkey = None
            kf = cfg.get("key_file")
            if kf:
                pkey = paramiko.RSAKey.from_private_key_file(kf)
            client.connect(host, port=port, username=user, pkey=pkey, timeout=_timeout())
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode("utf-8", "ignore"); err = stderr.read().decode("utf-8", "ignore")
        rc = stdout.channel.recv_exit_status()
        return rc == 0, {"rc": rc, "out": out, "err": err}
    except Exception as e:
        return False, {"error": str(e)}
    finally:
        try: client.close()
        except Exception: pass


def exec_serial(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Serial device. Config: { port, baudrate=9600, timeout=1 }
    Actions: write {data}, read {size}
    """
    try:
        import serial  # type: ignore
    except Exception:
        return False, {"error": "pyserial_not_available"}
    cfg = device.get("config") or {}
    port = cfg.get("port"); baud = int(cfg.get("baudrate") or 9600)
    if not port:
        return False, {"error": "missing_port"}
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=float(cfg.get("timeout") or 1.0))
        if action == "write":
            data = args.get("data")
            if isinstance(data, str):
                data = data.encode("utf-8")
            ser.write(data or b""); ser.flush(); ser.close(); return True, {"written": len(data or b"")}
        if action == "read":
            size = int(args.get("size") or 128)
            data = ser.read(size); ser.close();
            try:
                txt = data.decode("utf-8")
            except Exception:
                txt = str(data)
            return True, {"data": txt}
        ser.close(); return False, {"error": "unsupported_action"}
    except Exception as e:
        return False, {"error": str(e)}


def exec_modbus_tcp(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Modbus TCP using pymodbus. Config: { host, port=502 }
    Actions: read_coils {address,count}; write_coil {address,value}
    """
    try:
        from pymodbus.client import ModbusTcpClient  # type: ignore
    except Exception:
        return False, {"error": "pymodbus_not_available"}
    cfg = device.get("config") or {}
    host = cfg.get("host"); port = int(cfg.get("port") or 502)
    if not host:
        return False, {"error": "missing_host"}
    client = ModbusTcpClient(host, port=port)
    try:
        if not client.connect():
            return False, {"error": "connect_failed"}
        if action == "read_coils":
            rr = client.read_coils(int(args.get("address") or 0), int(args.get("count") or 1))
            return (not rr.isError()), {"bits": getattr(rr, 'bits', [])}
        if action == "write_coil":
            rr = client.write_coil(int(args.get("address") or 0), bool(args.get("value")))
            return (not rr.isError()), {"ok": True}
        return False, {"error": "unsupported_action"}
    except Exception as e:
        return False, {"error": str(e)}
    finally:
        try: client.close()
        except Exception: pass


def exec_opcua(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """OPC UA read/write using opcua lib. Config: { url, username?, password? }
    Actions: read {node}, write {node,value}
    """
    try:
        from opcua import Client  # type: ignore
    except Exception:
        return False, {"error": "opcua_not_available"}
    cfg = device.get("config") or {}
    url = cfg.get("url")
    if not url:
        return False, {"error": "missing_url"}
    client = Client(url)
    try:
        if cfg.get("username"):
            client.set_user(cfg.get("username")); client.set_password(cfg.get("password") or "")
        client.connect()
        if action == "read":
            node = client.get_node(str(args.get("node")))
            val = node.get_value()
            return True, {"value": val}
        if action == "write":
            node = client.get_node(str(args.get("node")))
            node.set_value(args.get("value"))
            return True, {"ok": True}
        return False, {"error": "unsupported_action"}
    except Exception as e:
        return False, {"error": str(e)}
    finally:
        try: client.disconnect()
        except Exception: pass


def exec_can(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """CAN bus (python-can). Config: { interface: 'socketcan', channel: 'can0', bitrate? }
    Actions: send {arbitration_id,data(hex)}, recv {timeout_ms}
    """
    try:
        import can  # type: ignore
    except Exception:
        return False, {"error": "python_can_not_available"}
    cfg = device.get("config") or {}
    interface = cfg.get("interface") or "socketcan"
    channel = cfg.get("channel") or "can0"
    bitrate = cfg.get("bitrate")
    bus = None
    try:
        if interface == "socketcan":
            bus = can.interface.Bus(channel=channel, bustype="socketcan")
        else:
            # fallback for other backends (kvaser, pcant, etc.)
            bus = can.interface.Bus(channel=channel, bustype=interface, bitrate=bitrate)
        if action == "send":
            arb = int(args.get("arbitration_id"))
            data_hex = (args.get("data") or "").replace(" ", "")
            data = bytes.fromhex(data_hex)
            msg = can.Message(arbitration_id=arb, data=data, is_extended_id=bool(args.get("extended", False)))
            bus.send(msg)
            return True, {"sent": True}
        if action == "recv":
            timeout = (int(args.get("timeout_ms") or 1000)) / 1000.0
            msg = bus.recv(timeout)
            if not msg:
                return False, {"error": "timeout"}
            return True, {"arbitration_id": msg.arbitration_id, "data": msg.data.hex()}
        return False, {"error": "unsupported_action"}
    except Exception as e:
        return False, {"error": str(e)}
    finally:
        try: bus.shutdown()
        except Exception: pass


def exec_ble(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Bluetooth LE via bleak. Config: { address }
    Actions: read {uuid}, write {uuid,data(hex)}
    """
    try:
        import asyncio
        from bleak import BleakClient  # type: ignore
    except Exception:
        return False, {"error": "bleak_not_available"}
    cfg = device.get("config") or {}
    addr = cfg.get("address")
    if not addr:
        return False, {"error": "missing_address"}

    async def _run():
        async with BleakClient(addr) as client:
            if action == "read":
                data = await client.read_gatt_char(str(args.get("uuid")))
                return True, {"data": data.hex()}
            if action == "write":
                data_hex = (args.get("data") or "").replace(" ", "")
                await client.write_gatt_char(str(args.get("uuid")), bytes.fromhex(data_hex), response=True)
                return True, {"ok": True}
            return False, {"error": "unsupported_action"}

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except RuntimeError:
        # if no running loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as e:
        return False, {"error": str(e)}


def exec_smtp(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Send email via SMTP. Config: { host, port, username?, password?, tls? }
    Action: send; Args: { from, to: [..], subject, text }
    """
    import smtplib
    from email.mime.text import MIMEText
    cfg = device.get("config") or {}
    host = cfg.get("host"); port = int(cfg.get("port") or 587)
    if not host:
        return False, {"error": "missing_host"}
    msg = MIMEText(args.get("text") or "")
    msg["Subject"] = args.get("subject") or ""
    msg["From"] = args.get("from") or cfg.get("username") or ""
    msg["To"] = ", ".join(args.get("to") or [])
    try:
        s = smtplib.SMTP(host, port, timeout=_timeout())
        if bool(cfg.get("tls", True)):
            s.starttls()
        if cfg.get("username"):
            s.login(cfg.get("username"), cfg.get("password") or "")
        s.send_message(msg); s.quit()
        return True, {"sent": True}
    except Exception as e:
        return False, {"error": str(e)}


def exec_imap(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Read email via IMAP. Config: { host, port?, username, password, ssl? }
    Action: list_unseen; Args: { mailbox: 'INBOX', limit: 5 }
    """
    import imaplib
    import email
    from email.header import decode_header
    cfg = device.get("config") or {}
    host = cfg.get("host"); user = cfg.get("username"); pwd = cfg.get("password")
    if not host or not user or not pwd:
        return False, {"error": "missing_host_or_credentials"}
    ssl = bool(cfg.get("ssl", True))
    try:
        M = imaplib.IMAP4_SSL(host) if ssl else imaplib.IMAP4(host)
        M.login(user, pwd)
        mailbox = args.get("mailbox") or "INBOX"
        M.select(mailbox)
        status, data = M.search(None, '(UNSEEN)')
        ids = (data[0] or b"").split()
        out: List[Dict[str, Any]] = []
        for mid in ids[: int(args.get("limit") or 5)]:
            typ, msg_data = M.fetch(mid, '(RFC822)')
            if typ != 'OK':
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subj, enc = decode_header(msg.get('Subject') or '')[0]
            if isinstance(subj, bytes): subj = subj.decode(enc or 'utf-8', 'ignore')
            out.append({"id": mid.decode(), "subject": subj})
        M.logout()
        return True, {"items": out}
    except Exception as e:
        return False, {"error": str(e)}


def exec_knx(device: Dict[str, Any], action: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Placeholder for KNX. Prefer integrating via Home Assistant (protocol: homeassistant)
    or ensure xknx is installed and extend here. Currently returns not_available.
    """
    try:
        import xknx  # type: ignore  # noqa: F401
    except Exception:
        return False, {"error": "knx_not_available", "hint": "use protocol=homeassistant or install xknx and extend"}
    return False, {"error": "knx_handler_not_implemented", "hint": "extend connectors.exec_knx for your GA/DPT"}
