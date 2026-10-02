#include <stdint.h>

__attribute__((noinline)) void mock_native_layer_three(void) {
    volatile uint64_t counter = 0;
    for (;;) {
        counter++;
    }
}

__attribute__((noinline)) void mock_native_layer_two(void) {
    mock_native_layer_three();
}

__attribute__((noinline)) void mock_native_layer_one(void) {
    mock_native_layer_two();
}

__attribute__((noinline)) void mock_infer_busy_loop(void) {
    mock_native_layer_one();
}
