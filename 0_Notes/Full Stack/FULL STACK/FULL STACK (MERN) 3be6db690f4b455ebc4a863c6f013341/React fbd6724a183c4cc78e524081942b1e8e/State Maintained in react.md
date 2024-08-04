# State Maintained in react

In React, state refers to a built-in object that a component can hold data in. This data can change over time and whenever this happens, React re-renders that component with the updated state data. Maintaining state in a React component involves initially setting the state with a default value when a component is created and then updating the state as needed when events occur, such as user interactions. This is done using the `useState` hook in functional components or the `setState` method in class components. It's important to note that state updates may be asynchronous, so it's recommended to use previous state when calculating the new state.

Sure, here are examples for each method:

1. **Local Component State:**

```jsx
import React, { useState } from 'react';

function MyComponent() {
  const [count, setCount] = useState(0);

  return (
    <div>
      <p>You clicked {count} times</p>
      <button onClick={() => setCount(count + 1)}>
        Click me
      </button>
    </div>
  );
}

```

In this example, we're using the `useState` hook to manage a count state in a functional component. When the button is clicked, the `setCount` function is called to update the state and the component is re-rendered with the new count.

1. **Context API:**

```jsx
import React, { useState, createContext, useContext } from 'react';

const CountContext = createContext();

function MyComponent() {
  const [count, setCount] = useState(0);

  return (
    <CountContext.Provider value={{ count, setCount }}>
      <ChildComponent />
    </CountContext.Provider>
  );
}

function ChildComponent() {
  const { count, setCount } = useContext(CountContext);

  return (
    <div>
      <p>You clicked {count} times</p>
      <button onClick={() => setCount(count + 1)}>
        Click me
      </button>
    </div>
  );
}

```

In this example, we're creating a context with `createContext` and using the `Provider` component to make the count state and `setCount` function available to the `ChildComponent`. Then in `ChildComponent`, we're using `useContext` to access the count state and `setCount` function.

1. **Redux:**

```jsx
import { createStore } from 'redux';

function counter(state = 0, action) {
  switch (action.type) {
    case 'INCREMENT':
      return state + 1;
    case 'DECREMENT':
      return state - 1;
    default:
      return state;
  }
}

let store = createStore(counter);

store.subscribe(() => console.log(store.getState()));

store.dispatch({ type: 'INCREMENT' });
store.dispatch({ type: 'INCREMENT' });
store.dispatch({ type: 'DECREMENT' });

```

In this Redux example, we're creating a store with a reducer function that handles `INCREMENT` and `DECREMENT` actions. When an action is dispatched with `store.dispatch`, the reducer processes the action and returns the new state.