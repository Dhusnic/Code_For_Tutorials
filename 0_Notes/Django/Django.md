1. Web Dev framework for python
2. built for python 3.X
3. Offers built-in solutions and features for basically all problems
4. It is Django can be expandable and customizable


https://chatgpt.com/share/251e915d-282b-4fcd-87e3-6064e2842963 - link for ecommerce Modal
https://github.com/Dhusnic/Django_Tutorial/tree/main - git link for tutorial

### Environment Setup

### Environment Setup

#creation_of_virtual_Enviroinment

```
pip install virtualenv
virtualenv venv
```


#Creation_of_Dijango_WorkSpace

```
pip install Django 
django-admin startproject mypage
```

#Run_Devolepment_Environment_or_Virtual_Enviroinment

```
python manage.py runserver - to run the devolepment server
```


#create_apps_using_manage

```
python manage.py startapp myapp
```

#File_Structure_Django
Sure! Here's a typical Django project structure and an explanation of the main files and directories:

### Typical Django Project Structure
```
myproject/
    manage.py
    myproject/
        __init__.py
        settings.py
        urls.py
        wsgi.py
        asgi.py
    myapp/
        __init__.py
        admin.py
        apps.py
        models.py
        tests.py
        views.py
        migrations/
            __init__.py
        templates/
        static/
    venv/
```

#### Explanation of Files and Directories

#### Project-Level Files
- **`manage.py`**:
  - A command-line utility that lets you interact with this Django project. You use it to run development servers, initiate database migrations, and more.

- **`myproject/`**:
  - This directory contains the project settings and configuration.

#### Files in the `myproject` Directory
- **`__init__.py`**:
  - An empty file that tells Python that this directory should be considered a package.

- **`settings.py`**:
  - Contains the settings and configuration for the Django project (e.g., database configuration, installed apps, middleware, templates, etc.).

- **`urls.py`**:
  - Contains URL declarations for the project. It's like a table of contents for the site, directing traffic based on the URL.

- **`wsgi.py`**:
  - An entry-point for WSGI-compatible web servers to serve your project. It stands for Web Server Gateway Interface.

- **`asgi.py`**:
  - An entry-point for ASGI-compatible web servers to serve your project. It stands for Asynchronous Server Gateway Interface.

#### Application-Level Files
- **`myapp/`**:
  - This directory contains the files for a Django app named `myapp`.

#### Files in the `myapp` Directory
- **`__init__.py`**:
  - An empty file that tells Python that this directory should be considered a package.

- **`admin.py`**:
  - Used to register models to be managed through the Django admin interface.

- **`apps.py`**:
  - Contains the configuration for the app. This is where you can specify some metadata about the app.

- **`models.py`**:
  - Defines the data models for your application. Models represent the structure of the database.

- **`tests.py`**:
  - Contains test cases for your application. This is where you can define unit tests to test your code.

- **`views.py`**:
  - Contains the views for your application. Views are the logic behind the web pages.

- **`migrations/`**:
  - This directory contains database migrations. Migrations are a way of propagating changes made to your models into the database schema.

  - **`__init__.py`**:
    - An empty file that tells Python that this directory should be considered a package.

- **`templates/`**:
  - This directory contains HTML templates for your application. You can create subdirectories here to organize your templates.

- **`static/`**:
  - This directory contains static files (CSS, JavaScript, images) for your application.

#### Virtual Environment
- **`venv/`**:
  - The directory containing the virtual environment for the project. This directory is typically not included in version control. It contains the installed packages and dependencies for the project.

#### Summary
This structure helps you keep your project organized. The `myproject` directory contains global configurations and settings, while each app (like `myapp`) contains its own models, views, templates, and static files. This modular approach makes Django projects scalable and easier to manage.


### FILE Flow or Work Architecture

![[Django.png]]

### MVT Structure

MVT (Model-View-Template) is a design pattern used by Django to structure its applications. It is similar to the Model-View-Controller (MVC) pattern but with a slight variation in terminology and the way components interact.

