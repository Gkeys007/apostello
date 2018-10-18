import hashlib
import logging
import re
from math import ceil

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django_q.models import Schedule
from django_q.tasks import async_task, schedule
from phonenumber_field.modelfields import PhoneNumberField

from apostello.exceptions import NoKeywordMatchException
from apostello.utils import fetch_default_reply
from apostello.validators import (
    TWILIO_INFO_WORDS,
    TWILIO_START_WORDS,
    TWILIO_STOP_WORDS,
    gsm_validator,
    less_than_sms_char_limit,
    no_overlap_keyword,
    not_twilio_num,
    twilio_reserved,
    validate_lower,
)
from site_config.models import ConfigurationError, SiteConfiguration

logger = logging.getLogger("apostello")

# precompile regex to remove non-alphanumeric characters:
re_non_alpha_numeric = re.compile("[\W_]+")


class RecipientGroup(models.Model):
    """Stores groups of recipients."""

    is_archived = models.BooleanField("Archived", default=False)
    name = models.CharField("Name of group", max_length=150, unique=True, validators=[gsm_validator])
    description = models.CharField("Group description", max_length=200)

    def send_message(self, content, sent_by, eta=None):
        """Send message to group."""
        async_task("apostello.tasks.group_send_message_task", content, self.name, sent_by, eta)

    def archive(self):
        """Archive the group."""
        self.is_archived = True
        self.keyword_set.clear()  # unlink any keywords
        self.save()

    def check_user_cost_limit(self, limit, msg):
        """Check the user has not exceeded their per SMS cost limit."""
        num_sms = ceil(len(msg) / 160)
        if limit == 0:
            return
        if limit < num_sms * self.calculate_cost():
            raise ValidationError("Sorry, you can only send messages that cost no more than ${0}.".format(limit))

    @cached_property
    def all_recipients(self):
        """Returns queryset of all recipients in group."""
        return self.recipient_set.all()

    @cached_property
    def all_recipients_not_in_group(self):
        """Returns queryset of all recipients not in group."""
        return Recipient.objects.filter(is_archived=False).exclude(groups__pk=self.pk).all()

    @property
    def all_recipients_names(self):
        """List of the names of recipients."""
        return [str(x) for x in self.all_recipients]

    def calculate_cost(self):
        """Calculate the cost of sending to this group."""
        try:
            cost = SiteConfiguration.get_twilio_settings()["sending_cost"]
        except ConfigurationError:
            cost = 0
        return cost * self.all_recipients.count()

    def __str__(self):
        """Pretty representation."""
        return self.name

    class Meta:
        ordering = ["name"]


