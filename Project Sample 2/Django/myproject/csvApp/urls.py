from django.urls import path
from .views import downloadeCSV
from .views import UploadDataView
urlpatterns=[
    path('downloade_csv',downloadeCSV),
    path('upload_csv', UploadDataView, name='upload-data'),
]