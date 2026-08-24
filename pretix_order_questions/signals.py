from django import forms
from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _

from pretix.api.signals import order_api_details
from pretix.base.signals import event_copy_data, order_modified, order_placed
from pretix.control.signals import nav_event_settings, order_info as control_order_info_signal
from pretix.presale.signals import contact_form_fields, order_info as presale_order_info_signal

from .forms import DisplayChoiceField, DisplayMultipleChoiceField
from .models import OrderQuestion, OrderQuestionOption
from .services import sync_order_answers


@receiver(nav_event_settings, dispatch_uid="pretix_order_questions_nav_event_settings")
def order_questions_settings_navigation(sender, request, **kwargs):
    if not request.user.has_event_permission(
            request.organizer, request.event, "event.settings.general:write", request=request):
        return []
    return [{
        "label": _("Order questions"),
        "url": reverse("plugins:pretix_order_questions:list", kwargs={
            "organizer": request.organizer.slug,
            "event": request.event.slug,
        }),
        "active": resolve(request.path_info).namespace == "plugins:pretix_order_questions",
    }]


def _field_for_question(question):
    kwargs = {
        "label": question.question,
        "help_text": question.help_text,
        "required": question.required,
    }
    if question.type == OrderQuestion.TYPE_TEXT:
        return forms.CharField(widget=forms.Textarea, **kwargs)
    if question.type == OrderQuestion.TYPE_BOOLEAN:
        return forms.BooleanField(**kwargs)

    choices = [(option.identifier, option.answer) for option in question.options.all()]
    if question.type == OrderQuestion.TYPE_CHOICE:
        return DisplayChoiceField(choices=[("", "---------"), *choices], **kwargs)
    if question.type == OrderQuestion.TYPE_CHOICE_MULTIPLE:
        return DisplayMultipleChoiceField(
            choices=choices,
            widget=forms.CheckboxSelectMultiple,
            **kwargs,
        )
    return forms.CharField(**kwargs)


@receiver(contact_form_fields, dispatch_uid="pretix_order_questions_contact_fields")
def order_question_fields(sender, **kwargs):
    return {
        question.form_key: _field_for_question(question)
        for question in sender.order_questions.filter(active=True).prefetch_related("options")
    }


@receiver(order_placed, dispatch_uid="pretix_order_questions_order_placed")
@receiver(order_modified, dispatch_uid="pretix_order_questions_order_modified")
def update_order_answers(sender, order, **kwargs):
    sync_order_answers(order)


@receiver(order_api_details, dispatch_uid="pretix_order_questions_order_api_details")
def order_questions_api_details(sender, order, **kwargs):
    answers = order.order_question_answers.select_related("question").prefetch_related("question__options")
    return {
        "order_questions": [
            {
                "identifier": answer.question.identifier,
                "question": str(answer.question),
                "answer": answer.display_value,
            }
            for answer in answers
        ]
    }


@receiver(event_copy_data, dispatch_uid="pretix_order_questions_copy_event")
def copy_event_questions(sender, other, **kwargs):
    for source in other.order_questions.prefetch_related("options"):
        target = OrderQuestion.objects.create(
            event=sender,
            question=source.question,
            help_text=source.help_text,
            identifier=source.identifier,
            type=source.type,
            required=source.required,
            active=source.active,
            position=source.position,
        )
        OrderQuestionOption.objects.bulk_create([
            OrderQuestionOption(
                question=target,
                identifier=option.identifier,
                answer=option.answer,
                position=option.position,
            )
            for option in source.options.all()
        ])


def _render_answers(template_name, sender, request, order):
    answers = list(
        order.order_question_answers.select_related("question").prefetch_related("question__options")
    )
    if not answers:
        return ""
    return get_template(template_name).render({
        "answers": answers,
        "event": sender,
        "order": order,
        "request": request,
    }, request=request)


@receiver(control_order_info_signal, dispatch_uid="pretix_order_questions_control_order_info")
def control_order_info(sender, request, order, **kwargs):
    return _render_answers("pretix_order_questions/control_order_info.html", sender, request, order)


@receiver(presale_order_info_signal, dispatch_uid="pretix_order_questions_presale_order_info")
def presale_order_info(sender, request, order, **kwargs):
    return _render_answers("pretix_order_questions/presale_order_info.html", sender, request, order)
