# Life Cycle Of a Component React

![Screenshot 2024-05-18 101700.png](Life%20Cycle%20Of%20a%20Component%20React%2035d3fd1d97544139a92d82ff01861ddd/Screenshot_2024-05-18_101700.png)

In React, the life cycle of a component can be broken down into four main phases: mounting, updating, unmounting, and error handling.

1. **Mounting:** This is the phase when the component is being created and inserted into the DOM. It has four built-in methods: `constructor()`, `static getDerivedStateFromProps()`, `render()`, and `componentDidMount()`.
2. **Updating:** An update can be caused by changes to props or state. This phase has five built-in methods: `static getDerivedStateFromProps()`, `shouldComponentUpdate()`, `render()`, `getSnapshotBeforeUpdate()` and `componentDidUpdate()`.
3. **Unmounting:** This is the final phase of a component's life cycle. It happens when the component is being removed from the DOM. It has one built-in method: `componentWillUnmount()`.
4. **Error Handling:** This phase deals with how the component handles any errors that occur during rendering, in a lifecycle method, or in the constructor of any child component. React provides two lifecycle methods for error handling: `static getDerivedStateFromError()` and `componentDidCatch()`.

Understanding these phases and the methods available in each one is essential for managing state and props effectively, optimizing the performance of your React applications, and handling errors gracefully.

![Screenshot 2024-05-18 101816.png](Life%20Cycle%20Of%20a%20Component%20React%2035d3fd1d97544139a92d82ff01861ddd/Screenshot_2024-05-18_101816.png)

## Mounting

The mounting phase is the initial phase in the component lifecycle in React. It is during this phase where the component instance is being created and inserted into the DOM. This phase comes with several built-in methods:

- `constructor()`: This is the method where you initialize state and bind methods. It's the first method that runs in your component. It is a good practice to set up state and other initial values in the constructor.
- `static getDerivedStateFromProps()`: This method exists for rare use cases where the state depends on changes in props over time. It returns an object to update the state, or null to update nothing.
- `render()`: This is the required method in each component. It examines this.props and this.state and returns one of the following types: React elements, Arrays and fragments, Portals, String and numbers, Booleans or null.
- `componentDidMount()`: This method is executed after the first render only on the client side. This is where AJAX requests and DOM or state updates should occur. This method is also used for integration with other JavaScript frameworks and any functions with delayed execution such as `setTimeout` or `setInterval`.

## Updating

The updating phase is triggered when there are changes to props or state. This phase has five built-in methods:

- `static getDerivedStateFromProps()`: This method is invoked right before calling the render method, both on the initial mount and on subsequent updates. It should return an object to update the state, or null to update nothing.
- `shouldComponentUpdate()`: This method is invoked before rendering when new props or state are being received. By default, this method returns true to let React know that it needs to re-render the component. You can return false to let React know that the component does not need to be updated.
- `render()`: This method is required in each component. It examines this.props and this.state and returns one of the following types: React elements, Arrays and fragments, Portals, String and numbers, Booleans or null.
- `getSnapshotBeforeUpdate()`: This method is called right before the most recently rendered output is committed to the DOM. It enables your component to capture some information from the DOM (e.g., scroll position) before it is potentially changed.
- `componentDidUpdate()`: This method is invoked immediately after updating occurs. This method is not called for the initial render.

## Unmounting

This is the final phase of a component's lifecycle. It happens when the component is being removed from the DOM. It has one built-in method:

- `componentWillUnmount()`: This method is called immediately before a component is destroyed and unmounted permanently. This is the time to perform any necessary cleanup, such as invalidating timers, canceling network requests, or cleaning up any subscriptions that were created in `componentDidMount()`.

## Error Handling

This phase deals with how the component handles any errors that occur during rendering, in a lifecycle method, or in the constructor of any child component. React provides two lifecycle methods for error handling:

- `static getDerivedStateFromError()`: This method is called during the "render" phase, thus no side-effects are permitted. It catches errors that are thrown from component's ancestors during rendering, in lifecycle methods, and constructors. It should return a value to update state.
- `componentDidCatch()`: This method is called during the "commit" phase, therefore side-effects are permitted. It catches errors thrown in the component tree but cannot catch errors thrown in event handlers. This is where you can handle side-effects caused by errors.

## Mounting Example

```jsx
class MountingExample extends React.Component {
  constructor(props) {
    super(props);
    this.state = { name: 'John' };
  }

  static getDerivedStateFromProps(props, state) {
    return {name: props.name};
  }

  render() {
    return <h1>Hello {this.state.name}</h1>;
  }

  componentDidMount() {
    console.log('Component mounted');
  }
}

```

## Updating Example

```jsx
class UpdatingExample extends React.Component {
  constructor(props) {
    super(props);
    this.state = { name: 'John' };
  }

  static getDerivedStateFromProps(props, state) {
    return {name: props.name};
  }

  shouldComponentUpdate(nextProps, nextState) {
    return nextState.name !== this.state.name;
  }

  render() {
    return <h1>Hello {this.state.name}</h1>;
  }

  getSnapshotBeforeUpdate(prevProps, prevState) {
    return 'Snapshot!';
  }

  componentDidUpdate(prevProps, prevState, snapshot) {
    console.log('Component updated', snapshot);
  }
}

```

## Unmounting Example

```jsx
class UnmountingExample extends React.Component {
  componentWillUnmount() {
    console.log('Component will unmount');
  }

  render() {
    return <h1>Hello World</h1>;
  }
}

```

## Error Handling Example

```jsx
class ErrorHandlingExample extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.log('Error caught: ', error, info);
  }

  render() {
    if (this.state.hasError) {
      return <h1>Something went wrong</h1>;
    }
    return this.props.children;
  }
}

```