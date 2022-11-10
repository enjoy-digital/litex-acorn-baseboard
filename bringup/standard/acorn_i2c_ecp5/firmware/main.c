#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <generated/csr.h>
#include <i2c.h>
#include "i2c_spi.h"


int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
    irq_setmask(0);
    irq_setie(1);
#endif
    uart_init();

    uint8_t d;
    bool ret = i2c_read(I2C_ADDR, GPIO_READ, &d, 1, true);
    printf("%d %d\n", ret, d);

    d = 0b0010;
    ret = i2c_write(I2C_ADDR, GPIO_ENABLE, &d, 1);
    if (!ret)
        printf("%d\n", ret);

    d = 0b00000100;
    ret = i2c_write(I2C_ADDR, GPIO_CONFIG, &d, 1);
    if (!ret)
        printf("%d\n", ret);

    d = 0b0010;
    ret = i2c_write(I2C_ADDR, GPIO_WRITE, &d, 1);
    if (!ret)
        printf("%d\n", ret);

    d = 0;
    ret = i2c_write(I2C_ADDR, CONFIG_SPI, &d, 1);
    if (!ret)
        printf("%d\n", ret);

    // read spi flash id
    uint8_t data[] = {0x9f, 0, 0, 0};
    ret = i2c_spi_write(1, data, sizeof(data));
    if (!ret)
        printf("%d\n", ret);
    ret = i2c_spi_read(1, data, sizeof(data));
    printf("%d %d %d %d %d\n", ret, data[0], data[1], data[2], data[3]);

    while(1) {
        busy_wait_us(1000 * 1000);
    }

    return 0;
}
