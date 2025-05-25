from django.shortcuts import render
from django.http import HttpResponse
# Create your views here.
def sing_up(req):
    return HttpResponse("hello signup")
def log_in(req):
    return HttpResponse("hello log_in")