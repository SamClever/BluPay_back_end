# Generated by Django 5.1.7 on 2025-04-04 12:08

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Accounts', '0004_rename_tree_name_kyc_last_name'),
    ]

    operations = [
        migrations.RenameField(
            model_name='kyc',
            old_name='full_name',
            new_name='First_name',
        ),
    ]
