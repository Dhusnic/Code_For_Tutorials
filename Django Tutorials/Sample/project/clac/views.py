from django.shortcuts import render
from django.http import HttpResponse
# Create your views here.
def home(request):
    return HttpResponse("hello world")
def html(request):
    return render(request,'html.html',{'name':'Dhusnic'})
def add(request):
    # val1=int(request.GET["num1"])
    val1=int(request.POST["num1"])
    # val2=int(request.GET["num2"])
    val2=int(request.POST["num2"])
    ans=val1+val2
    return render(request,'result.html',{'result':ans})
