// This program demonstrates the use of composite struct literal within function argument

package main

import "fmt"

type Person struct {
	Name string
	Age  int
}

func findAge(p Person) int {
	return p.Age
}

func func1() int {
	age := findAge(Person{Name: "John", Age: 30})
	return age
}

