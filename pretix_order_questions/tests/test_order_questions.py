import json
from datetime import timedelta
from decimal import Decimal

from bs4 import BeautifulSoup
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import CartPosition, Event, Item, Order, Organizer, Quota, Team, User
from pretix.base.signals import event_copy_data, order_modified, order_placed
from pretix.presale.forms.checkout import ContactForm
from pretix.testutils.sessions import get_cart_session_key

from pretix_order_questions.models import OrderAnswer, OrderQuestion, OrderQuestionOption
from pretix_order_questions.forms import OrderQuestionForm
from pretix_order_questions.signals import order_questions_settings_navigation


class OrderQuestionTest(TestCase):
    @scopes_disabled()
    def setUp(self):
        self.organizer = Organizer.objects.create(name="Dummy", slug="dummy")
        self.event = Event.objects.create(
            organizer=self.organizer,
            name="Festival",
            slug="festival",
            date_from=now() + timedelta(days=30),
            live=True,
            plugins="pretix_order_questions",
        )
        self.user = User.objects.create_user("staff@example.com", "password")
        team = Team.objects.create(organizer=self.organizer, name="Staff", all_event_permissions=True)
        team.all_events = True
        team.save()
        team.members.add(self.user)
        self.client.force_login(self.user)

    @scopes_disabled()
    def test_contact_form_contains_active_order_questions(self):
        question = OrderQuestion.objects.create(
            event=self.event,
            question="Pickup point",
            identifier="pickup",
            type=OrderQuestion.TYPE_CHOICE,
            required=True,
        )
        OrderQuestionOption.objects.create(
            question=question,
            identifier="theatre",
            answer="Theatre",
        )
        hidden = OrderQuestion.objects.create(
            event=self.event,
            question="Old question",
            identifier="old",
            type=OrderQuestion.TYPE_STRING,
            active=False,
        )
        request = RequestFactory().post("/")
        request.session = {}

        form = ContactForm(
            data={"email": "customer@example.com", question.form_key: "theatre"},
            event=self.event,
            request=request,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data[question.form_key], "theatre")
        self.assertNotIn(hidden.form_key, form.fields)

    @scopes_disabled()
    def test_checkout_saves_order_question_once_in_contact_data(self):
        self.event.settings.invoice_address_asked = False
        self.event.settings.attendee_names_asked = False
        item = Item.objects.create(event=self.event, name="Ticket", default_price=Decimal("10.00"))
        quota = Quota.objects.create(event=self.event, name="Tickets", size=10)
        quota.items.add(item)
        question = OrderQuestion.objects.create(
            event=self.event,
            question="Pickup point",
            identifier="pickup",
            type=OrderQuestion.TYPE_CHOICE,
            required=True,
        )
        OrderQuestionOption.objects.create(question=question, identifier="theatre", answer="Theatre")
        self.client.get(f"/{self.organizer.slug}/{self.event.slug}/")
        cart_id = get_cart_session_key(self.client, self.event)
        CartPosition.objects.create(
            event=self.event,
            cart_id=cart_id,
            item=item,
            price=Decimal("10.00"),
            expires=now() + timedelta(minutes=10),
        )

        url = f"/{self.organizer.slug}/{self.event.slug}/checkout/questions/"
        response = self.client.get(url)
        self.assertContains(response, f'name="{question.form_key}"')
        response = self.client.post(url, {
            "email": "customer@example.com",
            question.form_key: "theatre",
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn("/checkout/payment/", response["Location"])
        self.assertEqual(
            self.client.session["carts"][cart_id]["contact_form_data"][question.form_key],
            "theatre",
        )

    @scopes_disabled()
    def test_order_signals_store_answers_directly_on_order(self):
        question = OrderQuestion.objects.create(
            event=self.event,
            question="Pickup point",
            identifier="pickup",
            type=OrderQuestion.TYPE_CHOICE,
        )
        OrderQuestionOption.objects.create(question=question, identifier="theatre", answer="Theatre")
        order = Order.objects.create(
            event=self.event,
            code="ANSWER",
            secret="a" * 32,
            status=Order.STATUS_PENDING,
            datetime=now(),
            expires=now() + timedelta(days=1),
            total=Decimal("0.00"),
            locale="en",
            sales_channel=self.organizer.sales_channels.get(identifier="web"),
            meta_info=json.dumps({"contact_form_data": {question.form_key: "theatre"}}),
        )

        order_placed.send(sender=self.event, order=order, bulk=False)

        answer = OrderAnswer.objects.get(order=order, question=question)
        self.assertEqual(answer.value, "theatre")
        self.assertEqual(answer.display_value, "Theatre")

        order.meta_info = json.dumps({"contact_form_data": {question.form_key: ""}})
        order.save(update_fields=["meta_info"])
        order_modified.send(sender=self.event, order=order)
        self.assertFalse(OrderAnswer.objects.filter(order=order, question=question).exists())

    @scopes_disabled()
    def test_disabling_question_preserves_existing_answer(self):
        question = OrderQuestion.objects.create(
            event=self.event,
            question="Pickup point",
            identifier="pickup",
            type=OrderQuestion.TYPE_STRING,
        )
        order = Order.objects.create(
            event=self.event,
            code="KEEPANS",
            secret="b" * 32,
            status=Order.STATUS_PENDING,
            datetime=now(),
            expires=now() + timedelta(days=1),
            total=Decimal("0.00"),
            locale="en",
            sales_channel=self.organizer.sales_channels.get(identifier="web"),
            meta_info=json.dumps({"contact_form_data": {question.form_key: "Main office"}}),
        )
        order_placed.send(sender=self.event, order=order, bulk=False)

        question.active = False
        question.save(update_fields=["active"])
        order.meta_info = json.dumps({"contact_form_data": {}})
        order.save(update_fields=["meta_info"])
        order_modified.send(sender=self.event, order=order)

        self.assertEqual(OrderAnswer.objects.get(order=order, question=question).value, "Main office")

    def test_admin_views_render(self):
        self.event.settings.locales = ["cs", "en"]
        response = self.client.get(reverse("plugins:pretix_order_questions:list", kwargs={
            "organizer": self.organizer.slug,
            "event": self.event.slug,
        }))
        self.assertEqual(response.status_code, 200)
        links = order_questions_settings_navigation(self.event, response.wsgi_request)
        self.assertEqual(len(links), 1)
        self.assertTrue(links[0]["active"])

        response = self.client.get(reverse("plugins:pretix_order_questions:add", kwargs={
            "organizer": self.organizer.slug,
            "event": self.event.slug,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "options-TOTAL_FORMS")
        self.assertEqual(response.context["form"].fields["question"].widget.enabled_locales, ["cs", "en"])
        self.assertEqual(
            response.context["formset"].forms[0].fields["answer"].widget.enabled_locales,
            ["cs", "en"],
        )

        doc = BeautifulSoup(response.content.decode(), "lxml")
        question_input = doc.select_one('textarea[name^="question_"]')
        option_input = doc.select_one('[name^="options-0-answer_"]')
        self.assertIsNotNone(question_input)
        self.assertIsNotNone(option_input)
        response = self.client.post(reverse("plugins:pretix_order_questions:add", kwargs={
            "organizer": self.organizer.slug,
            "event": self.event.slug,
        }), {
            question_input["name"]: "Pickup point",
            "type": OrderQuestion.TYPE_CHOICE,
            "required": "on",
            "active": "on",
            "position": "0",
            "identifier": "pickup",
            "options-TOTAL_FORMS": "1",
            "options-INITIAL_FORMS": "0",
            "options-MIN_NUM_FORMS": "0",
            "options-MAX_NUM_FORMS": "1000",
            option_input["name"]: "Theatre",
            "options-0-identifier": "theatre",
            "options-0-ORDER": "0",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        question = OrderQuestion.objects.get(event=self.event, identifier="pickup")
        self.assertTrue(question.required)
        self.assertEqual(question.options.get().identifier, "theatre")

    @scopes_disabled()
    def test_event_copy_includes_questions_and_options(self):
        question = OrderQuestion.objects.create(
            event=self.event,
            question="Pickup point",
            identifier="pickup",
            type=OrderQuestion.TYPE_CHOICE,
        )
        OrderQuestionOption.objects.create(question=question, identifier="theatre", answer="Theatre")
        copied_event = Event.objects.create(
            organizer=self.organizer,
            name="Copied festival",
            slug="copied-festival",
            date_from=now() + timedelta(days=60),
            plugins="pretix_order_questions",
        )

        event_copy_data.send(sender=copied_event, other=self.event)

        copied = copied_event.order_questions.get(identifier="pickup")
        self.assertEqual(str(copied.question), "Pickup point")
        self.assertEqual(copied.options.get().identifier, "theatre")

    @scopes_disabled()
    def test_type_change_is_blocked_after_answers_exist(self):
        question = OrderQuestion.objects.create(
            event=self.event,
            question="Pickup point",
            identifier="pickup",
            type=OrderQuestion.TYPE_STRING,
        )
        order = Order.objects.create(
            event=self.event,
            code="TYPECHG",
            secret="c" * 32,
            status=Order.STATUS_PENDING,
            datetime=now(),
            expires=now() + timedelta(days=1),
            total=Decimal("0.00"),
            locale="en",
            sales_channel=self.organizer.sales_channels.get(identifier="web"),
        )
        OrderAnswer.objects.create(order=order, question=question, value="Theatre")

        form = OrderQuestionForm(data={
            "type": OrderQuestion.TYPE_BOOLEAN,
            "required": False,
            "active": True,
            "position": 0,
            "identifier": "pickup",
        }, instance=question)

        self.assertFalse(form.is_valid())
        self.assertIn("type", form.errors)
