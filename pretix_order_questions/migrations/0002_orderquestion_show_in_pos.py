from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pretix_order_questions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderquestion",
            name="show_in_pos",
            field=models.BooleanField(default=False, verbose_name="Show answer in POS"),
        ),
    ]
