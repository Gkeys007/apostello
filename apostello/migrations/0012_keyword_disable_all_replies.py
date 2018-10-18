# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-26 20:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("apostello", "0011_recipient_do_not_reply")]

    operations = [
        migrations.AddField(
            model_name="keyword",
            name="disable_all_replies",
            field=models.BooleanField(
                default=False,
                help_text="If checked, then we will never reply to this keyword.Note that users may still be asked for their name if they are new.",
                verbose_name="Disable all replies",
            ),
        )
    ]
