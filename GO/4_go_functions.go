package main

import "fmt"

// Greet a person by name
func greet(name string) {
	fmt.Printf("Hello, %s!\n", name)
}

// Add two integers and return the result
func add(a, b int) int {
	return a + b
}

// Divide two numbers and return result or an error if division by zero
func divide(a, b float64) (float64, error) {
	if b == 0 {
		return 0, fmt.Errorf("cannot divide by zero")
	}
	return a / b, nil
}

// Calculate sum and product of two numbers (named return values)
func calculate(x, y int) (sum, product int) {
	sum = x + y
	product = x * y
	return // naked return
}

// Sum multiple numbers (variadic function)
func sum(numbers ...int) int {
	total := 0
	for _, num := range numbers {
		total += num
	}
	return total
}

// Apply a function (operation) to two integers
func applyOperation(a, b int, operation func(int, int) int) int {
	return operation(a, b)
}

func main() {
	// Call greet function
	greet("Alice")

	// Call add function
	result := add(5, 3)
	fmt.Println("5 + 3 =", result)

	// Call divide function
	quotient, err := divide(10, 2)
	if err != nil {
		fmt.Println("Error:", err)
	} else {
		fmt.Println("10 / 2 =", quotient)
	}

	// Call calculate function
	s, p := calculate(4, 5)
	fmt.Printf("Sum: %d, Product: %d\n", s, p)

	// Call sum function with multiple numbers
	total := sum(1, 2, 3, 4, 5)
	fmt.Println("Sum of 1,2,3,4,5 =", total)

	// Anonymous function to multiply two numbers
	multiply := func(a, b int) int {
		return a * b
	}

	// Use applyOperation with anonymous function
	result = applyOperation(6, 7, multiply)
	fmt.Println("6 * 7 =", result)
}
