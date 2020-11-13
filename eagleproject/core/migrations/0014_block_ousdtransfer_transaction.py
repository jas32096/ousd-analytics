# Generated by Django 3.1.1 on 2020-11-12 16:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_auto_20201103_2119"),
    ]

    operations = [
        migrations.CreateModel(
            name="Block",
            fields=[
                (
                    "block_number",
                    models.IntegerField(primary_key=True, serialize=False),
                ),
                ("block_time", models.DateTimeField(db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name="OusdTransfer",
            fields=[
                (
                    "tx_hash",
                    models.CharField(max_length=66, primary_key=True, serialize=False),
                ),
                ("block_time", models.DateTimeField(db_index=True)),
                ("from_address", models.CharField(db_index=True, max_length=42)),
                ("to_address", models.CharField(db_index=True, max_length=42)),
                (
                    "amount",
                    models.DecimalField(decimal_places=18, default=0, max_digits=64),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                (
                    "tx_hash",
                    models.CharField(max_length=66, primary_key=True, serialize=False),
                ),
                ("block_number", models.IntegerField(db_index=True)),
                ("block_time", models.DateTimeField(db_index=True)),
                ("notes", models.TextField()),
                ("data", models.JSONField()),
                ("debug_data", models.JSONField()),
            ],
        ),
    ]