class Recipient(models.Model):
    """Stores the name and number of recipients."""

    is_archived = models.BooleanField("Archived", default=False)
    is_blocking = models.BooleanField(
        "Blocking",
        default=False,
        help_text="If our number has received on of Twilio's stop words, " "we are now blocked.",
    )
    first_name = models.CharField(
        "First Name", max_length=settings.MAX_NAME_LENGTH, validators=[gsm_validator], db_index=True
    )
    last_name = models.CharField("Last Name", max_length=40, validators=[gsm_validator], db_index=True)
    number = PhoneNumberField(
        unique=True, validators=[not_twilio_num], help_text="Cannot be our number, or we get an SMS loop."
    )
    do_not_reply = models.BooleanField(
        "Do not reply", default=False, help_text="Tick this box to disable automated replies for this person."
    )
    never_contact = models.BooleanField(
        "Never Contact", default=False, help_text="Tick this box to prevent any messages being sent to this person."
    )
    notes = models.TextField("Notes", max_length=2000, blank=True, null=True)
    groups = models.ManyToManyField(RecipientGroup, blank=True)

    def personalise(self, message):
        """
        Personalise outgoing message.

        Any occurence of "%name%" will be replaced with the Recipient's first
        name.
        """
        return message.replace("%name%", self.first_name)

    def send_message(self, content="", group=None, sent_by="", eta=None):
        """
        Send SMS to an individual.

        If the person is blocking us, we skip them.
        """
        if not content:
            # No content, skip sending a message
            logger.info("Message content empty, skip api call")
            return
        if self.is_blocking or self.never_contact:
            return
        elif eta is None:
            async_task("apostello.tasks.recipient_send_message_task", self.pk, content, group, sent_by)
        else:
            try:
                groupObj = RecipientGroup.objects.get(name=group)
            except RecipientGroup.DoesNotExist as e:
                groupObj = None
            QueuedSms.objects.create(
                time_to_send=eta, content=content, sent_by=sent_by, recipient_group=groupObj, recipient=self
            )

    def archive(self):
        """Archive the recipient and removes it from groups."""
        self.is_archived = True
        self.groups.clear()
        self.save()

    @staticmethod
    def check_user_cost_limit(recipients, limit, msg):
        """Check the user has not exceeded their per SMS cost limit."""
        cost = SiteConfiguration.get_twilio_settings()["sending_cost"]
        num_sms = ceil(len(msg) / 160)
        if limit == 0:
            return
        if limit < len(recipients) * cost * num_sms:
            raise ValidationError("Sorry, you can only send messages that cost no more than ${0}.".format(limit))

    @cached_property
    def full_name(self):
        """Recipient's full name."""
        return "{fn} {ln}".format(fn=self.first_name, ln=self.last_name)

    @property
    def last_sms(self):
        """Last message sent to this person"""
        last_sms = cache.get("last_msg__{0}".format(self.pk))
        if last_sms is None:
            msg = SmsInbound.objects.filter(sender_num=str(self.number))
            try:
                msg = msg[0]  # sms are already sorted in time
                t = msg.time_received
                if t is not None:
                    t = t.strftime("%d %b %H:%M")
                last_sms = {"content": msg.content, "time_received": t}
            except IndexError:
                last_sms = {"content": "", "time_received": ""}
            cache.set("last_msg__{0}".format(self.pk), last_sms, 600)
        return last_sms

    def save(self, *args, **kwargs):
        """Override save method to back date name change to SMS."""
        add_to_group_flag = self.pk is None
        super(Recipient, self).save(*args, **kwargs)
        async_task("apostello.tasks.update_msgs_name", self.pk)
        if add_to_group_flag:
            from apostello.tasks import add_new_contact_to_groups

            async_task("apostello.tasks.add_new_contact_to_groups", self.pk)

    def __str__(self):
        """Pretty representation."""
        return self.full_name

    class Meta:
        ordering = ["last_name", "first_name"]