Here's a detailed explanation of each component in MVT along with an example and a flow diagram:

#### Components of MVT

1. **Model**: 
   - Represents the data or the database. It is responsible for maintaining the data logic. In Django, models are defined using Python classes and are mapped to database tables.
   
2. **View**:
   - Contains the logic that is executed in response to a user request. It interacts with the model to fetch data and sends it to the template.
   
3. **Template**:
   - Responsible for rendering the data to be presented to the user. It contains the HTML code mixed with Django Template Language (DTL).

#### Example Application: Simple Blog

#### Step-by-Step Implementation

1. **Model**:
    - Define a model for a blog post.
    ```python
    from django.db import models

    class Post(models.Model):
        title = models.CharField(max_length=100)
        content = models.TextField()
        created_at = models.DateTimeField(auto_now_add=True)

        def __str__(self):
            return self.title
    ```

2. **View**:
    - Create a view to list all blog posts.
    ```python
    from django.shortcuts import render
    from .models import Post

    def post_list(request):
        posts = Post.objects.all()
        return render(request, 'blog/post_list.html', {'posts': posts})
    ```

3. **Template**:
    - Create an HTML template to display the blog posts.
    ```html
    <!-- blog/templates/blog/post_list.html -->
    <!DOCTYPE html>
    <html>
    <head>
        <title>Blog Posts</title>
    </head>
    <body>
        <h1>Blog Posts</h1>
        <ul>
            {% for post in posts %}
                <li>{{ post.title }} - {{ post.created_at }}</li>
                <p>{{ post.content }}</p>
            {% endfor %}
        </ul>
    </body>
    </html>
    ```

4. **URL Configuration**:
    - Map the view to a URL.
    ```python
    # blog/urls.py
    from django.urls import path
    from .views import post_list

    urlpatterns = [
        path('', post_list, name='post_list'),
    ]
    ```

5. **Main URL Configuration**:
    - Include the blog URL configuration in the main `urls.py`.
    ```python
    # myproject/urls.py
    from django.contrib import admin
    from django.urls import path, include

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('blog/', include('blog.urls')),
    ]
    ```

#### Flow Diagram


![[MVT dijango.png]]
Here’s a flow diagram illustrating the MVT architecture in Django:

```plaintext
+-------------------+
|  User Request     |
|  (HTTP Request)   |
+-------------------+
        |
        v
+-------------------+
|     URLConf       |-----\
+-------------------+     |
        |                |
        v                |
+-------------------+     |
|       View        |     |
+-------------------+     |
        |                |
        v                |
+-------------------+     |
|       Model       |     |
|   (Database ORM)  |     |
+-------------------+     |
        |                |
        v                |
+-------------------+     |
|      Template     |<----/
|  (HTML + DTL)     |
+-------------------+
        |
        v
+-------------------+
|  User Response    |
|  (HTTP Response)  |
+-------------------+
```

#### Detailed Flow

1. **User Request**: A user makes an HTTP request to a Django application.
2. **URLConf**: The request is routed to the appropriate view based on the URL configuration.
3. **View**: The view processes the request, interacts with the model to retrieve or manipulate data, and prepares the context for the template.
4. **Model**: The model represents the data structure and handles data operations.
5. **Template**: The view renders the data into the template, which generates the final HTML to be sent back to the user.
6. **User Response**: The generated HTML is sent back to the user as an HTTP response.

This is a high-level overview of the MVT pattern in Django with an example of a simple blog application.

### DTL-Django Template Language

Django Template Language (DTL) is a powerful feature of Django that allows you to create dynamic HTML templates. Here's an overview of its syntax and uses:

#### 1. **Variables**

- **Syntax:** `{{ variable_name }}`
- **Use:** To output the value of a variable.
- **Example:**
  ```html
  <p>Hello, {{ user.username }}!</p>
  ```

#### 2. **Filters**

- **Syntax:** `{{ value|filter_name:arg1:arg2 }}`
- **Use:** To modify or format the value.
- It always use pipe symbol " | " for representing symbol
- **Example:**
  ```html
  <p>{{ value|lower }}</p>  <!-- Converts value to lowercase -->
  <p>{{ number|floatformat:2 }}</p>  <!-- Formats number to 2 decimal places -->
  ```

