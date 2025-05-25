from django.contrib import admin
from django.urls import path
from . import views
urlpatterns=[
    path('home/',views.home,name='home'),
    path('htmlpage/',views.html,name='html'),
    path('htmlpage/add',views.add,name='add'),
]