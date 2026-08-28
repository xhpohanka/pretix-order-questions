from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextarea

from pretix.base.forms import I18nModelForm

from .models import OrderQuestion, OrderQuestionOption


class DisplayChoiceField(forms.ChoiceField):
    """Show choice labels when the core renders checkout confirmation data."""

    def bound_data(self, data, initial):
        data = super().bound_data(data, initial)
        if data in (None, ""):
            return data
        labels = {str(value): str(label) for value, label in self.choices}
        return labels.get(str(data), str(data))


class DisplayMultipleChoiceField(forms.MultipleChoiceField):
    """Show all selected choice labels in the checkout confirmation."""

    def bound_data(self, data, initial):
        data = super().bound_data(data, initial)
        if not data:
            return data
        labels = {str(value): str(label) for value, label in self.choices}
        values = data if isinstance(data, (list, tuple)) else [data]
        return ", ".join(labels.get(str(value), str(value)) for value in values)


class OrderQuestionForm(I18nModelForm):
    question = I18nFormField(label=_("Question"), widget=I18nTextarea, widget_kwargs={"attrs": {"rows": 2}})

    class Meta:
        model = OrderQuestion
        localized_fields = "__all__"
        fields = ("question", "type", "required", "active", "show_in_pos", "position", "help_text", "identifier")
        widgets = {"help_text": I18nTextarea}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["identifier"].required = False
        self.fields["identifier"].label = _("Internal question identifier")
        self.fields["identifier"].help_text = _(
            "Used for exports and integrations, not shown to customers. "
            "Leave empty to generate it automatically."
        )

    def clean_type(self):
        value = self.cleaned_data["type"]
        if self.instance.pk and value != self.instance.type and self.instance.answers.exists():
            raise ValidationError(_(
                "The question type cannot be changed after answers have been recorded. "
                "Disable this question and create a new one instead."
            ))
        return value


class OrderQuestionOptionForm(I18nModelForm):
    identifier = forms.CharField(
        required=False,
        label=_("Internal answer identifier"),
        help_text=_("Used for stored answers and integrations; customers see the answer text."),
    )

    class Meta:
        model = OrderQuestionOption
        localized_fields = "__all__"
        fields = ("answer", "identifier")


OrderQuestionOptionFormSet = inlineformset_factory(
    OrderQuestion,
    OrderQuestionOption,
    form=OrderQuestionOptionForm,
    can_delete=True,
    can_order=True,
    extra=1,
)
