from django.urls import path,include
from .views import sing_up,log_in
urlpatterns=[
    path('sign_up/',sing_up),
    path('log_in/',log_in),
    
]