class Keyword(models.Model):
    """Stores a keyword with its related data."""

    is_archived = models.BooleanField("Archived", default=False)
    keyword = models.SlugField(
        "Keyword",
        max_length=12,
        unique=True,
        validators=[validate_lower, gsm_validator, twilio_reserved, no_overlap_keyword],
    )
    description = models.CharField("Keyword Description", max_length=200)
    disable_all_replies = models.BooleanField(
        "Disable all replies",
        default=False,
        help_text="If checked, then we will never reply to this keyword."
        "Note that users may still be asked for their name if they are new.",
    )
    custom_response = models.CharField(
        "Auto response",
        max_length=100,
        blank=True,
        validators=[gsm_validator, less_than_sms_char_limit],
        help_text="This text will be sent back as a reply when any incoming "
        "message matches this keyword. "
        "If empty, the site wide response will be used.",
    )
    custom_response_new_person = models.CharField(
        "Auto response used when the contact is new",
        max_length=100,
        blank=True,
        validators=[gsm_validator, less_than_sms_char_limit],
        help_text="This text will be sent back as a reply when any incoming "
        "message matches this keyword and the contact is new. "
        "If empty, the normal custom response will be used.",
    )
    deactivated_response = models.CharField(
        "Deactivated response",
        max_length=100,
        blank=True,
        validators=[gsm_validator, less_than_sms_char_limit],
        help_text="Use this if you want a custom response after deactivation. "
        "e.g. 'You are too late for this event, sorry!'",
    )
    too_early_response = models.CharField(
        "Not yet activated response",
        max_length=1000,
        blank=True,
        validators=[gsm_validator, less_than_sms_char_limit],
        help_text="Use this if you want a custom response before. "
        "e.g. 'You are too early for this event, please try again on Monday!'",
    )
    activate_time = models.DateTimeField(
        "Activation Time",
        default=timezone.now,
        help_text="The keyword will not be active before this time and so no "
        "messages will be able to match it. Leave blank to activate now.",
    )
    deactivate_time = models.DateTimeField(
        "Deactivation Time",
        blank=True,
        null=True,
        help_text="The keyword will not be active after this time and so no "
        "messages will be able to match it. Leave blank to never deactivate.",
    )
    linked_groups = models.ManyToManyField(
        RecipientGroup,
        blank=True,
        help_text="Contacts that match this keyword will be added to the" " selected groups.",
    )
    owners = models.ManyToManyField(
        User,
        blank=True,
        verbose_name="Limit viewing to only these people",
        help_text="If this field is empty, any user can see this keyword. "
        "If populated, then only the named users and staff will have access.",
    )
    subscribed_to_digest = models.ManyToManyField(
        User,
        blank=True,
        verbose_name="Subscribed to daily emails.",
        related_name="subscribers",
        help_text="Choose users that will receive daily updates of matched " "messages.",
    )
    last_email_sent_time = models.DateTimeField("Time of last sent email", blank=True, null=True)

    def construct_reply(self, recipient):
        """Make reply to an incoming message."""
        reply = self.get_current_response(recipient=recipient)
        return recipient.personalise(reply)

    def add_contact_to_groups(self, sender):
        """Add contact to linked group.

        If this keyword has a linked group, we want to add the contact that
        sent the current SMS.

        Note, this will only be called if we have already matched the keyword.
        """
        for grp in self.linked_groups.all():
            if not grp.is_archived:
                grp.recipient_set.add(sender)
                grp.save()

    def get_current_response(self, recipient=None):
        if self.disable_all_replies:
            return ""

        if not self.is_live:
            if self.deactivated_response != "" and self.has_ended:
                reply = self.deactivated_response
            elif self.too_early_response != "" and self.has_not_started:
                reply = self.too_early_response
            else:
                reply = fetch_default_reply("default_no_keyword_not_live")
        else:
            # keyword is active
            reply = self.custom_response or fetch_default_reply("default_no_keyword_auto_reply")
            if recipient is not None:
                # check if user is unknown
                if recipient.first_name == "Unknown":
                    reply = self.custom_response_new_person or reply

        return reply.replace("%keyword%", self.keyword)

    @cached_property
    def current_response(self, recipient=None):
        """Currently active response"""
        return self.get_current_response(recipient=recipient)

    @property
    def has_started(self):
        """True if the current time is after the start time."""
        return timezone.now() > self.activate_time

    @property
    def has_not_started(self):
        """True if the current time is before the start time."""
        return not self.has_started

    @property
    def has_not_ended(self):
        """True if the current time is before the end time."""
        if self.deactivate_time is None:
            not_ended = True
        else:
            not_ended = timezone.now() < self.deactivate_time

        return not_ended

    @property
    def has_ended(self):
        """True if the current time is after the end time."""
        return not self.has_not_ended

    @property
    def is_live(self):
        """Is keyword active."""
        return self.has_started and self.has_not_ended

    def fetch_matches(self):
        """Fetch un-archived messages that match keyword."""
        return SmsInbound.objects.filter(matched_keyword=self.keyword, is_archived=False)

    def fetch_archived_matches(self):
        """Fetch archived messages that match keyword."""
        return SmsInbound.objects.filter(matched_keyword=self.keyword, is_archived=True)

    @property
    def num_matches(self):
        """Fetch number of un-archived messages that match keyword."""
        cache_key = "keyword_{0}_num_resps".format(self.pk)
        cached_val = cache.get(cache_key)
        if cached_val is None:
            new_val = self.fetch_matches().count()
            cache.set(cache_key, new_val, 600)
            return new_val
        else:
            return cached_val

    @property
    def num_archived_matches(self):
        """Fetch number of archived messages that match keyword."""
        cache_key = "keyword_{0}_num_arch_resps".format(self.pk)
        cached_val = cache.get(cache_key)
        if cached_val is None:
            new_val = self.fetch_archived_matches().count()
            cache.set(cache_key, new_val, 600)
            return new_val
        else:
            return cached_val

    @property
    def is_locked(self):
        """Is keyword is locked."""
        if self.owners.all().count() > 0:
            return True
        else:
            return False

    def can_user_access(self, user):
        """Check if user is allowed to access this keyword."""
        if not self.is_locked:
            return True
        if user in self.owners.all():
            return True
        elif user.is_staff:
            return True
        else:
            return False

    def archive(self):
        """Archive this keyword and all matches."""
        self.is_archived = True
        self.save()
        logger.debug("Archived %s (pk=%s)", self.keyword, self.pk)
        for sms in self.fetch_matches():
            sms.archive()

    def clean(self):
        """Ensure we do not start before we finish."""
        if self.deactivate_time is None:
            return
        if self.activate_time > self.deactivate_time:
            raise ValidationError("The start time must be before the end time!")

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        """Force lower case keywords."""
        self.keyword = self.keyword.lower()
        super(Keyword, self).save(force_insert, force_update, *args, **kwargs)
        async_task("apostello.tasks.populate_keyword_response_count", pk=self.pk)

    @staticmethod
    def _match(sms):
        """Match keyword or raises exception."""
        cleaned_sms = sms.lower().strip()
        cleaned_sms = re_non_alpha_numeric.sub("", cleaned_sms)
        if cleaned_sms == "":
            raise NoKeywordMatchException
        if cleaned_sms.startswith(TWILIO_STOP_WORDS):
            return "stop"
        elif cleaned_sms.startswith(TWILIO_START_WORDS):
            return "start"
        elif cleaned_sms.startswith(TWILIO_INFO_WORDS):
            return "info"
        elif cleaned_sms.startswith("name"):
            return "name"

        for keyword in Keyword.objects.all():
            if cleaned_sms.startswith(str(keyword)):
                query_keyword = keyword
                # return <Keyword object>
                return query_keyword
        else:
            raise NoKeywordMatchException

    @staticmethod
    def match(sms):
        """Match keyword at start of sms."""
        try:
            return Keyword._match(sms)
        except NoKeywordMatchException:
            return "No Match"

    @staticmethod
    def lookup_colour(sms):
        """Generate. colour for sms table."""
        keyword = Keyword.match(sms)

        if keyword == "stop":
            return "#FFCDD2"
        elif keyword == "name":
            return "#BBDEFB"
        elif keyword == "No Match":
            return "#B6B6B6"
        else:
            return "#" + hashlib.md5(str(keyword).encode("utf-8")).hexdigest()[:6]

    def __str__(self):
        """Pretty representation."""
        return self.keyword

    class Meta:
        ordering = ["keyword"]


