#ifndef CAN_BITRATE_H
#define CAN_BITRATE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

typedef struct
{
    char code;
    uint32_t bitrate;
    uint16_t prescaler;
    uint8_t time_seg1_tq;
    uint8_t time_seg2_tq;
} can_bitrate_timing_t;

typedef enum
{
    CAN_BITRATE_CMD_NOT_COMMAND = 0,
    CAN_BITRATE_CMD_QUERY,
    CAN_BITRATE_CMD_SET,
    CAN_BITRATE_CMD_INVALID
} can_bitrate_command_t;

/* SLCAN-compatible S0..S8 bit-rate table for a 36 MHz CAN peripheral clock. */
const can_bitrate_timing_t *can_bitrate_from_code(char code);
const can_bitrate_timing_t *can_bitrate_default(void);

/* Parse an exact "S?" query or "S0".."S8" set command. */
can_bitrate_command_t can_bitrate_parse_command(
    const char *line,
    const can_bitrate_timing_t **timing);

#ifdef __cplusplus
}
#endif

#endif /* CAN_BITRATE_H */
