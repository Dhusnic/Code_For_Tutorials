from django.shortcuts import render
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.urls import reverse

# Create your views here.
month_chall = {
    "jan": "Hello everyone jan",
    "feb": "Hello everyone feb",
    "mar": "Hello everyone mar",
    "apr": "Hello everyone apr",
    "may": "Hello everyone may",
    "jun": "Hello everyone jun",
    "jul": "Hello everyone jul",
    "aug": "Hello everyone aug",
}


def monthly(request, month):
    return HttpResponse(month_chall[month])


def myapp(request):
    list_items = ""
    months = list(month_chall.keys())
    for month in months:
        month_path = reverse("month-chall", args=[month])
        month = month.capitalize()
        list_items += f'<li><a href="{month_path}">{month}</a></li>'
    data = f"<h1><ul>{list_items}</ul></h1>"
    return HttpResponse(data)


def monthly_number(request, month):
    months = list(month_chall.keys())
    if month > len(months):
        return HttpResponseNotFound("Invalid month")
    else:
        redirect_month = months[month - 1]
        redirect_path = reverse("month-chall", args=[redirect_month])
        return HttpResponseRedirect(redirect_path)
