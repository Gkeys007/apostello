import types
from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone
from tests.conftest import twilio_vcr

from apostello import logs, models
from site_config.models import SiteConfiguration

today = timezone.localdate()


class MockMsg:
    def __init__(self, from_):
        self.sid = "a" * 34
        self.body = "test message"
        self.from_ = from_
        self.to = settings.to = "447922537999"
        self.date_created = timezone.now()
        self.date_sent = timezone.now()
        self.status = "unknown"


@pytest.mark.django_db
class TestImportLogs:
    """
    Test log imports.

    Unable to test this properly as Twilio raises an exception when test
    credentials are used.
    """

    @twilio_vcr
    def test_all_incoming(self):
        logs.check_incoming_log()

    @twilio_vcr
    def test_all_outgoing(self):
        logs.check_outgoing_log()


@pytest.mark.django_db
class TestExpiry:
    """
    Test log imports with expiry date.
    """

    @twilio_vcr
    def test_import_incoming_expiry_date(self):
        config = SiteConfiguration.get_solo()
        config.sms_expiration_date = today
        config.save()
        logs.check_incoming_log()
        assert models.SmsInbound.objects.filter(time_received__lt=today).count() == 0

    @twilio_vcr
    def test_import_outgoing_expiry_date(self):
        config = SiteConfiguration.get_solo()
        config.sms_expiration_date = today
        config.save()
        logs.check_outgoing_log()
        assert models.SmsOutbound.objects.filter(time_sent__lt=today).count() == 0

    @twilio_vcr
    def test_cleanup_expiry_date(self):
        config = SiteConfiguration.get_solo()
        config.sms_expiration_date = None
        config.save()
        logs.check_incoming_log()
        logs.check_outgoing_log()
        num_sms = models.SmsInbound.objects.count() + models.SmsOutbound.objects.count()
        logs.cleanup_expired_sms()
        assert num_sms > 0
        assert models.SmsInbound.objects.count() + models.SmsOutbound.objects.count() == num_sms
        config = SiteConfiguration.get_solo()
        config.sms_expiration_date = today + timedelta(days=1)
        config.save()
        logs.cleanup_expired_sms()
        assert models.SmsInbound.objects.count() + models.SmsOutbound.objects.count() == 0

    @twilio_vcr
    def test_import_incoming_rolling(self):
        config = SiteConfiguration.get_solo()
        config.sms_expiration_date = None
        config.sms_rolling_expiration_days = 0
        config.save()
        logs.check_incoming_log()
        assert models.SmsInbound.objects.filter(time_received__lt=today).count() == 0

    @twilio_vcr
    def test_import_outgoing_rolling(self):
        config = SiteConfiguration.get_solo()
        config.sms_expiration_date = None
        config.sms_rolling_expiration_days = 0
        config.save()
        logs.check_outgoing_log()
        assert models.SmsOutbound.objects.filter(time_sent__lt=today).count() == 0

    @twilio_vcr
    def test_cleanup_rolling(self):
        config = SiteConfiguration.get_solo()
        config.sms_expiration_date = None
        config.sms_rolling_expiration_days = None
        config.save()
        logs.check_incoming_log()
        logs.check_outgoing_log()
        num_sms = models.SmsInbound.objects.count() + models.SmsOutbound.objects.count()
        logs.cleanup_expired_sms()
        assert num_sms > 0
        assert models.SmsInbound.objects.count() + models.SmsOutbound.objects.count() == num_sms
        config = SiteConfiguration.get_solo()
        config.sms_rolling_expiration_days = 0
        config.save()
        logs.cleanup_expired_sms()
        assert models.SmsInbound.objects.count() + models.SmsOutbound.objects.count() == 0

    def test_cleanup(self):
        # setup
        config = SiteConfiguration.get_solo()
        config.sms_rolling_expiration_days = None
        config.sms_expiration_date = today - timedelta(days=100)
        config.save()
        sms = models.SmsInbound.objects.create(
            content="test message",
            time_received=timezone.now() - timedelta(50),
            sender_name="John Calvin",
            sender_num="+447927401749",
            matched_keyword="test",
            sid="12345",
        )
        sms.save()
        assert models.SmsInbound.objects.count() == 1  # we have one sms
        logs.cleanup_expired_sms()
        assert models.SmsInbound.objects.count() == 1  # cleanup should leave it untouched
        config.sms_rolling_expiration_days = 50
        config.save()
        logs.cleanup_expired_sms()
        assert models.SmsInbound.objects.count() == 1  # cleanup should leave it untouched
        config.sms_rolling_expiration_days = 49
        config.save()
        logs.cleanup_expired_sms()
        assert models.SmsInbound.objects.count() == 0  # cleanup should remove sms


@pytest.mark.django_db
class TestSmsHandlers:
    def test_handle_incoming_sms(self):
        config = SiteConfiguration.get_solo()
        config.sms_expiration_date = None
        config.save()

        msg = MockMsg("447922537999")
        logs.handle_incoming_sms(msg)
        assert models.SmsInbound.objects.all()[0].content == msg.body
        assert models.SmsInbound.objects.count() == 1

        cnp = logs.handle_incoming_sms(msg)
        assert models.SmsInbound.objects.count() == 1

    def test_handle_outgoing_sms(self):
        config = SiteConfiguration.get_solo()
        config.sms_expiration_date = None
        config.save()

        msg = MockMsg("447932537999")
        cnp = logs.handle_outgoing_sms(msg)
        assert models.SmsOutbound.objects.all()[0].content == msg.body
        assert models.SmsOutbound.objects.count() == 1

        logs.handle_outgoing_sms(msg)
        assert models.SmsOutbound.objects.count() == 1


@pytest.mark.django_db
class TestFetchingClients:
    @twilio_vcr
    def test_fetch_all_in(self):
        i = logs.fetch_generator("in")
        for msg in i:
            str(i)

    @twilio_vcr
    def test_fetch_all_out(self):
        i = logs.fetch_generator("out")
        for msg in i:
            str(i)

    @twilio_vcr
    def test_fetch_all_bad(self):
        assert isinstance(logs.fetch_generator("nope"), list)
