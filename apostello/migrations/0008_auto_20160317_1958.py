# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-03-17 19:58
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("apostello", "0007_auto_20160315_1213")]

    operations = [
        migrations.AlterField(
            model_name="recipientgroup",
            name="name",
            field=models.CharField(
                max_length=150,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[\\s\\w@?£!1$\"¥#è?¤é%ù&ì\\ò(Ç)*:Ø+;ÄäøÆ,<LÖlöæ\\-=ÑñÅß.>ÜüåÉ/§à¡¿']+$",
                        message="You can only use GSM characters.",
                    )
                ],
                verbose_name="Name of group",
            ),
        )
    ]
