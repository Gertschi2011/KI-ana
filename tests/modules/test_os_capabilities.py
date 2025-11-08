"""Tests for OS module capabilities system."""

import pytest
from netapi.modules.os.capabilities import allowed_caps


def test_allowed_caps_owner():
    """Test capabilities for owner role."""
    caps = allowed_caps("owner")
    
    assert isinstance(caps, list)
    assert len(caps) > 0
    
    # Owner should have all caps
    expected = ["fs.read", "web.get", "proc.run", "mem.store", "mem.recall", "notify.send"]
    for cap in expected:
        assert cap in caps


def test_allowed_caps_admin():
    """Test capabilities for admin role."""
    caps = allowed_caps("admin")
    
    assert isinstance(caps, list)
    assert len(caps) > 0
    
    # Admin should have most caps
    assert "fs.read" in caps
    assert "web.get" in caps


def test_allowed_caps_creator():
    """Test capabilities for creator role."""
    caps = allowed_caps("creator")
    
    assert isinstance(caps, list)
    # Creator might have limited caps
    assert "mem.store" in caps or "mem.recall" in caps


def test_allowed_caps_user():
    """Test capabilities for user role."""
    caps = allowed_caps("user")
    
    assert isinstance(caps, list)
    # User should have basic caps
    # Exact caps depend on implementation


def test_allowed_caps_case_insensitive():
    """Test that role matching is case-insensitive."""
    caps_lower = allowed_caps("owner")
    caps_upper = allowed_caps("OWNER")
    caps_mixed = allowed_caps("Owner")
    
    assert caps_lower == caps_upper == caps_mixed


def test_allowed_caps_unknown_role():
    """Test capabilities for unknown/invalid role."""
    caps = allowed_caps("unknown_role")
    
    assert isinstance(caps, list)
    # Should return minimal or empty caps for unknown roles


def test_allowed_caps_hierarchy():
    """Test that higher roles have equal or more capabilities than lower roles."""
    owner_caps = set(allowed_caps("owner"))
    admin_caps = set(allowed_caps("admin"))
    user_caps = set(allowed_caps("user"))
    
    # Owner should have at least as many caps as admin
    assert len(owner_caps) >= len(admin_caps)
    
    # Admin should have at least as many caps as user
    assert len(admin_caps) >= len(user_caps)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
