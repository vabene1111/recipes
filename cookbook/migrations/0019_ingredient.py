# Generated by Django 3.0.2 on 2020-02-16 22:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cookbook', '0018_auto_20200216_2303'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ingredient',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True)),
            ],
        ),
    ]
