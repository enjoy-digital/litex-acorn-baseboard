// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <libbase/i2c.h>

#include <generated/csr.h>

/*-----------------------------------------------------------------------*/
/* Uart                                                                  */
/*-----------------------------------------------------------------------*/

static char *readstr(void)
{
	char c[2];
	static char s[64];
	static int ptr = 0;

	if(readchar_nonblock()) {
		c[0] = getchar();
		c[1] = 0;
		switch(c[0]) {
			case 0x7f:
			case 0x08:
				if(ptr > 0) {
					ptr--;
					fputs("\x08 \x08", stdout);
				}
				break;
			case 0x07:
				break;
			case '\r':
			case '\n':
				s[ptr] = 0x00;
				fputs("\n", stdout);
				ptr = 0;
				return s;
			default:
				if(ptr >= (sizeof(s) - 1))
					break;
				fputs(c, stdout);
				s[ptr] = c[0];
				ptr++;
				break;
		}
	}

	return NULL;
}

static char *get_token(char **str)
{
	char *c, *d;

	c = (char *)strchr(*str, ' ');
	if(c == NULL) {
		d = *str;
		*str = *str+strlen(*str);
		return d;
	}
	*c = 0;
	d = *str;
	*str = c+1;
	return d;
}

static void prompt(void)
{
	printf("\e[92;1mlitex-demo-app\e[0m> ");
}

/*-----------------------------------------------------------------------*/
/* Help                                                                  */
/*-----------------------------------------------------------------------*/

static void help(void)
{
	puts("\nLiteX lcd test app built "__DATE__" "__TIME__"\n");
	puts("Available commands:");
	puts("help               - Show this command");
	puts("reboot             - Reboot CPU");
	puts("lcd                - LCD test");
}

/*-----------------------------------------------------------------------*/
/* Commands                                                              */
/*-----------------------------------------------------------------------*/

static void reboot_cmd(void)
{
	ctrl_reset_write(1);
}

/* From https://github.com/uNetworking/SSD1306/blob/master/ssd1306_minimal.h */

unsigned char SSD1306_MINIMAL_framebuffer[1024];
#define SSD1306_MINIMAL_SLAVE_ADDR 0x3c

/* Transfers the entire framebuffer in 64 I2C data messages */
static void SSD1306_MINIMAL_transferFramebuffer(void) {
  unsigned char *p = SSD1306_MINIMAL_framebuffer;
  for (int i = 0; i < 64; i++) {
  		i2c_write(SSD1306_MINIMAL_SLAVE_ADDR, 0x40, p, 16);
  }
}

/* Horizontal addressing mode maps to linear framebuffer */
static void SSD1306_MINIMAL_setPixel(unsigned int x, unsigned int y) {
  x &= 0x7f;
  y &= 0x3f;
  SSD1306_MINIMAL_framebuffer[((y & 0xf8) << 4) + x] |= 1 << (y & 7);
}

const unsigned char lcd_init[] = {

	/* Enable charge pump regulator (RESET = ) */
	0x8d,
	0x14,
	/* Display On (RESET = ) */
	0xaf,
	/* Set Memory Addressing Mode to Horizontal Addressing Mode (RESET = Page Addressing Mode) */
	0x20,
	0x0,
	/* Reset Column Address (for horizontal addressing) */
	0x21,
	0,
	127,
	/* Reset Page Address (for horizontal addressing) */
	0x22,
	0,
	7
  };

static void lcd_cmd(void)
{
	int i;
	int x, y;

	/* LCD initialization */
	for (i = 0; i < sizeof(lcd_init); i++)
		i2c_write(SSD1306_MINIMAL_SLAVE_ADDR, 0x80, &lcd_init[i], 1);

	/* LCD test */

	/* Clear Framebuffer */
	for (int i = 0; i < 1024; i++) {
		SSD1306_MINIMAL_framebuffer[i] = 0;
	  }

	 for (x=0; x<64; x+=2) {
	 	for (y=0; y<16; y+=2) {
	  		SSD1306_MINIMAL_setPixel(x, y);
	  	}
	  }

	/* Transfer framebuffer to device */
	SSD1306_MINIMAL_transferFramebuffer();
}

/*-----------------------------------------------------------------------*/
/* Console service / Main                                                */
/*-----------------------------------------------------------------------*/

static void console_service(void)
{
	char *str;
	char *token;

	str = readstr();
	if(str == NULL) return;
	token = get_token(&str);
	if(strcmp(token, "help") == 0)
		help();
	else if(strcmp(token, "reboot") == 0)
		reboot_cmd();
	else if(strcmp(token, "lcd") == 0)
		lcd_cmd();
	prompt();
}

int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
	uart_init();

	help();
	prompt();

	while(1) {
		console_service();
	}

	return 0;
}
