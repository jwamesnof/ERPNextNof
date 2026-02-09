"""Configuration management for OTP Service."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ERPNext Configuration
    erpnext_base_url: str = "http://localhost:8080"
    erpnext_api_key: str
    erpnext_api_secret: str
    erpnext_site_name: str = "erpnext.localhost"

    # OTP Service Configuration
    otp_service_host: str = "0.0.0.0"
    otp_service_port: int = 8001
    otp_service_env: str = "development"

    # Test Configuration
    run_integration: bool = False
    erpnext_test_username: str = "Administrator"
    erpnext_test_password: str = "admin"

    # Business Rules Defaults
    default_warehouse: Optional[str] = "Stores - WH"
    no_weekends: bool = True
    cutoff_time: str = "14:00"
    timezone: str = "UTC"
    lead_time_buffer_days: int = 1
    processing_lead_time_days_default: int = 1
    delivery_model: str = "latest_acceptable"

    # Mock Supply Configuration (for testing/demo)
    use_mock_supply: bool = False
    mock_data_file: str = "data/mock_supply.json"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
