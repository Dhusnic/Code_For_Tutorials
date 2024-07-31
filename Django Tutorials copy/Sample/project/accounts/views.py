from django.shortcuts import render,redirect
from django.contrib.auth.models import User
from django.contrib import auth
from django.contrib import messages
def register(request):
    if request.method=="POST":
        first_name=request.POST['first_name']
        last_name=request.POST['last_name']
        user_name=request.POST['user_name']
        password=request.POST['password']
        email=request.POST['email']
        confirm_password=request.POST['confirm_password']
        if password==confirm_password:
            if User.objects.filter(username=user_name).exists():
                print("UserName Taken")
                messages.info(request,"User Id is Taken")
            elif User.objects.filter(email=email).exists():
                print("email Taken")
                messages.info(request,"Email Id is Taken")

            else:
                user=User.objects.create_user(username=user_name,password=password,email=email,first_name=first_name,last_name=last_name)
                user.save()
                print("user created")
                return redirect("login")
        else:
            messages.info(request,"Email Id is Taken")
            print("Password is not matching")
        return redirect('register')

    else:
        return render(request,"register.html")
    
def login(request):
    if request.method=='POST':
        username=request.POST['user_name']
        password=request.POST['password']
        user=auth.authenticate(username=username,password=password)
        if user is not None:
            auth.login(request,user)
            return redirect("/travello")
        else:
            messages.info(request,'invalid Credentials')
            return redirect('login')
    else:
     return render(request,"login.html")
