# Generated by Django 5.0.3 on 2024-04-19 00:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0020_alter_playertotalscore_event_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='playerscore',
            name='points',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]