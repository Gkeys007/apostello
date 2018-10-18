# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-21 11:35
from __future__ import unicode_literals

import apostello.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("site_config", "0001_initial")]

    operations = [
        migrations.RemoveField(model_name="siteconfiguration", name="from_email"),
        migrations.AlterField(
            model_name="defaultresponses",
            name="default_no_keyword_auto_reply",
            field=models.TextField(
                default="Thank you, %name%, your message has been received.",
                help_text="This message will be sent when an SMS matches a keyword, but that keyword has no reply set.",
                max_length=1000,
                validators=[apostello.validators.less_than_sms_char_limit],
            ),
        ),
        migrations.AlterField(
            model_name="defaultresponses",
            name="default_no_keyword_not_live",
            field=models.TextField(
                default='Thank you, %name%, for your text. But "%keyword%" is not active...',
                help_text='Default message for when a keyword is not currently active. ("%keyword" will be replaced with the matched keyword)',
                max_length=1000,
                validators=[apostello.validators.less_than_sms_char_limit],
            ),
        ),
        migrations.AlterField(
            model_name="defaultresponses",
            name="keyword_no_match",
            field=models.TextField(
                default="Thank you, %name%, your message has not matched any of our keywords. Please correct your message and try again.",
                help_text='Reply to use when an SMS does not match any keywords.("%name%" will be replaced with the user\'s first name)',
                max_length=1000,
                validators=[apostello.validators.less_than_sms_char_limit],
            ),
        ),
        migrations.AlterField(
            model_name="defaultresponses",
            name="name_failure_reply",
            field=models.TextField(
                default="Something went wrong, sorry, please try again with the format 'name John Smith'.",
                help_text='Reply to use when someone matches "name" but we are unable to parse their name.',
                max_length=1000,
                validators=[apostello.validators.less_than_sms_char_limit],
            ),
        ),
        migrations.AlterField(
            model_name="defaultresponses",
            name="name_update_reply",
            field=models.TextField(
                default="Thanks %s!",
                help_text='Reply to use when someone matches "name". ("%s" is replaced with the person\'s first name)',
                max_length=1000,
                validators=[apostello.validators.less_than_sms_char_limit],
            ),
        ),
        migrations.AlterField(
            model_name="defaultresponses",
            name="start_reply",
            field=models.TextField(
                default="Thanks for signing up!",
                help_text='Reply to use when someone matches "start".',
                max_length=1000,
                validators=[apostello.validators.less_than_sms_char_limit],
            ),
        ),
        migrations.AlterField(
            model_name="siteconfiguration",
            name="disable_all_replies",
            field=models.BooleanField(default=False, help_text="Tick this box to disable all automated replies."),
        ),
        migrations.AlterField(
            model_name="siteconfiguration",
            name="office_email",
            field=models.EmailField(
                blank=True, help_text="Email address that receives important notifications.", max_length=254
            ),
        ),
        migrations.AlterField(
            model_name="siteconfiguration",
            name="sms_char_limit",
            field=models.PositiveSmallIntegerField(
                default=160,
                help_text="SMS length limit. The sending forms use this value to limit the size of messages. Check the Twilio pricing docs for pricing information.",
            ),
        ),
        migrations.AlterField(
            model_name="siteconfiguration",
            name="sync_elvanto",
            field=models.BooleanField(
                default=False,
                help_text="Toggle automatic syncing of Elvanto groups. Syncing will be done every 24 hours.",
            ),
        ),
    ]