class SmsInbound(models.Model):
    """A SmsInbound is a message that was sent to the twilio number."""

    sid = models.CharField("SID", max_length=34, unique=True, help_text="Twilio's unique ID for this SMS")
    is_archived = models.BooleanField("Is Archived", default=False, db_index=True)
    dealt_with = models.BooleanField(
        "Dealt With?", default=False, help_text="Used, for example, " "to mark people as registered for an event."
    )
    content = models.CharField("Message body", blank=True, max_length=1600)
    time_received = models.DateTimeField(blank=True, null=True)
    sender_name = models.CharField("Sent by", max_length=200)
    sender_num = models.CharField("Sent from", max_length=200)
    matched_keyword = models.CharField(max_length=12, db_index=True)
    matched_colour = models.CharField(max_length=7)
    display_on_wall = models.BooleanField(
        "Display on Wall?", default=False, help_text="If True, SMS will be shown on all live walls."
    )

    def archive(self):
        """Archive the SMS."""
        self.is_archived = True
        self.display_on_wall = False
        self.save()

    def delete_from_twilio(self):
        """
        Permanently remove this message from Twilio and apostello.

        This cannot be reversed.
        """
        async_task("apostello.tasks.delete_from_twilio", self.sid)
        self.delete()

    def __str__(self):
        """Pretty representation."""
        return self.content

    @cached_property
    def sender_pk(self):
        """pk for message sender."""
        return Recipient.objects.get(number=self.sender_num).pk

    def reimport(self):
        """
        Manual retrieval of a message from twilio in case of server downtime.

        Note that the message will not be replied to.
        """
        matched_keyword = Keyword.match(self.content.strip())
        self.matched_keyword = str(matched_keyword)
        self.matched_colour = Keyword.lookup_colour(self.content.strip())
        self.is_archived = False
        self.dealt_with = False
        self.save()
        return self

    def save(self, *args, **kwargs):
        """Override save method to invalidate cache."""
        super(SmsInbound, self).save(*args, **kwargs)
        # invalidate per person last sms cache
        cache.set("last_msg__{0}".format(self.sender_num), None, 0)
        # update number of matched responses caches
        async_task("apostello.tasks.populate_keyword_response_count")

    class Meta:
        ordering = ["-time_received"]
        index_together = ["is_archived", "matched_keyword"]


