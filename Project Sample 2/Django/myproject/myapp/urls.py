from django.urls import path,include
from .views import dataview
from .views import image_gallery
from rest_framework.routers  import DefaultRouter
routes= DefaultRouter()
routes.register(r'/data',dataview)
urlpatterns=[
    path(r'data',include(routes.urls)),
]