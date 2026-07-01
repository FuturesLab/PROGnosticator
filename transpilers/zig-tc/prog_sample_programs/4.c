/* 
 This program demonstrates the use of `volatile` on a struct field pointer, 
 nested compound literals in an array initializer, and `const` pointer to an 
 array of int.
*/

#include <stdlib.h>

typedef struct {
    volatile int *vp;  // `volatile` on struct field pointer
} vstruct;

const int array[3] = {1, 2, 3};  // `const` pointer to array of int

vstruct vs = { (int[]){1, 2, 3} };  // nested compound literals in array initializer

int func1() {
    int sum = 0;
    for(int i = 0; i < 3; i++) {
        sum += *(vs.vp + i) + *(array + i);
    }
    return sum;
}