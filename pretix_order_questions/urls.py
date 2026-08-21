from django.urls import re_path

from .views import OrderQuestionCreate, OrderQuestionDelete, OrderQuestionList, OrderQuestionUpdate


urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/order-questions/$",
        OrderQuestionList.as_view(), name="list",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/order-questions/add/$",
        OrderQuestionCreate.as_view(), name="add",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/order-questions/(?P<pk>\d+)/edit/$",
        OrderQuestionUpdate.as_view(), name="edit",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/order-questions/(?P<question>\d+)/delete/$",
        OrderQuestionDelete.as_view(), name="delete",
    ),
]
