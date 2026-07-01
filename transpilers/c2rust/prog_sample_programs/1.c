/*
 * C program demonstrating the construct 'nested for-loop with labeled break'.
 */ 

#include <stdlib.h>

int func1() {
    int i, j, result = 0;

    for(i = 0; i < 10; i++) {
        for(j = 0; j < 10; j++) {
            if(j == 5) {
                break;
            }
            result += i;
        }
        if(i == 5) {
            break;
        }
    }

    return result;
}
