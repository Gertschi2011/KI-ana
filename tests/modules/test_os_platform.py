"""Tests for OS platform detection module."""

import pytest
import platform
from netapi.modules.os.platform import detector
from netapi.modules.os.platform import linux, windows, macos


def test_detect_platform():
    """Test platform detection."""
    plat = detector.detect_platform()
    assert plat in ["linux", "windows", "macos", "unknown"]
    
    # Should be cached on second call
    plat2 = detector.detect_platform()
    assert plat == plat2


def test_get_platform_info():
    """Test comprehensive platform info retrieval."""
    info = detector.get_platform_info()
    
    assert isinstance(info, dict)
    assert "os" in info
    assert "os_release" in info
    assert "machine" in info
    assert "python" in info
    assert "python_implementation" in info
    assert "cpu_count" in info
    assert "platform_details" in info
    
    # Validate types
    assert isinstance(info["os"], str)
    assert isinstance(info["platform_details"], dict)


def test_platform_info_caching():
    """Test that platform info is cached properly."""
    # Clear cache first
    detector.clear_cache()
    
    # First call
    info1 = detector.get_platform_info()
    
    # Second call should return cached value
    info2 = detector.get_platform_info()
    
    assert info1 == info2
    
    # Clear cache
    detector.clear_cache()
    
    # After clearing, should recompute
    info3 = detector.get_platform_info()
    assert info3 == info1  # Should still be equal, just not cached


def test_cpu_count():
    """Test CPU count detection."""
    cpu_count = detector._get_cpu_count()
    assert cpu_count is None or isinstance(cpu_count, int)
    if cpu_count is not None:
        assert cpu_count > 0


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-specific test")
def test_linux_distro_detection():
    """Test Linux distribution detection."""
    distro = linux.get_distro()
    assert isinstance(distro, str)
    assert len(distro) > 0


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-specific test")
def test_linux_system_info():
    """Test Linux system info."""
    info = linux.get_system_info()
    
    assert isinstance(info, dict)
    assert "distro" in info
    assert "kernel" in info
    assert "desktop" in info
    
    # Validate types
    assert isinstance(info["distro"], str)
    assert isinstance(info["kernel"], str)


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-specific test")
def test_linux_memory_info():
    """Test Linux memory info retrieval."""
    mem_info = linux.get_memory_info()
    
    if mem_info is not None:
        assert isinstance(mem_info, dict)
        # Should have at least one memory field
        assert any(key in mem_info for key in ["total", "available", "free"])


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-specific test")
def test_linux_gpu_info():
    """Test Linux GPU detection."""
    gpus = linux.get_gpu_info()
    
    assert isinstance(gpus, list)
    # GPU info is optional, but if present should be well-formed
    for gpu in gpus:
        assert isinstance(gpu, dict)
        assert "name" in gpu


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_windows_system_info():
    """Test Windows system info."""
    info = windows.get_system_info()
    
    assert isinstance(info, dict)
    assert "version" in info
    assert "edition" in info
    assert "build" in info


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_windows_memory_info():
    """Test Windows memory info."""
    mem_info = windows.get_memory_info()
    
    assert isinstance(mem_info, dict)
    # May be empty if ctypes fails, but should be a dict


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-specific test")
def test_macos_system_info():
    """Test macOS system info."""
    info = macos.get_system_info()
    
    assert isinstance(info, dict)
    assert "version" in info
    assert "version_name" in info
    assert "arch" in info
    assert "model" in info


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-specific test")
def test_macos_version_name():
    """Test macOS version name detection."""
    version_name = macos.get_version_name()
    assert isinstance(version_name, str)


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-specific test")
def test_macos_memory_info():
    """Test macOS memory info."""
    mem_info = macos.get_memory_info()
    
    if mem_info is not None:
        assert isinstance(mem_info, dict)
        assert "total" in mem_info


def test_platform_consistency():
    """Test that detected platform matches actual system."""
    detected = detector.detect_platform()
    actual_system = platform.system().lower()
    
    if actual_system == "linux":
        assert detected == "linux"
    elif actual_system == "windows":
        assert detected == "windows"
    elif actual_system == "darwin":
        assert detected == "macos"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
