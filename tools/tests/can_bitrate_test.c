#include <assert.h>
#include <stdio.h>

#include "can_bitrate.h"

int main(void)
{
    static const uint32_t expected_rates[] = {
        10000u, 20000u, 50000u, 100000u, 125000u,
        250000u, 500000u, 800000u, 1000000u
    };
    const can_bitrate_timing_t *timing;
    unsigned int i;

    for (i = 0u; i < sizeof expected_rates / sizeof expected_rates[0]; i++)
    {
        uint32_t total_tq;
        const char code = (char)('0' + i);

        timing = can_bitrate_from_code(code);
        assert(timing != NULL);
        assert(timing->code == code);
        assert(timing->bitrate == expected_rates[i]);
        total_tq = 1u + timing->time_seg1_tq + timing->time_seg2_tq;
        assert(36000000u / ((uint32_t)timing->prescaler * total_tq) == timing->bitrate);
    }

    assert(can_bitrate_from_code('/') == NULL);
    assert(can_bitrate_from_code('9') == NULL);
    assert(can_bitrate_default()->bitrate == 500000u);

    timing = NULL;
    assert(can_bitrate_parse_command("S?", &timing) == CAN_BITRATE_CMD_QUERY);
    assert(timing == NULL);
    assert(can_bitrate_parse_command("S4", &timing) == CAN_BITRATE_CMD_SET);
    assert(timing != NULL && timing->bitrate == 125000u);
    assert(can_bitrate_parse_command("S9", &timing) == CAN_BITRATE_CMD_INVALID);
    assert(can_bitrate_parse_command("S", &timing) == CAN_BITRATE_CMD_INVALID);
    assert(can_bitrate_parse_command("S60", &timing) == CAN_BITRATE_CMD_INVALID);
    assert(can_bitrate_parse_command("t1230", &timing) == CAN_BITRATE_CMD_NOT_COMMAND);
    assert(can_bitrate_parse_command(NULL, &timing) == CAN_BITRATE_CMD_NOT_COMMAND);

    puts("can_bitrate_test: ok");
    return 0;
}
