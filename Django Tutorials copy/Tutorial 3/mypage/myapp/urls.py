from django.urls import path
from . import views
urlpatterns = [
    path("",views.myapp),
    path('<int:month>',views.monthly_number),
    path('<str:month>',views.monthly,name="month-chall"),
]

