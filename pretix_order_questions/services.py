import json

from .models import OrderAnswer


def sync_order_answers(order):
    data = json.loads(order.meta_info or "{}").get("contact_form_data", {})
    questions = order.event.order_questions.filter(active=True)
    for question in questions:
        if question.form_key not in data or data[question.form_key] in (None, "", []):
            OrderAnswer.objects.filter(order=order, question=question).delete()
            continue
        OrderAnswer.objects.update_or_create(
            order=order,
            question=question,
            defaults={"value": data[question.form_key]},
        )
