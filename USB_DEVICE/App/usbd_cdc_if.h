#ifndef USBD_CDC_IF_H
#define USBD_CDC_IF_H

#ifdef __cplusplus
extern "C" {
#endif

#include "usbd_cdc.h"

extern USBD_CDC_ItfTypeDef USBD_CDC_fops_FS;

uint8_t CDC_Transmit_FS(uint8_t *buffer, uint16_t length);
uint8_t CDC_TxBusy_FS(void);

#ifdef __cplusplus
}
#endif

#endif /* USBD_CDC_IF_H */
