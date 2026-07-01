/* This program demonstrates the use of a volatile-qualified pointer to an array of structs */

#include <stddef.h>

struct example_struct {
    int a;
    float b;
    char c;
};

volatile struct example_struct (*ptr_to_array)[];
int func1() {
    struct example_struct example_array[10];
    ptr_to_array = &example_array;

    (*ptr_to_array)[0].a = 10;
    (*ptr_to_array)[1].b = 20.5;
    (*ptr_to_array)[9].c = 'z';

    return 0;
}
