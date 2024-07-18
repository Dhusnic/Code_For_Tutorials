1. Web Dev framework for python
2. built for python 3.X
3. Offers built-in solutions and features for basically all problems
4. It is Django can be expandable and customizable


https://chatgpt.com/share/251e915d-282b-4fcd-87e3-6064e2842963 - link for ecommerce Modal
https://github.com/Dhusnic/Django_Tutorial/tree/main - git link for tutorial

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

### Explanation of Files and Directories

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

### Summary
This structure helps you keep your project organized. The `myproject` directory contains global configurations and settings, while each app (like `myapp`) contains its own models, views, templates, and static files. This modular approach makes Django projects scalable and easier to manage.


#DTL-Django_Template_Language

Django Template Language (DTL) is a powerful feature of Django that allows you to create dynamic HTML templates. Here's an overview of its syntax and uses:

### 1. **Variables**

- **Syntax:** `{{ variable_name }}`
- **Use:** To output the value of a variable.
- **Example:**
  ```html
  <p>Hello, {{ user.username }}!</p>
  ```

### 2. **Filters**

- **Syntax:** `{{ value|filter_name:arg1:arg2 }}`
- **Use:** To modify or format the value.
- It always use pipe symbol " | " for representing symbol
- **Example:**
  ```html
  <p>{{ value|lower }}</p>  <!-- Converts value to lowercase -->
  <p>{{ number|floatformat:2 }}</p>  <!-- Formats number to 2 decimal places -->
  ```

### 3. **Tags**

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

### 4. **Comments**

- **Syntax:**
  ```html
  {# This is a comment #}
  ```
- **Use:** To add comments in templates.

### 5. **Inheritance**

- **Syntax:**
  ```html
  {% extends "base.html" %}
  {% block content %}
    ...code...
  {% endblock %}
  ```
- **Use:** To use a base template and override specific blocks.

### 6. **Custom Tags and Filters**

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