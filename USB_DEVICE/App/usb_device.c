#include "usb_device.h"

#include "main.h"
#include "usbd_cdc.h"
#include "usbd_cdc_if.h"
#include "usbd_core.h"
#include "usbd_desc.h"

USBD_HandleTypeDef hUsbDeviceFS;

void MX_USB_DEVICE_Init(void)
{
    if (USBD_Init(&hUsbDeviceFS, &VCP_Desc, 0u) != USBD_OK ||
        USBD_RegisterClass(&hUsbDeviceFS, USBD_CDC_CLASS) != USBD_OK ||
        USBD_CDC_RegisterInterface(&hUsbDeviceFS, &USBD_CDC_fops_FS) != USBD_OK ||
        USBD_Start(&hUsbDeviceFS) != USBD_OK)
    {
        Error_Handler();
    }
}
