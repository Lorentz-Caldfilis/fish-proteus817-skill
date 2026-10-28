/* Original minimal fixture. STM32F103: PA0 input -> PA5 output.
 * Register definitions follow ST RM0008, GPIO and RCC chapters.
 * No vendor firmware or library is included. SPDX-License-Identifier: MIT
 */
typedef unsigned int u32;
#define REG32(address) (*(volatile u32 *)(address))
#define RCC_APB2ENR REG32(0x40021018u)
#define GPIOA_CRL   REG32(0x40010800u)
#define GPIOA_IDR   REG32(0x40010808u)
#define GPIOA_BSRR  REG32(0x40010810u)

int main(void)
{
    u32 previous = 2u;
    RCC_APB2ENR |= 1u << 2;  /* IOPAEN; reset HSI remains the clock source. */
    (void)RCC_APB2ENR;
    GPIOA_BSRR = (1u << 16) | (1u << 21); /* PA0 pull-down, PA5 initially low. */
    GPIOA_CRL = (GPIOA_CRL & ~0x00f0000fu) | 0x00200008u;
    for (;;) {
        const u32 state = GPIOA_IDR & 1u;
        if (state != previous) {
            GPIOA_BSRR = state ? (1u << 5) : (1u << 21);
            previous = state;
        }
    }
}
