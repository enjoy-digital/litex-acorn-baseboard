#include <i2c.h>
#include "i2c_spi.h"

#define MAX_BUFFER 200


bool i2c_spi_write(uint8_t ss, uint8_t *data, unsigned len)
{
    bool ret;
    unsigned current_len = MAX_BUFFER;
    for (; len > 0;)
    {
        if (len < MAX_BUFFER)
            current_len = len;
        ret = i2c_write(I2C_ADDR, ss, data, current_len);
        if (!ret)
            return ret;
        len -= current_len;
        data += current_len;
    }
    return ret;
}


bool i2c_spi_read(uint8_t ss, uint8_t *data, unsigned len)
{
    for (unsigned timeout = 100; timeout > 0; timeout --)
    {
        if (i2c_read(I2C_ADDR, ss, data, len, true))
            return true;
    }
    return false;
}


