package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

func main() {
	// Create a new buffered reader to read from standard input (keyboard)
	reader := bufio.NewReader(os.Stdin)

	// Reading string input
	fmt.Print("Enter your name: ")
	name, _ := reader.ReadString('\n') // read until Enter is pressed
	name = strings.TrimSpace(name)     // remove newline/spaces

	// Reading integer input
	fmt.Print("Enter your age: ")
	ageStr, _ := reader.ReadString('\n') // read as string
	ageStr = strings.TrimSpace(ageStr)
	age, err := strconv.Atoi(ageStr) // convert string → int
	if err != nil {
		fmt.Println("❌ Invalid age entered")
		return
	}

	// Formatted output
	fmt.Printf("Hello %s, you are %d years old.\n", name, age)
	fmt.Fprintf(os.Stdout, "✅ Welcome to Go programming!\n")
}
