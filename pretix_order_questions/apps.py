from django.utils.translation import gettext_lazy as _

from pretix.base.plugins import PluginConfig

from . import __version__


class PluginApp(PluginConfig):
    name = "pretix_order_questions"
    verbose_name = _("Order questions")

    class PretixPluginMeta:
        name = _("Order questions")
        author = "Jan Pohanka"
        description = _("Ask custom questions once per order instead of once per ticket.")
        category = "FEATURE"
        visible = True
        version = __version__
        compatibility = "pretix>=2026.7.0.dev0"
        settings_links = [
            ((_('Settings'), _('Order questions')), 'plugins:pretix_order_questions:list', {}),
        ]

    def ready(self):
        from . import signals  # noqa: F401
