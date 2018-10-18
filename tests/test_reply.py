import pytest
from tests.conftest import twilio_vcr

from apostello.models import Recipient, RecipientGroup
from apostello.reply import InboundSms
from apostello.utils import fetch_default_reply


@pytest.mark.django_db
class TestConstructReply:
    """Tests apostello.reply:InboundSms.construct_reply function."""

    def test_no_existing_keyword(self, recipients):
        msg = InboundSms({"From": str(recipients["calvin"].number), "Body": "nope"})
        reply = msg.construct_reply()
        assert reply == fetch_default_reply("keyword_no_match").replace("%name%", "John")

    def test_existing_keyword(self, recipients, keywords):
        msg = InboundSms({"From": str(recipients["calvin"].number), "Body": "test msg"})
        reply = msg.construct_reply()
        assert reply == "Test custom response with John"

    @twilio_vcr
    def test_name(self, recipients):
        msg = InboundSms({"From": str(recipients["calvin"].number), "Body": "name John Calvin"})
        reply = msg.construct_reply()
        assert "John" in str(reply)

    def test_name_never_contact(self, recipients):
        recipients["beza"].never_contact = True
        recipients["beza"].save()
        msg = InboundSms({"From": str(recipients["beza"].number), "Body": "name"})
        reply = msg.construct_reply()
        assert len(reply) == 0

    @twilio_vcr
    def test_only_one_name(self, recipients):
        msg = InboundSms({"From": str(recipients["calvin"].number), "Body": "name JohnCalvin"})
        reply = msg.construct_reply()
        assert "Something went wrong" in reply

    @twilio_vcr
    def test_stop_start(self, recipients):
        msg = InboundSms({"From": str(recipients["calvin"].number), "Body": "stop "})
        reply = msg.construct_reply()
        assert len(reply) == 0
        assert Recipient.objects.get(pk=recipients["calvin"].pk).is_blocking

        msg = InboundSms({"From": str(recipients["calvin"].number), "Body": "start "})
        reply = msg.construct_reply()
        assert Recipient.objects.get(pk=recipients["calvin"].pk).is_blocking is False
        assert "signing up" in reply

    @twilio_vcr
    def test_existing_keyword_new_contact(self, keywords):
        msg = InboundSms({"From": "+447927401749", "Body": "test msg"})
        reply = msg.construct_reply()
        assert reply == "Thanks new person!"

    @twilio_vcr
    def test_existing_keyword_new_contact(self, keywords):
        msg = InboundSms({"From": "+447927401749", "Body": "2test msg"})
        reply = msg.construct_reply()
        assert reply == fetch_default_reply("default_no_keyword_auto_reply").replace("%name%", "Unknown")

    def test_is_blocking_reply(self, recipients):
        msg = InboundSms({"From": str(recipients["wesley"].number), "Body": "test"})
        reply = msg.construct_reply()
        assert len(reply) == 0

    def test_do_not_reply(self, recipients):
        msg = InboundSms({"From": str(recipients["beza"].number), "Body": "test"})
        reply = msg.construct_reply()
        assert len(reply) == 0

    def test_never_contact(self, recipients):
        recipients["beza"].never_contact = True
        recipients["beza"].save()
        msg = InboundSms({"From": str(recipients["beza"].number), "Body": "test"})
        reply = msg.construct_reply()
        assert len(reply) == 0

    def test_switch_off_no_keyword_reply(self, recipients):
        from site_config.models import DefaultResponses

        dr = DefaultResponses.get_solo()
        dr.keyword_no_match = ""
        dr.clean()
        dr.save()
        msg = InboundSms({"From": str(recipients["calvin"].number), "Body": "test"})
        reply = msg.construct_reply()
        assert len(reply) == 0

    def test_contact_added_to_group_keyword(self, recipients, groups, keywords):
        populated_group = groups["test_group"]
        empty_group = groups["empty_group"]
        assert empty_group.recipient_set.count() == 0
        assert populated_group.recipient_set.count() == 2
        test_keyword = keywords["test"]
        test_keyword.linked_groups.add(empty_group, populated_group)
        test_keyword.save()
        msg = InboundSms({"From": str(recipients["beza"].number), "Body": "test"})
        reply = msg.construct_reply()
        grp1 = RecipientGroup.objects.get(name="Empty Group")
        assert grp1.recipient_set.all().count() == 1
        grp2 = RecipientGroup.objects.get(name="Test Group")
        assert grp2.recipient_set.all().count() == 3

        # let's repeat to test case where contact already in group:
        reply = msg.construct_reply()
        grp = RecipientGroup.objects.get(name="Empty Group")
        assert grp.recipient_set.count() == 1
