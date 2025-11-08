from netapi.agent.agent import run_agent


def test_agent_returns_reply_for_ambiguous_prompt():
    res = run_agent("erklär mal", persona="friendly", lang="de-DE", conv_id="t1")
    assert res.get("ok") is True
    reply = (res.get("reply") or "").strip()
    assert reply != ""


def test_agent_dedupes_repeated_fallbacks_same_conv():
    conv = "loop-guard-1"
    # Very ambiguous message to trigger fallback behavior
    res1 = run_agent("Kannst du es kurz erklären?", persona="friendly", lang="de-DE", conv_id=conv)
    r1 = (res1.get("reply") or "").strip()
    # Same intent again should not yield the exact same fallback text
    res2 = run_agent("Kannst du es kurz erklären?", persona="friendly", lang="de-DE", conv_id=conv)
    r2 = (res2.get("reply") or "").strip()
    assert r1 != ""
    assert r2 != ""
    assert r1 != r2, "Agent should not return identical fallback twice in a row for same conversation"
