package main

import "fmt"

func demo() {
	// Variable declarations with explicit types
	var name string = "John"  // string
	var age int = 30          // integer
	var height float64 = 5.9  // decimal number
	var isStudent bool = true // boolean

	// Short variable declarations (Go infers the type automatically)
	city := "New York" // string
	score := 95.5      // float64

	// Multiple variable declarations
	var x, y, z int = 1, 2, 3 // integers in one line
	a, b := "Hello", "World"  // shorthand multiple assignment

	// Constants (values cannot be changed)
	const PI = 3.14159
	const greeting = "Welcome"

	// Printing all values (to avoid "declared and not used" error)
	fmt.Println("Name:", name)
	fmt.Println("Age:", age)
	fmt.Println("Height:", height)
	fmt.Println("Is Student:", isStudent)
	fmt.Println("City:", city)
	fmt.Println("Score:", score)
	fmt.Println("Coordinates:", x, y, z)
	fmt.Println("Words:", a, b)
	fmt.Println("PI:", PI)
	fmt.Println("Greeting:", greeting)
}

func main() {
	demo()
}
