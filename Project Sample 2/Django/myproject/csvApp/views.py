from django.shortcuts import render
from django.http import HttpResponse
from .serializers import CSV_DataSerializer
import csv
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
# Create your views here.
def downloadeCSV(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Data.csv"'
    writer = csv.DictWriter(response, fieldnames=['Name', 'Age', 'Degree'])
    writer.writeheader()
    return response
def UploadDataView(request):
    serializer=CSV_DataSerializer(data=request.data,many=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)