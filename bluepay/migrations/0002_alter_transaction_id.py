# Generated by Django 5.1.7 on 2025-03-15 23:27

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bluepay', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
    ]
