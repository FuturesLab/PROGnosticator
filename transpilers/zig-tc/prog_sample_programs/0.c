/* This program demonstrates the enumeration type definition in C. */

#include <stdlib.h>

enum Season { Spring, Summer, Autumn, Winter }; 

int func1() {
    enum Season s;
    s = Winter;
    return s;
}
