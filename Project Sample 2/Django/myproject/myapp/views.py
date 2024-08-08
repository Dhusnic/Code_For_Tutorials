from rest_framework import viewsets
from .models import data
from .serializers import dataSerializer
from rest_framework import viewsets
from django.conf import settings
from django.shortcuts import render
import os

# Create your views here.
class dataview(viewsets.ModelViewSet):
    queryset=data.objects.all()
    serializer_class=dataSerializer
    
def image_gallery(request):
    image_dir = os.path.join(settings.MEDIA_ROOT, 'images')  # Assuming images are stored in media/images
    image_urls = [f'{settings.MEDIA_URL}images/{filename}' for filename in os.listdir(image_dir)]
    return render(request, 'image_gallery.html', {'image_urls': image_urls})
