"""Unit tests for configuration management."""
import pytest

pytestmark = pytest.mark.unit


class TestSettingsConfiguration:
    """Test suite for Settings configuration."""

    def test_settings_loads_defaults(self):
        """Test that settings loads with default values."""
        from src.config import settings

        assert settings.erpnext_base_url == "http://localhost:8080"
        assert settings.erpnext_site_name == "erpnext.localhost"
        assert settings.otp_service_host == "0.0.0.0"
        assert settings.otp_service_port == 8001
        assert settings.otp_service_env == "development"
        assert settings.default_warehouse == "Stores - WH"
        assert settings.no_weekends is True
        assert settings.cutoff_time == "14:00"
        assert settings.timezone == "UTC"
        assert settings.lead_time_buffer_days == 1
        assert settings.delivery_model == "latest_acceptable"

    def test_settings_api_key_required(self):
        """Test that ERPNext API credentials exist."""
        from src.config import settings

        assert hasattr(settings, "erpnext_api_key")
        assert hasattr(settings, "erpnext_api_secret")

    def test_settings_business_rule_defaults(self):
        """Test business rule defaults are sensible."""
        from src.config import settings

        assert settings.no_weekends is True  # Sunday-Thursday workweek
        assert settings.lead_time_buffer_days >= 0
        assert settings.cutoff_time == "14:00"  # 2 PM
        assert settings.timezone == "UTC"

    def test_settings_deployment_environments(self):
        """Test that deployment environment can be configured."""
        from src.config import settings

        assert settings.otp_service_env in ["development", "production", "test"]

    def test_settings_warehouse_configuration(self):
        """Test warehouse-related settings."""
        from src.config import settings

        assert settings.default_warehouse is not None
        assert isinstance(settings.default_warehouse, str)
        assert len(settings.default_warehouse) > 0

    def test_settings_erpnext_connection_config(self):
        """Test ERPNext connection configuration exists."""
        from src.config import settings

        assert settings.erpnext_base_url.startswith("http")
        assert settings.erpnext_site_name
        assert settings.erpnext_api_key
        assert settings.erpnext_api_secret

    def test_settings_test_credentials_available(self):
        """Test that test credentials are configured."""
        from src.config import settings

        assert settings.run_integration in [True, False]
        assert settings.erpnext_test_username == "Administrator"
        assert settings.erpnext_test_password == "admin"

    def test_settings_delivery_model(self):
        """Test delivery model setting."""
        from src.config import settings

        assert hasattr(settings, "delivery_model")
        assert settings.delivery_model in ["latest_acceptable", "strict_fail", "no_early_delivery"]


class TestSettingsPydanticValidation:
    """Test Pydantic validation of Settings."""

    def test_settings_port_positive_integer(self):
        """Test that port must be positive integer."""
        from src.config import settings

        assert settings.otp_service_port > 0
        assert isinstance(settings.otp_service_port, int)

    def test_settings_lead_time_non_negative(self):
        """Test that lead time buffer is non-negative."""
        from src.config import settings

        assert settings.lead_time_buffer_days >= 0
        assert isinstance(settings.lead_time_buffer_days, int)

    def test_settings_string_fields_not_empty(self):
        """Test that important string fields are not empty."""
        from src.config import settings

        assert len(settings.erpnext_base_url) > 0
        assert len(settings.otp_service_host) > 0
        assert len(settings.cutoff_time) > 0
        assert len(settings.timezone) > 0


class TestGlobalSettingsInstance:
    """Test the global settings instance."""

    def test_settings_is_singleton_like(self):
        """Test that settings instance is globally accessible."""
        from src.config import settings as settings_import

        assert settings_import is not None
        # Should have all expected attributes
        assert hasattr(settings_import, "erpnext_base_url")
        assert hasattr(settings_import, "otp_service_port")

    def test_settings_immutable_behavior(self):
        """Test that settings values are consistent."""
        from src.config import settings

        # Access multiple times should return consistent values
        base_url_1 = settings.erpnext_base_url
        base_url_2 = settings.erpnext_base_url
        assert base_url_1 == base_url_2
