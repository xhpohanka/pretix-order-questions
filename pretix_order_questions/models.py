from django.core.validators import RegexValidator
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField

from pretix.base.models import Event, Order


identifier_validator = RegexValidator(
    regex=r"^[a-zA-Z0-9.\-_]+$",
    message=_("The identifier may only contain letters, numbers, dots, dashes, and underscores."),
)


class OrderQuestion(models.Model):
    TYPE_STRING = "S"
    TYPE_TEXT = "T"
    TYPE_BOOLEAN = "B"
    TYPE_CHOICE = "C"
    TYPE_CHOICE_MULTIPLE = "M"
    TYPE_CHOICES = (
        (TYPE_STRING, _("Text (one line)")),
        (TYPE_TEXT, _("Multiline text")),
        (TYPE_BOOLEAN, _("Yes/No")),
        (TYPE_CHOICE, _("Choose one from a list")),
        (TYPE_CHOICE_MULTIPLE, _("Choose multiple from a list")),
    )

    event = models.ForeignKey(Event, related_name="order_questions", on_delete=models.CASCADE)
    question = I18nTextField(verbose_name=_("Question"))
    help_text = I18nTextField(verbose_name=_("Help text"), blank=True)
    identifier = models.CharField(
        max_length=190,
        verbose_name=_("Internal identifier"),
        validators=[identifier_validator],
        help_text=_("Used for exports and integrations. Leave empty to generate it automatically."),
    )
    type = models.CharField(max_length=1, choices=TYPE_CHOICES, verbose_name=_("Question type"))
    required = models.BooleanField(default=False, verbose_name=_("Required question"))
    active = models.BooleanField(default=True, verbose_name=_("Ask this question during checkout"))
    show_in_pos = models.BooleanField(default=False, verbose_name=_("Show answer in POS"))
    position = models.PositiveIntegerField(default=0, verbose_name=_("Position"))

    class Meta:
        ordering = ("position", "pk")
        unique_together = (("event", "identifier"),)

    def __str__(self):
        return str(self.question)

    @property
    def form_key(self):
        return f"pretix_order_question_{self.pk}"

    def save(self, *args, **kwargs):
        if not self.identifier:
            chars = "ABCDEFGHJKLMNPQRSTUVWXYZ3789"
            while True:
                identifier = get_random_string(8, chars)
                if not OrderQuestion.objects.filter(event=self.event, identifier=identifier).exists():
                    self.identifier = identifier
                    break
        super().save(*args, **kwargs)


class OrderQuestionOption(models.Model):
    question = models.ForeignKey(OrderQuestion, related_name="options", on_delete=models.CASCADE)
    identifier = models.CharField(max_length=190, validators=[identifier_validator])
    answer = I18nCharField(verbose_name=_("Answer"))
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "pk")
        unique_together = (("question", "identifier"),)

    def __str__(self):
        return str(self.answer)

    def save(self, *args, **kwargs):
        if not self.identifier:
            chars = "ABCDEFGHJKLMNPQRSTUVWXYZ3789"
            while True:
                identifier = get_random_string(8, chars)
                if not OrderQuestionOption.objects.filter(question=self.question, identifier=identifier).exists():
                    self.identifier = identifier
                    break
        super().save(*args, **kwargs)


class OrderAnswer(models.Model):
    order = models.ForeignKey(Order, related_name="order_question_answers", on_delete=models.CASCADE)
    question = models.ForeignKey(OrderQuestion, related_name="answers", on_delete=models.CASCADE)
    value = models.JSONField()

    class Meta:
        unique_together = (("order", "question"),)

    def __str__(self):
        return self.display_value

    @property
    def display_value(self):
        if self.question.type == OrderQuestion.TYPE_BOOLEAN:
            return str(_("Yes") if self.value else _("No"))
        if self.question.type in (OrderQuestion.TYPE_CHOICE, OrderQuestion.TYPE_CHOICE_MULTIPLE):
            values = self.value if isinstance(self.value, list) else [self.value]
            options = {o.identifier: str(o.answer) for o in self.question.options.all()}
            return ", ".join(options.get(value, str(value)) for value in values)
        return str(self.value)
