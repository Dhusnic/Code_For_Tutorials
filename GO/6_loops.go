package main

import "fmt"

func main() {
	// 1️⃣ Basic for loop: counting from 1 to 5
	fmt.Println("Counting 1 to 5:")
	for i := 1; i <= 5; i++ {
		fmt.Println(i)
	}

	// 2️⃣ While-like loop: countdown from 5
	fmt.Println("\nCountdown:")
	count := 5
	for count > 0 { // Go doesn't have 'while'; use for with a condition
		fmt.Println(count)
		count--
	}

	// 3️⃣ Infinite loop with break
	fmt.Println("\nInfinite loop with break:")
	i := 0
	for { // infinite loop
		if i >= 3 { // break when condition is met
			break
		}
		fmt.Println("Iteration:", i)
		i++
	}

	// 4️⃣ Continue statement: skip even numbers
	fmt.Println("\nSkipping even numbers:")
	for i := 1; i <= 10; i++ {
		if i%2 == 0 { // if number is even, skip to next iteration
			continue
		}
		fmt.Println(i)
	}

	// 5️⃣ Range loop: iterate over slices (arrays)
	numbers := []int{10, 20, 30, 40, 50}
	fmt.Println("\nUsing range:")
	for index, value := range numbers {
		fmt.Printf("Index: %d, Value: %d\n", index, value)
	}
}
