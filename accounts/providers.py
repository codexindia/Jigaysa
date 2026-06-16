"""Pluggable auth provider interfaces (extension point for later phases).

OTP/SMS and social login are scaffolded but not implemented in Phase 1. These
abstract interfaces define the contract; swap the mock implementations for
Twilio / MSG91 / Google by pointing ``SMS_PROVIDER`` (settings) at another
class. Use ``get_sms_provider()`` to resolve the configured one.
"""

from abc import ABC, abstractmethod

from django.conf import settings
from django.utils.module_loading import import_string


class SMSProvider(ABC):
    """Sends OTP / transactional SMS. Implement for a real gateway later."""

    @abstractmethod
    def send_otp(self, phone: str, code: str) -> None:
        ...


class SocialProvider(ABC):
    """Verifies a social/SSO token and returns the user's profile claims."""

    @abstractmethod
    def verify_token(self, token: str) -> dict:
        ...


class ConsoleSMSProvider(SMSProvider):
    """Dev mock: 'sends' the OTP by printing it to the console."""

    def send_otp(self, phone: str, code: str) -> None:
        print(f"[ConsoleSMSProvider] OTP for {phone}: {code}")


def get_sms_provider() -> SMSProvider:
    """Resolve the SMS provider configured via settings.SMS_PROVIDER."""
    return import_string(settings.SMS_PROVIDER)()
