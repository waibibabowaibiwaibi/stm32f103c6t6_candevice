/**
 ******************************************************************************
 * @file    can_codec.h
 * @brief   SLCAN-style ASCII frame encode/decode for the USB<->CAN bridge.
 *
 * Wire format (see README_Converter.md):
 *   standard : 't' III L DD..      III = 3 hex ID digits, L = 1 decimal DLC
 *   extended : 'T' IIIIIIII L DD.. IIIIIIII = 8 hex ID digits
 *   remote   : same as above but 'r' / 'R', no data bytes
 *   status   : 'V' - replies with 'V' <rx> <tx> <drop> <err>
 *
 * Every length is checked against the identifier type before any data is
 * read, and the DLC is refused when it is outside 0..8.  This is the fix for
 * the out-of-bounds write into can_tx_data[8] that a frame such as "t1239"
 * used to trigger.
 ******************************************************************************
 */
#ifndef CAN_CODEC_H
#define CAN_CODEC_H

#include <stdint.h>

#define CAN_CODEC_MAX_DATA 8

/* Decode result. */
typedef enum
{
    CAN_DEC_OK = 0,       /* frame decoded into *frame                */
    CAN_DEC_NOT_FRAME,    /* not a t/T/r/R frame (ignore silently)    */
    CAN_DEC_BAD_DLC,      /* DLC outside 0..8                         */
    CAN_DEC_BAD_HEX,      /* malformed identifier or data digit       */
    CAN_DEC_BAD_LENGTH    /* payload length does not match the header */
} can_decode_result_t;

typedef struct
{
    uint32_t id;   /* 11-bit StdId or 29-bit ExtId */
    uint8_t  ext;  /* 1 = extended identifier      */
    uint8_t  rtr;  /* 1 = remote transmission request */
    uint8_t  dlc;  /* 0..8 */
    uint8_t  data[CAN_CODEC_MAX_DATA];
} can_frame_t;

/**
 * @brief  Decode one NUL-terminated ASCII frame.
 * @param  text  NUL-terminated command text (no CR/LF).
 * @param  frame receives the decoded frame on CAN_DEC_OK.
 * @retval see can_decode_result_t
 */
can_decode_result_t can_decode(const char *text, can_frame_t *frame);

/**
 * @brief  Encode a CAN frame as ASCII.
 * @param  out   destination, at least CAN_ENCODE_MAX bytes.
 * @param  frame frame to encode.
 * @retval number of characters written (never NUL-terminated)
 */
uint16_t can_encode(char *out, const can_frame_t *frame);

/* "T" + 8 hex + DLC digit + 16 data + '\r' + NUL */
#define CAN_ENCODE_MAX (1 + 8 + 1 + (CAN_CODEC_MAX_DATA * 2) + 1 + 1)

#endif /* CAN_CODEC_H */
