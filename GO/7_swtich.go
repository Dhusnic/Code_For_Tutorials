package main

import (
	"fmt"
	"time"
)

func main() {
	// 1️⃣ Basic switch: check current weekday
	day := time.Now().Weekday()
	switch day {
	case time.Monday:
		fmt.Println("It's Monday")
	case time.Tuesday:
		fmt.Println("It's Tuesday")
	case time.Wednesday:
		fmt.Println("It's Wednesday")
	case time.Thursday:
		fmt.Println("It's Thursday")
	case time.Friday:
		fmt.Println("It's Friday")
	default: // if none of the above
		fmt.Println("It's weekend!")
	}

	// 2️⃣ Switch with multiple cases in one line
	grade := 'B'
	switch grade {
	case 'A', 'a':
		fmt.Println("Excellent!")
	case 'B', 'b':
		fmt.Println("Good job!")
	case 'C', 'c':
		fmt.Println("Not bad")
	default:
		fmt.Println("Need improvement")
	}

	// 3️⃣ Switch without an expression (acts like if-else)
	score := 85
	switch {
	case score >= 90:
		fmt.Println("Grade: A")
	case score >= 80:
		fmt.Println("Grade: B")
	case score >= 70:
		fmt.Println("Grade: C")
	default:
		fmt.Println("Grade: F")
	}
}
