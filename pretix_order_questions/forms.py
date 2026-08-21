from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextarea

from pretix.base.forms import I18nModelForm

from .models import OrderQuestion, OrderQuestionOption


class OrderQuestionForm(I18nModelForm):
    question = I18nFormField(label=_("Question"), widget=I18nTextarea, widget_kwargs={"attrs": {"rows": 2}})

    class Meta:
        model = OrderQuestion
        localized_fields = "__all__"
        fields = ("question", "type", "required", "active", "position", "help_text", "identifier")
        widgets = {"help_text": I18nTextarea}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["identifier"].required = False

    def clean_type(self):
        value = self.cleaned_data["type"]
        if self.instance.pk and value != self.instance.type and self.instance.answers.exists():
            raise ValidationError(_(
                "The question type cannot be changed after answers have been recorded. "
                "Disable this question and create a new one instead."
            ))
        return value


class OrderQuestionOptionForm(I18nModelForm):
    identifier = forms.CharField(required=False, label=_("Internal identifier"))

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
