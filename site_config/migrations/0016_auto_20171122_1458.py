# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-22 14:58
from __future__ import unicode_literals

import apostello.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("site_config", "0015_auto_20171107_1326")]

    operations = [
        migrations.AlterField(
            model_name="defaultresponses",
            name="default_no_keyword_not_live",
            field=models.TextField(
                default='Thank you, %name%, for your text. But "%keyword%" is not active...',
                help_text='Default message for when a keyword is not currently active. ("%keyword%" will be replaced with the matched keyword)',
                max_length=1000,
                validators=[apostello.validators.less_than_sms_char_limit],
            ),
        )
    ]
