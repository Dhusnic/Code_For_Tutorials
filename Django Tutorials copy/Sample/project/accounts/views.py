from django.shortcuts import render,redirect
from django.contrib.auth.models import User
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
            elif User.objects.filter(email=email).exists():
                print("email Taken")
            
        
            else:
                user=User.objects.create_user(username=user_name,password=Password1,email=email,first_name=first_name,last_name=last_name)
                user.save()
                print("user created")
                return redirect("/travello")
        else:
            print("Password is not matching")
        return redirect("/travello/accounts/register")

    else:
        return render(request,"register.html")