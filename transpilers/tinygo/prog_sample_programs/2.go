// This program demonstrates the construct of comparing the lengths of two slices using len function.

package main

import "fmt"

func func1() int {
    slice1 := []int{1, 2, 3, 4, 5}
    slice2 := []int{6, 7, 8}

    len1 := len(slice1)
    len2 := len(slice2)

    if len1 > len2 {
        return 1
    } else if len1 < len2 {
        return -1
    }
    return 0
}

