#include "can_bitrate.h"

#include <stddef.h>

/*
 * bxCAN bit rate = 36 MHz / (prescaler * (1 + BS1 + BS2)).
 * S0..S6 and S8 use 18 time quanta with an 88.9% sample point.  S7 uses
 * 15 time quanta with an 86.7% sample point.  Every entry is exact.
 */
static const can_bitrate_timing_t timings[] = {
    {'0',   10000u, 200u, 15u, 2u},
    {'1',   20000u, 100u, 15u, 2u},
    {'2',   50000u,  40u, 15u, 2u},
    {'3',  100000u,  20u, 15u, 2u},
    {'4',  125000u,  16u, 15u, 2u},
    {'5',  250000u,   8u, 15u, 2u},
    {'6',  500000u,   4u, 15u, 2u},
    {'7',  800000u,   3u, 12u, 2u},
    {'8', 1000000u,   2u, 15u, 2u},
};

const can_bitrate_timing_t *can_bitrate_from_code(char code)
{
    unsigned int index;

    if (code < '0' || code > '8')
    {
        return NULL;
    }
    index = (unsigned int)(code - '0');
    return &timings[index];
}

const can_bitrate_timing_t *can_bitrate_default(void)
{
    return can_bitrate_from_code('6');
}

can_bitrate_command_t can_bitrate_parse_command(
    const char *line,
    const can_bitrate_timing_t **timing)
{
    const can_bitrate_timing_t *selected;

    if (timing != NULL)
    {
        *timing = NULL;
    }
    if (line == NULL || line[0] != 'S')
    {
        return CAN_BITRATE_CMD_NOT_COMMAND;
    }
    if (line[1] == '?' && line[2] == '\0')
    {
        return CAN_BITRATE_CMD_QUERY;
    }
    if (line[1] == '\0' || line[2] != '\0')
    {
        return CAN_BITRATE_CMD_INVALID;
    }

    selected = can_bitrate_from_code(line[1]);
    if (selected == NULL)
    {
        return CAN_BITRATE_CMD_INVALID;
    }
    if (timing != NULL)
    {
        *timing = selected;
    }
    return CAN_BITRATE_CMD_SET;
}