class QueuedSms(models.Model):
    """And outbound SMS to be sent at a later time."""

    time_to_send = models.DateTimeField()
    sent = models.BooleanField(default=False)
    failed = models.BooleanField(default=False)
    content = models.CharField("Message", max_length=1600, validators=[gsm_validator])
    sent_by = models.CharField(
        "Sender", max_length=200, help_text="User that sent message. Stored for auditing purposes."
    )
    recipient_group = models.ForeignKey(
        RecipientGroup,
        null=True,
        blank=True,
        help_text="Group (if any) that message was sent to",
        on_delete=models.CASCADE,
    )
    recipient = models.ForeignKey(Recipient, blank=True, null=True, on_delete=models.CASCADE)

    def cancel(self):
        """Cancel message."""
        self.delete()

    def send(self):
        """Send the sms."""
        if self.sent or self.failed:
            # only try to send once
            return

        from apostello.tasks import recipient_send_message_task

        try:
            if self.recipient_group is not None:
                group = self.recipient_group.name
            else:
                group = None
            recipient_send_message_task(self.recipient.pk, self.content, group, self.sent_by)
            self.sent = True
        except Exception as e:
            self.failed = True

        self.save()

    def __str__(self):
        """Pretty representation."""
        status = "Sent" if self.sent else "Queued"
        val = "[{status}] To: {recipient} Msg: {content}\nScheduled for {time}".format(
            status=status, recipient=self.recipient, content=self.content, time=self.time_to_send
        )
        return val

    class Meta:
        ordering = ["time_to_send"]


class SmsOutbound(models.Model):
    """An SmsOutbound is an SMS that has been sent out by the app."""

    sid = models.CharField("SID", max_length=34, unique=True, help_text="Twilio's unique ID for this SMS")
    content = models.CharField("Message", max_length=1600, validators=[gsm_validator])
    time_sent = models.DateTimeField(default=timezone.now)
    sent_by = models.CharField(
        "Sender", max_length=200, help_text="User that sent message. Stored for auditing purposes."
    )
    recipient_group = models.ForeignKey(
        RecipientGroup,
        null=True,
        blank=True,
        help_text="Group (if any) that message was sent to",
        on_delete=models.CASCADE,
    )
    recipient = models.ForeignKey(Recipient, blank=True, null=True, on_delete=models.CASCADE)
    status = models.CharField("Status", max_length=50, help_text="Status of SMS (from Twilio)")

    def delete_from_twilio(self):
        """
        Permanently remove this message from Twilio and apostello.

        This cannot be reversed.
        """
        async_task("apostello.tasks.delete_from_twilio", self.sid)
        self.delete()

    def __str__(self):
        """Pretty representation."""
        return self.content

    class Meta:
        ordering = ["-time_sent"]


class UserProfile(models.Model):
    """
    Stores permissions related to a User.

    The default profile is created on first access to user.profile.
    """

    user = models.OneToOneField(User, unique=True, related_name="profile", on_delete=models.CASCADE)

    approved = models.BooleanField(default=False, help_text="This must be true to grant users access to the site.")
    show_tour = models.BooleanField(default=True, help_text="If true, the user will be shown popup tour on index page.")

    message_cost_limit = models.DecimalField(
        default=2.00,
        help_text="Amount in USD that this user can spend on a single SMS."
        " Note that this is a sanity check, not a security measure -"
        " There are no rate limits."
        " If you do not trust a user, revoke their ability to send SMS."
        " Set to zero to disable limit.",
        max_digits=5,
        decimal_places=2,
    )

    can_see_groups = models.BooleanField(default=True)
    can_see_contact_names = models.BooleanField(default=True)
    can_see_keywords = models.BooleanField(default=True)
    can_see_outgoing = models.BooleanField(default=True)
    can_see_incoming = models.BooleanField(default=True)

    can_send_sms = models.BooleanField(default=False)
    can_see_contact_nums = models.BooleanField(default=False)
    can_see_contact_notes = models.BooleanField(default=False)
    can_import = models.BooleanField(default=False)
    can_archive = models.BooleanField(default=True)

    @staticmethod
    def nullProfile():
        p = UserProfile()

        dummy_user = User()
        dummy_user.email = "--"
        dummy_user.username = "--"
        dummy_user.is_staff = True
        dummy_user.is_social = False
        dummy_user.pk = 0

        p.user = dummy_user
        p.pk = 0
        return p

    def __str__(self):
        """Pretty representation."""
        return "Profile: " + str(self.user)

    class Meta:
        ordering = ["user__email"]

    def save(self, *args, **kwargs):
        """Override save method to set approved status and invalidate navbar cache."""
        if self.pk is None:
            # on first save, approve whitelisted domains
            try:
                email = self.user.email
                email_domain = email.split("@")[1]
                safe_domains = settings.WHITELISTED_LOGIN_DOMAINS
                if email_domain in safe_domains:
                    self.approved = True
            except IndexError:
                # no email adress, leave as unapproved
                pass
        else:
            # any other save, we want to refresh navbar and elm settings:
            for k in ["topbar", "elmSettings"]:
                key = make_template_fragment_key(k, [self.user])
                cache.delete(key)
        super(UserProfile, self).save(*args, **kwargs)
