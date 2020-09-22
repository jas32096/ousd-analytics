# Generated by Django 3.1.1 on 2020-09-22 14:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_debugtx'),
    ]

    operations = [
        migrations.CreateModel(
            name='LogPointer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contract', models.CharField(db_index=True, max_length=256)),
                ('last_block', models.IntegerField(db_index=True)),
            ],
        ),
    ]
