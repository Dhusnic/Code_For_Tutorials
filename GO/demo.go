package main

import "fmt"

// Simple program that prints and reads input.
func main() {
	fmt.Println("Hello, World!")
	fmt.Println("Dhusnic")

	var a, b int
	fmt.Print("Enter first number: ")
	fmt.Scanf("%d", &a) // %d for integer
	fmt.Print("Enter second number: ")
	fmt.Scanf("%d", &b)

	fmt.Println("You entered a =", a, "and b =", b)

	// Example addition
	fmt.Println("Sum:", a+b)
}
