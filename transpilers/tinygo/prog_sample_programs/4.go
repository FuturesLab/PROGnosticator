// This program demonstrates: cast from *struct to interface{} via assignment, closure inside loop capturing loop variable properly,
// interface method invoked from within a method of embedding type
package main

import (
	"fmt"
)

type MyInterface interface {
	myMethod() int
}

type MyStruct struct {
	number int
}

type MyEmbeddingType struct {
	MyInterface
}

func (ms *MyStruct) myMethod() int {
	return ms.number
}

func (met *MyEmbeddingType) callMyMethod() {
	fmt.Println(met.myMethod())
}

func func1() int {
	myStruct := &MyStruct{number: 10}
	var i MyInterface = myStruct

	numbers := []int{2, 3, 4}
	for _, num := range numbers {
		func(num int) {
			i = &MyStruct{number: i.myMethod() * num}
		}(num)
	}

	// Embedding type used
	embeddingType := &MyEmbeddingType{i}
	embeddingType.callMyMethod()

	return i.myMethod()
}

