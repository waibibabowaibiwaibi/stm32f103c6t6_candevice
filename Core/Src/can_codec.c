/**
 ******************************************************************************
 * @file    can_codec.c
 * @brief   SLCAN-style ASCII frame encode/decode.  See can_codec.h.
 ******************************************************************************
 */
#include "can_codec.h"

#define HEX_ID_DIGITS_STD 3u
#define HEX_ID_DIGITS_EXT 8u

#define ID_MAX_STD 0x7FFu        /* 11-bit standard identifier       */
#define ID_MAX_EXT 0x1FFFFFFFu   /* 29-bit extended identifier       */

static int hex_nibble(char c, uint8_t *out)
{
    if (c >= '0' && c <= '9') { *out = (uint8_t)(c - '0'); return 0; }
    if (c >= 'a' && c <= 'f') { *out = (uint8_t)(c - 'a' + 10); return 0; }
    if (c >= 'A' && c <= 'F') { *out = (uint8_t)(c - 'A' + 10); return 0; }
    return -1;
}

static char hex_digit(uint8_t v)
{
    if (v < 10u)
    {
        return (char)('0' + (int)v);
    }
    return (char)('A' + ((int)v - 10));
}

can_decode_result_t can_decode(const char *text, can_frame_t *frame)
{
    char kind;
    uint8_t id_digits;
    uint32_t id;
    uint32_t dlc;
    uint32_t header_len;
    uint32_t expect_len;
    uint32_t frame_len;
    uint32_t i;

    kind = text[0];

    if (kind == 't' || kind == 'r')
    {
        id_digits = HEX_ID_DIGITS_STD;
        frame->ext = 0u;
    }
    else if (kind == 'T' || kind == 'R')
    {
        id_digits = HEX_ID_DIGITS_EXT;
        frame->ext = 1u;
    }
    else
    {
        return CAN_DEC_NOT_FRAME;
    }

    frame->rtr = (kind == 'r' || kind == 'R') ? 1u : 0u;

    /* Total length of the string not counting an optional trailing CR/LF.
       Measuring it up front means a truncated frame is reported as a length
       error rather than being misdiagnosed as bad hex further down. */
    frame_len = 0u;
    while (text[frame_len] != '\0')
    {
        frame_len++;
    }
    if (frame_len > 0u && (text[frame_len - 1u] == '\r' || text[frame_len - 1u] == '\n'))
    {
        frame_len--;
    }

    /* --- identifier: exactly id_digits hex characters --- */
    header_len = 1u + id_digits;
    if (frame_len < header_len)
    {
        return CAN_DEC_BAD_LENGTH;
    }
    for (i = 0u, id = 0u; i < id_digits; i++)
    {
        uint8_t nibble;
        if (hex_nibble(text[1 + i], &nibble) != 0)
        {
            return CAN_DEC_BAD_HEX;
        }
        id = (id << 4) | nibble;
    }

    if (id > (frame->ext ? ID_MAX_EXT : ID_MAX_STD))
    {
        return CAN_DEC_BAD_HEX;
    }
    frame->id = id;

    /* --- DLC: exactly one decimal digit, and inside 0..8 --- */
    if (frame_len < header_len + 1u)
    {
        return CAN_DEC_BAD_LENGTH;
    }
    {
        char c = text[header_len];
        if (c < '0' || c > '9')
        {
            return CAN_DEC_BAD_HEX;
        }
        dlc = (uint32_t)(c - '0');
    }
    if (dlc > CAN_CODEC_MAX_DATA)
    {
        return CAN_DEC_BAD_DLC;
    }
    frame->dlc = (uint8_t)dlc;

    /* --- payload length must match exactly; remote frames carry none --- */
    expect_len = header_len + 1u + (frame->rtr ? 0u : (dlc * 2u));
    if (frame_len != expect_len)
    {
        return CAN_DEC_BAD_LENGTH;
    }

    /* --- payload --- */
    if (!frame->rtr)
    {
        for (i = 0u; i < dlc; i++)
        {
            uint8_t hi, lo;
            uint32_t at = header_len + 1u + (i * 2u);
            if (hex_nibble(text[at], &hi) != 0 ||
                hex_nibble(text[at + 1u], &lo) != 0)
            {
                return CAN_DEC_BAD_HEX;
            }
            frame->data[i] = (uint8_t)((hi << 4) | lo);
        }
    }

    /* Data beyond the DLC is left untouched; the transmit path only ever
       reads frame->data[0 .. dlc-1]. */
    return CAN_DEC_OK;
}

uint16_t can_encode(char *out, const can_frame_t *frame)
{
    uint16_t n = 0u;
    uint8_t i;

    if (frame->ext)
    {
        out[n++] = frame->rtr ? 'R' : 'T';
        for (i = 0u; i < 8u; i++)
        {
            out[n++] = hex_digit((uint8_t)((frame->id >> (4u * (7u - i))) & 0x0Fu));
        }
    }
    else
    {
        out[n++] = frame->rtr ? 'r' : 't';
        for (i = 0u; i < 3u; i++)
        {
            out[n++] = hex_digit((uint8_t)((frame->id >> (4u * (2u - i))) & 0x0Fu));
        }
    }

    out[n++] = (char)('0' + (frame->dlc > CAN_CODEC_MAX_DATA ? CAN_CODEC_MAX_DATA : frame->dlc));

    if (!frame->rtr)
    {
        for (i = 0u; i < frame->dlc && i < CAN_CODEC_MAX_DATA; i++)
        {
            out[n++] = hex_digit((uint8_t)(frame->data[i] >> 4));
            out[n++] = hex_digit((uint8_t)(frame->data[i] & 0x0Fu));
        }
    }

    out[n++] = '\r';
    return n;
}