#### 3. **Tags**

#### **Control Flow Tags**

- **If Tag**
  - **Syntax:**
    ```html
    {% if condition %}
      ...code...
    {% elif other_condition %}
      ...code...
    {% else %}
      ...code...
    {% endif %}
    ```
  - **Use:** For conditional logic.
  - **Example:**
    ```html
    {% if user.is_authenticated %}
      <p>Welcome back!</p>
    {% else %}
      <p>Please log in.</p>
    {% endif %}
    ```

- **For Tag**
  - **Syntax:**
    ```html
    {% for item in item_list %}
      ...code...
    {% empty %}
      ...code...
    {% endfor %}
    ```
  - **Use:** To loop through a list of items.
  - **Example:**
    ```html
    <ul>
      {% for user in users %}
        <li>{{ user.username }}</li>
      {% empty %}
        <li>No users found.</li>
      {% endfor %}
    </ul>
    ```

- **Block Tag**
  - **Syntax:**
    ```html
    {% block block_name %}
      ...code...
    {% endblock %}
    ```
  - **Use:** To define a block of content that can be overridden in child templates.
  - **Example:**
    ```html
    {% block content %}
      <p>This is the default content.</p>
    {% endblock %}
    ```

- **Include Tag**
  - **Syntax:**
    ```html
    {% include "template_name.html" %}
    ```
  - **Use:** To include another template.
  - **Example:**
    ```html
    {% include "header.html" %}
    ```

- **Extends Tag**
  - **Syntax:**
    ```html
    {% extends "base.html" %}
    ```
  - **Use:** To extend a base template.
  - **Example:**
    ```html
    {% extends "base.html" %}
    {% block content %}
      <p>This is the content of the child template.</p>
    {% endblock %}
    ```

#### **Static Files**

- **Syntax:**
  ```html
  {% load static %}
  <img src="{% static 'images/logo.png' %}" alt="Logo">
  ```
- **Use:** To include static files like images, JavaScript, and CSS.

#### **URL Tag**

- **Syntax:**
  ```html
  {% url 'view_name' arg1=value1 %}
  ```
- **Use:** To generate URLs for views.
- **Example:**
  ```html
  <a href="{% url 'profile' user.id %}">Profile</a>
  ```

#### 4. **Comments**

- **Syntax:**
  ```html
  {# This is a comment #}
  ```
- **Use:** To add comments in templates.

#### 5. **Inheritance**

- **Syntax:**
  ```html
  {% extends "base.html" %}
  {% block content %}
    ...code...
  {% endblock %}
  ```
- **Use:** To use a base template and override specific blocks.

#### 6. **Custom Tags and Filters**

- **Syntax:** Custom tags and filters require creating Python functions and registering them with Django's template system.

**Creating a custom filter example:**

1. **Create a custom filter in a `templatetags` module:**

   ```python
   # myapp/templatetags/my_custom_filters.py
   from django import template

   register = template.Library()

   @register.filter
   def custom_filter(value):
       return value.upper()
   ```

2. **Load and use the custom filter in a template:**

   ```html
   {% load my_custom_filters %}
   {{ my_variable|custom_filter }}
   ```

These are the basics of Django Template Language. The flexibility of DTL allows for creating dynamic and reusable templates effectively.

### Django Credentials

admin Username: dhusnicinfantdm
admin webpage: http://127.0.0.1:8000/admin/login/?next=/admin/
admin password: Dhusnic#2003


### Django rest framework

#environs

```
pip install django-environ
```

#django_rest_Framework

```
pip install djangorestframework
```

#create_api_app

```
python manage.py startapp api
```


Serializers -> used to convert python data to JSON Data
Generics -> used to create , update , delete any type of modal


Connect Django to Mongo DB

1. Djongo
```
pip install djongo
```

2. pymongo :-

```
pip install pymongo==3.12.1 --upgrade
```


