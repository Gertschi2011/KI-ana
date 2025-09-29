import types
import sys
import time
from pathlib import Path

import importlib
import pytest

# Module under test
router_mod_path = 'ki_ana.netapi.modules.chat.router'


def make_dummy_memory_store(return_value):
    mod = types.SimpleNamespace()
    def save_memory_entry(title: str, content: str, tags=None, url: str | None = None):
        return return_value
    mod.save_memory_entry = save_memory_entry
    return mod


def import_router_with_store(dummy_store):
    # Inject dummy store module under expected import path: netapi.memory_store (router uses from ... import memory_store)
    sys.modules['ki_ana.netapi.memory_store'] = dummy_store
    sys.modules['netapi.memory_store'] = dummy_store  # defensive alias if used elsewhere
    # Reload router to pick the injected module
    return importlib.import_module(router_mod_path)


@pytest.mark.parametrize('raw, expect_id, expect_file', [
    # list -> first dict
    ([{"id": "BLK_123", "file": "runtime/blocks/BLK_123.json", "url": "https://x"}], "BLK_123", "BLK_123.json"),
    # dict w/o id but file path
    ({"file": "runtime/blocks/BLK_999.json", "url": "u"}, "BLK_999", "BLK_999.json"),
    # string path
    ("runtime/blocks/BLK_42.json", "BLK_42", "BLK_42.json"),
])
def test_save_memory_normalizes_shapes(raw, expect_id, expect_file, monkeypatch):
    dummy_store = make_dummy_memory_store(raw)
    router = import_router_with_store(dummy_store)
    out = router.save_memory(title="t", content="c", tags=["x"], url="https://example.org")
    assert isinstance(out, dict)
    assert out.get('id') == expect_id
    assert out.get('file') == expect_file
    assert 'vision' in (out.get('tags') or [])
    assert out.get('url') == "https://example.org"


def test_save_memory_empty_list_fallback(monkeypatch):
    dummy_store = make_dummy_memory_store([])
    router = import_router_with_store(dummy_store)
    out = router.save_memory(title="t", content="c", tags=[], url=None)
    assert isinstance(out, dict)
    assert out.get('id', '').startswith('BLK_auto_')
    assert out.get('file').endswith('.json')


def test_coerce_to_dict_variants(monkeypatch):
    # Import current router without altering memory_store
    router = importlib.import_module(router_mod_path)
    cd = router._coerce_to_dict
    assert cd({"a": 1}) == {"a": 1}
    assert cd([{"a": 1}]) == {"a": 1}
    assert cd([]) == {}
    assert cd("runtime/blocks/BLK_7.json") == {"file": "runtime/blocks/BLK_7.json"}
    p = Path("runtime/blocks/BLK_8.json")
    assert cd(p) == {"file": str(p)}


def test_extract_block_id(monkeypatch):
    router = importlib.import_module(router_mod_path)
    ebid = router._extract_block_id
    assert ebid({"id": "BLK_1"}) == "BLK_1"
    assert ebid({"block_id": "BLK_2"}) == "BLK_2"
    assert ebid({"file": "runtime/blocks/BLK_3.json"}) == "BLK_3"
    assert ebid("runtime/blocks/BLK_4.json") == "BLK_4"
    # Fallback generates BLK_auto_*
    bid = ebid({})
    assert bid.startswith("BLK_auto_")
