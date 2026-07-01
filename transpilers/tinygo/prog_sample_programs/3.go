// This program is exercising the construct of a for loop with early exit via goto in Go

package main

import "fmt"

func func1() int {
	var res int
	for i := 0; i <= 10; i++ {
		if i > 7 {
			goto Exit
		}
		res += i
	}

Exit:
	return res
}

