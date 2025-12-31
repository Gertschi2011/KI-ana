import importlib


def test_legacy_chat_router_imports():
    mod = importlib.import_module("netapi.modules.chat.router")
    assert getattr(mod, "router", None) is not None
