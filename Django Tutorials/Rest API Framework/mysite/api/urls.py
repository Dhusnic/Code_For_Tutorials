from django.urls import path
from . import views
urlpatterns=[
    path("blog",views.BlogPostListCreate.as_view(),name="blogpost-view-create"),
    path("blog/<int:pk>/",views.BlogPostRetrieveUpdateDestroy.as_view(),name="blogpost-update"),
]