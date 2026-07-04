from splintercomclient.device import get_device_type, get_os_info


class TestGetOsInfo:
    def test_returns_string(self):
        result = get_os_info()
        assert isinstance(result, str)

    def test_max_30_chars(self):
        result = get_os_info()
        assert len(result) <= 30

    def test_not_empty(self):
        result = get_os_info()
        assert len(result) > 0


class TestGetDeviceType:
    def test_returns_string(self):
        result = get_device_type()
        assert isinstance(result, str)

    def test_max_30_chars(self):
        result = get_device_type()
        assert len(result) <= 30

    def test_not_empty(self):
        result = get_device_type()
        assert len(result) > 0

    def test_contains_arch_identifier(self):
        """Should contain a known architecture string."""
        result = get_device_type()
        known_archs = ["x86_64", "aarch64", "armv7l", "arm64", "AMD64"]
        assert any(arch in result for arch in known_archs), (
            f"Expected known architecture in '{result}'"
        )
