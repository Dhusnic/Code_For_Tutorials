package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

func main() {
	reader := bufio.NewReader(os.Stdin)

	// 1️⃣ Age check (adult or minor)
	fmt.Print("Enter your age: ")
	ageStr, _ := reader.ReadString('\n')
	ageStr = strings.TrimSpace(ageStr)
	age, err := strconv.Atoi(ageStr)
	if err != nil {
		fmt.Println("Invalid input! Please enter a number.")
	} else {
		if age >= 18 {
			fmt.Println("You are an adult")
		} else {
			fmt.Println("You are a minor")
		}
	}

	// 2️⃣ Even or odd check
	fmt.Print("Enter a number: ")
	numStr, _ := reader.ReadString('\n')
	numStr = strings.TrimSpace(numStr)
	num, err := strconv.Atoi(numStr)
	if err != nil {
		fmt.Println("Invalid input! Please enter a number.")
	} else {
		if num%2 == 0 {
			fmt.Println("Number is even")
		} else {
			fmt.Println("Number is odd")
		}
	}

	// 3️⃣ Grade calculation
	fmt.Print("Enter your score: ")
	scoreStr, _ := reader.ReadString('\n')
	scoreStr = strings.TrimSpace(scoreStr)
	score, err := strconv.Atoi(scoreStr)
	if err != nil {
		fmt.Println("Invalid input! Please enter a number.")
	} else {
		if score >= 90 {
			fmt.Println("Grade: A")
		} else if score >= 80 {
			fmt.Println("Grade: B")
		} else if score >= 70 {
			fmt.Println("Grade: C")
		} else {
			fmt.Println("Grade: F")
		}
	}
}
