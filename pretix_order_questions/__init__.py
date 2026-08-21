__version__ = "0.1.0"

default_app_config = "pretix_order_questions.apps.PluginApp"

from .apps import PluginApp  # noqa: E402

PretixPluginMeta = PluginApp.PretixPluginMeta
