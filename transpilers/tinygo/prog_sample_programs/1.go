// This program is exercising how to negate boolean expressions in constant declaration
package main

import "fmt"

const (
    isTrue = true
    isFalse = !isTrue
)

func func1() int {
    if isFalse {
        return 0
    }

    return 1
}
