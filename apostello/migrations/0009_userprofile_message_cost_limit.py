# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-03-23 11:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("apostello", "0008_auto_20160317_1958")]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="message_cost_limit",
            field=models.DecimalField(
                decimal_places=2,
                default=2.0,
                help_text="Amount in USD that this user can spend on a single SMS. Note that this is a sanity check, not a security measure - There are no rate limits. If you do not trust a user, revoke their ability to send SMS. Set to zero to disable limit.",
                max_digits=5,
            ),
        )
    ]
