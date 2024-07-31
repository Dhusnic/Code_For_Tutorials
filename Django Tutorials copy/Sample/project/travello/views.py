from django.shortcuts import render
from .models import Destination
# Create your views here.
def index(request):
   # dest1=Destination()
   # dest1.name="Mumbai"
   # dest1.price=700
   # dest1.offer=True
   # dest1.img='place/2.png'
   # dest1.des="nothing special in Mumbai"
   # dest2=Destination()
   # dest2.name="America"
   # dest2.price=900
   # dest2.offer=False
   # dest2.img="place/5.png"
   # dest2.des="nothing special in America"
   # dest3=Destination()
   # dest3.name="Banglore"
   # dest3.price=200
   # dest3.offer=True
   # dest3.img="place/6.png"
   # dest3.des="Girls"
   # dests=[dest1,dest2,dest3]

   dests=Destination.objects.all()
   return render(request,"index.html",{"dests":dests})


def contact(request):
   return render(request,"contact.html")