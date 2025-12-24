package main

import "fmt"

func main() {
	// Signed integer types
	var i8 int8 = 127                   // 8-bit integer (-128 to 127)
	var i16 int16 = 32767               // 16-bit integer (-32,768 to 32,767)
	var i32 int32 = 2147483647          // 32-bit integer (-2,147,483,648 to 2,147,483,647)
	var i64 int64 = 9223372036854775807 // 64-bit integer (-2^63 to 2^63-1)

	// Unsigned integer
	var ui uint = 42 // uint depends on system (32-bit or 64-bit)

	// Floating-point types
	var f32 float32 = 3.14              // 32-bit float
	var f64 float64 = 3.141592653589793 // 64-bit float (default in Go)

	// String and boolean
	var text string = "Hello, Go!"
	var flag bool = true

	// Type conversion
	var num int = 42                              // integer
	var floatNum float64 = float64(num)           // int → float64
	var stringNum string = fmt.Sprintf("%d", num) // int → string using Sprintf

	// Printing values
	fmt.Println("Int8:", i8)
	fmt.Println("Int16:", i16)
	fmt.Println("Int32:", i32)
	fmt.Println("Int64:", i64)
	fmt.Println("Unsigned Int:", ui)
	fmt.Println("Float32:", f32)
	fmt.Println("Float64:", f64)
	fmt.Println("String:", text)
	fmt.Println("Boolean:", flag)
	fmt.Println("Converted Float:", floatNum)
	fmt.Println("Converted String:", stringNum)

	// Using formatted output
	fmt.Printf("\nFormatted -> Integer: %d, Float: %.2f\n", num, floatNum)
	fmt.Printf("Formatted -> String: %s, Boolean: %t\n", text, flag)
}
