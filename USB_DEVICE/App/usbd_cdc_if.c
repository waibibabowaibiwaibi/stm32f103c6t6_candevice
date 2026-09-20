#include "usbd_cdc_if.h"

#include "main.h"
#include "usb_device.h"

static uint8_t usb_rx_buffer[CDC_DATA_FS_OUT_PACKET_SIZE];

static USBD_CDC_LineCodingTypeDef line_coding = {
    115200u,
    0u,
    0u,
    8u
};

static int8_t CDC_Init_FS(void);
static int8_t CDC_DeInit_FS(void);
static int8_t CDC_Control_FS(uint8_t command, uint8_t *buffer, uint16_t length);
static int8_t CDC_Receive_FS(uint8_t *buffer, uint32_t *length);

USBD_CDC_ItfTypeDef USBD_CDC_fops_FS = {
    CDC_Init_FS,
    CDC_DeInit_FS,
    CDC_Control_FS,
    CDC_Receive_FS
};

static int8_t CDC_Init_FS(void)
{
    (void)USBD_CDC_SetTxBuffer(&hUsbDeviceFS, NULL, 0u);
    (void)USBD_CDC_SetRxBuffer(&hUsbDeviceFS, usb_rx_buffer);
    return (int8_t)USBD_OK;
}

static int8_t CDC_DeInit_FS(void)
{
    return (int8_t)USBD_OK;
}

static int8_t CDC_Control_FS(uint8_t command, uint8_t *buffer, uint16_t length)
{
    if (command == CDC_SET_LINE_CODING && length >= 7u)
    {
        line_coding.bitrate = (uint32_t)buffer[0]
                            | ((uint32_t)buffer[1] << 8)
                            | ((uint32_t)buffer[2] << 16)
                            | ((uint32_t)buffer[3] << 24);
        line_coding.format = buffer[4];
        line_coding.paritytype = buffer[5];
        line_coding.datatype = buffer[6];
    }
    else if (command == CDC_GET_LINE_CODING && length >= 7u)
    {
        buffer[0] = (uint8_t)line_coding.bitrate;
        buffer[1] = (uint8_t)(line_coding.bitrate >> 8);
        buffer[2] = (uint8_t)(line_coding.bitrate >> 16);
        buffer[3] = (uint8_t)(line_coding.bitrate >> 24);
        buffer[4] = line_coding.format;
        buffer[5] = line_coding.paritytype;
        buffer[6] = line_coding.datatype;
    }

    return (int8_t)USBD_OK;
}

static int8_t CDC_Receive_FS(uint8_t *buffer, uint32_t *length)
{
    Bridge_ReceiveBytes(buffer, *length);
    (void)USBD_CDC_SetRxBuffer(&hUsbDeviceFS, usb_rx_buffer);
    (void)USBD_CDC_ReceivePacket(&hUsbDeviceFS);
    return (int8_t)USBD_OK;
}

uint8_t CDC_Transmit_FS(uint8_t *buffer, uint16_t length)
{
    if (hUsbDeviceFS.pClassData == NULL)
    {
        return USBD_BUSY;
    }

    (void)USBD_CDC_SetTxBuffer(&hUsbDeviceFS, buffer, length);
    return USBD_CDC_TransmitPacket(&hUsbDeviceFS);
}

uint8_t CDC_TxBusy_FS(void)
{
    USBD_CDC_HandleTypeDef *cdc;

    if (hUsbDeviceFS.pClassData == NULL)
    {
        return 1u;
    }

    cdc = (USBD_CDC_HandleTypeDef *)hUsbDeviceFS.pClassData;
    return cdc->TxState != 0u ? 1u : 0u;
}
