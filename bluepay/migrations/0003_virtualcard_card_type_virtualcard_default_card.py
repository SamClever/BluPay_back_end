# Generated by Django 5.1.7 on 2025-04-10 12:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bluepay', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='virtualcard',
            name='card_type',
            field=models.CharField(blank=True, choices=[('master', 'master'), ('visa', 'visa'), ('verve', 'verve')], max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='virtualcard',
            name='default_card',
            field=models.BooleanField(default=False),
        ),
    ]
