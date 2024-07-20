Sure, here’s a comparison between React and Angular in a tabular format:

| Feature                 | React                                         | Angular                                          |
|-------------------------|-----------------------------------------------|--------------------------------------------------|
| **Type**                | Library for building UI components            | Full-fledged framework                           |
| **Developed by**        | Facebook                                      | Google                                           |
| **Initial Release**     | 2013                                          | 2010                                             |
| **Language**            | JavaScript (JSX)                              | TypeScript                                       |
| **Data Binding**        | One-way data binding                          | Two-way data binding                             |
| **DOM**                 | Virtual DOM                                   | Real DOM with Incremental DOM                    |
| **Learning Curve**      | Moderate (requires learning additional libraries) | Steep (comprehensive with many built-in features)|
| **Performance**         | High due to virtual DOM and selective rendering | Good but can be slower due to real DOM           |
| **Components**          | Functional and class components               | Component-based architecture with templates      |
| **State Management**    | Uses libraries like Redux, Context API        | Built-in services and RxJS for state management  |
| **Routing**             | Requires external libraries like React Router | Built-in with @angular/router module             |
| **Forms**               | Requires external libraries                   | Built-in forms module with validation            |
| **Templates**           | JSX                                           | HTML templates with Angular directives           |
| **Dependency Injection**| No built-in support, use context or libraries | Built-in support                                 |
| **Testing**             | Jest, Enzyme                                  | Jasmine, Karma                                   |
| **Community Support**   | Large, with extensive third-party libraries   | Large, with strong enterprise support            |
| **Mobile Development**  | React Native                                  | NativeScript, Ionic                              |

This table highlights the primary differences between React and Angular, helping you decide which might be more suitable for your needs based on your project's requirements and your team's expertise.

### Installation of Angular

#prequrirement_of_Angular
1. node
2. cli
3. VS Code
4. Type Script
#installing_Angular_Application

1. Install Node
2. 
```
npm i @angular/cli -g
ng new myapp

```


#running_the_Angular

```
cd .\myapp\
ng serve
```


An Angular project typically has a well-defined folder structure that organizes the different parts of the application. Here's a common folder tree structure with explanations for each file and folder:

```
angular-project/
├── e2e/                    # End-to-end tests
│   ├── src/
│   │   ├── app.e2e-spec.ts  # End-to-end test spec for the app
│   │   ├── app.po.ts        # Page object for the app
│   └── tsconfig.e2e.json    # TypeScript configuration for e2e tests
├── node_modules/            # Node.js packages
├── src/                     # Source code for the Angular application
│   ├── app/                 # Angular components, services, and modules
│   │   ├── components/      # Angular components
│   │   ├── services/        # Angular services
│   │   ├── app.component.ts # Root component
│   │   ├── app.module.ts    # Root module
│   │   └── app-routing.module.ts # Application routing module
│   ├── assets/              # Static assets like images and fonts
│   ├── environments/        # Environment configuration files
│   │   ├── environment.ts   # Default environment configuration
│   │   └── environment.prod.ts # Production environment configuration
│   ├── favicon.ico          # Favicon for the application
│   ├── index.html           # Main HTML file
│   ├── main.ts              # Entry point for the Angular application
│   ├── polyfills.ts         # Polyfills needed for the application
│   ├── styles.css           # Global styles for the application
│   ├── test.ts              # Test setup file
│   └── tsconfig.app.json    # TypeScript configuration for the application
├── .editorconfig            # Editor configuration file
├── .gitignore               # Specifies files and directories to be ignored by Git
├── angular.json            # Angular CLI configuration file
├── package.json            # Project metadata and dependencies
├── README.md               # Project documentation
├── tsconfig.json           # TypeScript configuration file
└── tslint.json             # TSLint configuration file (or `eslint.json` for ESLint)
```

### File and Folder Descriptions

- **e2e/**: Contains end-to-end tests. These tests verify the entire application flow from the user's perspective.
  - `src/app.e2e-spec.ts`: Test cases for end-to-end tests.
  - `src/app.po.ts`: Page objects that abstract interactions with the UI for testing.

- **node_modules/**: Contains the project's npm dependencies.

- **src/**: Contains the application source code.
  - **app/**: Contains the main app components, services, and modules.
    - **components/**: Folder for Angular components.
    - **services/**: Folder for Angular services.
    - `app.component.ts`: The root component of the application.
    - `app.module.ts`: The root module of the application, which declares and imports other modules and components.
    - `app-routing.module.ts`: Defines the application's routes.
  - **assets/**: Static assets like images and fonts.
  - **environments/**: Contains environment-specific configuration files.
    - `environment.ts`: Default (development) environment settings.
    - `environment.prod.ts`: Production environment settings.
  - `favicon.ico`: The favicon for the application.
  - `index.html`: The main HTML file for the application.
  - `main.ts`: The entry point of the application that bootstraps the Angular module.
  - `polyfills.ts`: Polyfills needed for the application to work in various browsers.
  - `styles.css`: Global styles applied to the application.
  - `test.ts`: Configures the test environment.
  - `tsconfig.app.json`: TypeScript configuration specific to the application code.

- **.editorconfig**: Configures coding styles for different editors.

- **.gitignore**: Specifies files and directories to be excluded from version control.

- **angular.json**: Angular CLI configuration file that contains project and build settings.

- **package.json**: Contains metadata about the project and its dependencies.

- **README.md**: Provides information about the project, including setup instructions and usage.

- **tsconfig.json**: TypeScript configuration file for the entire project.

- **tslint.json**: Configuration file for TSLint (if using TSLint). If using ESLint, this would be `eslint.json`.

This structure helps in organizing code, configurations, and assets in a way that facilitates development, testing, and deployment.

MVW
components is a where model and view combing
binding html and component is templateurl
component => @component
module => @NgModule

#code_flow 

-----
app.html->app.component.ts->app.module.ts->main.ts->index.html

---
The work flow (or) code flow of Angular:

![[angular work flow.png]]


### `HTML` - UI 

### `model` - functional component or Object

### `Component` - which adds both UI and Functional component

`[]` ->    receives data from UI to Object
`()` -> sends data  from UI to object
`[()]` -> send and receive data b/w the UI and Object

![[single way and two way.png]]


### `Module` - 




---

web package Management while running :  

to build the file:

```
cd ./myapp
ng build
```

![[angular web package management.png]]

---
![[Assests/angular MVW concept.png]]


---

![[angular ui.png]]

___

### Package-lock.jason



![[jason package lock version.png]]


### Routing

![[routing-architecture-angular.png]]

link in .html--->routing URL ---> app.Route.ts ---> loading Component file ---> display area of rout in Html.


Bootstrap is where first page or Master Page which is to be load


### Lazy Routing

![[lazy route.jpeg]]

