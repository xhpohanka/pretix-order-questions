from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.control.views.event import EventSettingsViewMixin

from .forms import OrderQuestionForm, OrderQuestionOptionFormSet
from .models import OrderQuestion


class OrderQuestionList(EventSettingsViewMixin, EventPermissionRequiredMixin, ListView):
    template_name = "pretix_order_questions/list.html"
    context_object_name = "questions"
    permission = "event.settings.general:write"

    def get_queryset(self):
        return self.request.event.order_questions.prefetch_related("options")


class OrderQuestionMixin(EventSettingsViewMixin, EventPermissionRequiredMixin):
    model = OrderQuestion
    form_class = OrderQuestionForm
    template_name = "pretix_order_questions/form.html"
    context_object_name = "question"
    permission = "event.settings.general:write"

    def get_queryset(self):
        return self.request.event.order_questions.all()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        if not kwargs.get("instance"):
            kwargs["instance"] = OrderQuestion(event=self.request.event)
        return kwargs

    def get_formset(self):
        instance = getattr(self, "object", None) or self.get_form_kwargs()["instance"]
        return OrderQuestionOptionFormSet(
            self.request.POST if self.request.method == "POST" else None,
            instance=instance,
            prefix="options",
            form_kwargs={"event": self.request.event},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["formset"] = kwargs.get("formset") or self.get_formset()
        return context

    def get_success_url(self):
        return reverse("plugins:pretix_order_questions:list", kwargs={
            "organizer": self.request.organizer.slug,
            "event": self.request.event.slug,
        })

    @transaction.atomic
    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.event = self.request.event
        formset = OrderQuestionOptionFormSet(
            self.request.POST,
            instance=self.object,
            prefix="options",
            form_kwargs={"event": self.request.event},
        )
        if not formset.is_valid():
            return self.form_invalid(form, formset=formset)

        choice_type = self.object.type in (OrderQuestion.TYPE_CHOICE, OrderQuestion.TYPE_CHOICE_MULTIPLE)
        option_forms = [f for f in formset.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        if choice_type and not option_forms:
            form.add_error("type", _("Add at least one answer option for this question type."))
            return self.form_invalid(form, formset=formset)

        self.object.save()
        for deleted_form in formset.deleted_forms:
            if deleted_form.instance.pk:
                deleted_form.instance.delete()
        for position, option_form in enumerate(formset.ordered_forms):
            option = option_form.save(commit=False)
            option.question = self.object
            option.position = position
            option.save()

        messages.success(self.request, _("The order question has been saved."))
        return super().form_valid(form)

    def form_invalid(self, form, formset=None):
        messages.error(self.request, _("We could not save your changes. See below for details."))
        return self.render_to_response(self.get_context_data(form=form, formset=formset))


class OrderQuestionCreate(OrderQuestionMixin, CreateView):
    pass


class OrderQuestionUpdate(OrderQuestionMixin, UpdateView):
    pass


class OrderQuestionDelete(EventSettingsViewMixin, EventPermissionRequiredMixin, DeleteView):
    model = OrderQuestion
    template_name = "pretix_order_questions/delete.html"
    context_object_name = "question"
    permission = "event.settings.general:write"

    def get_object(self, queryset=None):
        try:
            return self.request.event.order_questions.get(pk=self.kwargs["question"])
        except OrderQuestion.DoesNotExist:
            raise Http404

    def get_success_url(self):
        messages.success(self.request, _("The order question has been deleted."))
        return reverse("plugins:pretix_order_questions:list", kwargs={
            "organizer": self.request.organizer.slug,
            "event": self.request.event.slug,
        })
