/* Host test for Core/Src/can_codec.c
 * Build: clang -I Core/Inc -o can_codec_test.exe tools/tests/can_codec_test.c Core/Src/can_codec.c
 */
#include <stdio.h>
#include <string.h>
#include "can_codec.h"

static int failures = 0;
static int checks = 0;

static void expect_result(const char *text, can_decode_result_t want)
{
    can_frame_t f;
    can_decode_result_t got;
    memset(&f, 0, sizeof f);
    got = can_decode(text, &f);
    checks++;
    if (got != want)
    {
        failures++;
        printf("  FAIL  \"%s\" -> got %d, want %d\n", text, (int)got, (int)want);
    }
    else
    {
        printf("  ok    \"%s\" -> %d\n", text, (int)got);
    }
}

static void expect_frame(const char *text, uint32_t id, uint8_t ext, uint8_t dlc,
                         const uint8_t *data)
{
    can_frame_t f;
    memset(&f, 0, sizeof f);
    checks++;
    if (can_decode(text, &f) != CAN_DEC_OK)
    {
        failures++;
        printf("  FAIL  \"%s\" rejected but should decode\n", text);
        return;
    }
    if (f.id != id || f.ext != ext || f.dlc != dlc || f.rtr != 0)
    {
        failures++;
        printf("  FAIL  \"%s\" -> id=%X ext=%u dlc=%u (want %X/%u/%u)\n",
               text, f.id, f.ext, f.dlc, id, ext, dlc);
        return;
    }
    if (dlc && data && memcmp(f.data, data, dlc) != 0)
    {
        failures++;
        printf("  FAIL  \"%s\" data mismatch\n", text);
        return;
    }
    printf("  ok    \"%s\" -> id=%X ext=%u dlc=%u\n", text, f.id, f.ext, f.dlc);
}

static void roundtrip(const can_frame_t *in)
{
    char buf[CAN_ENCODE_MAX];
    can_frame_t out;
    uint16_t n;
    memset(&out, 0, sizeof out);
    n = can_encode(buf, in);
    buf[n] = '\0';
    checks++;
    if (can_decode(buf, &out) != CAN_DEC_OK)
    {
        failures++;
        printf("  FAIL  roundtrip: could not re-decode \"%s\"\n", buf);
        return;
    }
    if (out.id != in->id || out.ext != in->ext || out.dlc != in->dlc ||
        out.rtr != in->rtr || (in->dlc && memcmp(out.data, in->data, in->dlc) != 0))
    {
        failures++;
        printf("  FAIL  roundtrip mismatch on \"%s\"\n", buf);
        return;
    }
    printf("  ok    roundtrip \"%s\"\n", buf);
}

int main(void)
{
    printf("== well-formed frames ==\n");
    {
        const uint8_t d[8] = {0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88};
        expect_frame("t12381122334455667788", 0x123, 0, 8, d);
        expect_frame("t0008A0B0C0D0E0F00010", 0x000, 0, 8, (const uint8_t[]){0xA0,0xB0,0xC0,0xD0,0xE0,0xF0,0x00,0x10});
        expect_frame("T0000012381122334455667788", 0x123, 1, 8, d);
        expect_frame("t7FF0", 0x7FF, 0, 0, NULL);
        expect_frame("T1FFFFFFF0", 0x1FFFFFFF, 1, 0, NULL);
    }

    printf("\n== the reported overflow: DLC must be 0..8 ==\n");
    expect_result("t1239", CAN_DEC_BAD_DLC);
    expect_result("t1239AA", CAN_DEC_BAD_DLC);
    /* The README defines the DLC field as one decimal digit, so a hex letter
       is genuinely malformed there; either verdict is safe, and what matters
       is that it can never reach the data copy. */
    expect_result("t123F112233445566778899AABBCCDDEEFF", CAN_DEC_BAD_HEX);
    expect_result("T00000123F112233445566778899AABBCCDDEEFF", CAN_DEC_BAD_HEX);

    printf("\n== short / long frames ==\n");
    expect_result("t123811223344556677", CAN_DEC_BAD_LENGTH);      /* one byte short */
    expect_result("t1238112233445566778899", CAN_DEC_BAD_LENGTH);  /* one byte long  */
    expect_result("t123", CAN_DEC_BAD_LENGTH);
    expect_result("t1238", CAN_DEC_BAD_LENGTH);
    expect_result("t123", CAN_DEC_BAD_LENGTH);

    printf("\n== malformed identifiers ==\n");
    expect_result("t12G81122334455667788", CAN_DEC_BAD_HEX);
    expect_result("tZZZ81122334455667788", CAN_DEC_BAD_HEX);
    expect_result("t123x1122334455667788", CAN_DEC_BAD_HEX);
    expect_result("t1238112233445566778Z", CAN_DEC_BAD_HEX);

    printf("\n== non-frame input is ignored ==\n");
    expect_result("", CAN_DEC_NOT_FRAME);
    expect_result("X1238", CAN_DEC_NOT_FRAME);
    expect_result("hello", CAN_DEC_NOT_FRAME);
    expect_result("V", CAN_DEC_NOT_FRAME);
    expect_result("\r", CAN_DEC_NOT_FRAME);

    printf("\n== remote frames ==\n");
    {
        can_frame_t f;
        memset(&f, 0, sizeof f);
        checks++;
        if (can_decode("r1238", &f) != CAN_DEC_OK || f.rtr != 1 || f.dlc != 8 || f.id != 0x123)
        { failures++; printf("  FAIL  r1238\n"); }
        else printf("  ok    \"r1238\" -> rtr=%u id=%X dlc=%u\n", f.rtr, f.id, f.dlc);

        memset(&f, 0, sizeof f);
        checks++;
        if (can_decode("r123811", &f) != CAN_DEC_BAD_LENGTH)
        { failures++; printf("  FAIL  r123811 should have no payload\n"); }
        else printf("  ok    \"r123811\" -> rejected (no payload on remote frames)\n");
    }

    printf("\n== encode/decode roundtrip ==\n");
    {
        can_frame_t f;
        memset(&f, 0, sizeof f);
        f.id = 0x123; f.ext = 0; f.dlc = 8;
        for (int i = 0; i < 8; i++) f.data[i] = (uint8_t)(0xA0 + i);
        roundtrip(&f);

        memset(&f, 0, sizeof f);
        f.id = 0x1ABCDEF; f.ext = 1; f.dlc = 3;
        f.data[0] = 0xDE; f.data[1] = 0xAD; f.data[2] = 0xBE;
        roundtrip(&f);

        memset(&f, 0, sizeof f);
        f.id = 0x7FF; f.ext = 0; f.dlc = 0;
        roundtrip(&f);

        memset(&f, 0, sizeof f);
        f.id = 0x456; f.ext = 0; f.rtr = 1; f.dlc = 4;
        roundtrip(&f);
    }

    printf("\n== boundary identifiers ==\n");
    expect_result("t8000", CAN_DEC_BAD_HEX);        /* > 0x7FF for standard */
    expect_result("T200000000", CAN_DEC_BAD_HEX);   /* > 29 bits            */
    expect_frame("t7FF0", 0x7FF, 0, 0, NULL);
    expect_frame("T1FFFFFFF0", 0x1FFFFFFF, 1, 0, NULL);

    printf("\n%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
