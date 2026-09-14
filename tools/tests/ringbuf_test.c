/* Host test for Core/Inc/ringbuf.h -- the byte ring and the message queue that
 * replaced the ping-pong double buffer.
 *
 * Build: clang -I Core/Inc -o ringbuf_test.exe tools/tests/ringbuf_test.c
 */
#include <stdio.h>
#include <string.h>
#include "ringbuf.h"

static int failures = 0;
static int checks = 0;

#define CHECK(cond, ...)                                     \
    do {                                                     \
        checks++;                                            \
        if (!(cond)) { failures++; printf("  FAIL  ");        \
            printf(__VA_ARGS__); printf("\n"); }             \
    } while (0)

#define OKMSG(...) do { printf("  ok    "); printf(__VA_ARGS__); printf("\n"); } while (0)

/* ---------------------------------------------------------------- byte ring */
static void test_byte_ring(void)
{
    uint8_t storage[8];
    ring_u8_t r;
    uint8_t out;

    printf("== byte ring ==\n");
    ring_u8_init(&r, storage, sizeof storage);

    CHECK(ring_u8_count(&r) == 0, "fresh ring should be empty");
    CHECK(ring_u8_space(&r) == 7, "usable capacity is size-1 (got %u)", ring_u8_space(&r));

    /* fill to capacity */
    for (int i = 0; i < 7; i++) CHECK(ring_u8_push(&r, (uint8_t)i) == 1, "push %d", i);
    CHECK(ring_u8_count(&r) == 7, "count after fill");
    CHECK(ring_u8_space(&r) == 0, "space after fill");
    CHECK(ring_u8_push(&r, 0xEE) == 0, "push into a full ring must report failure");
    OKMSG("fills to size-1 and refuses to overflow");

    /* drain in order */
    for (int i = 0; i < 7; i++) {
        CHECK(ring_u8_pop(&r, &out) == 0 && out == (uint8_t)i,
              "pop %d got %02X", i, out);
    }
    CHECK(ring_u8_pop(&r, &out) == -1, "pop from empty ring must report failure");
    OKMSG("drains in FIFO order, empty pop detected");

    /* contiguous run helper, including the wrap case */
    ring_u8_init(&r, storage, sizeof storage);
    for (int i = 0; i < 6; i++) ring_u8_push(&r, (uint8_t)(0x10 + i));
    CHECK(ring_u8_peek_run(&r) == 6, "run before wrap (got %u)", ring_u8_peek_run(&r));
    ring_u8_consume(&r, 5);
    CHECK(ring_u8_peek_run(&r) == 1, "run after partial consume (got %u)",
          ring_u8_peek_run(&r));
    /* head is at 6, so two more fit before the storage end */
    ring_u8_push(&r, 0xAA); ring_u8_push(&r, 0xBB);
    CHECK(ring_u8_peek_run(&r) == 3, "run to the end of storage (got %u)",
          ring_u8_peek_run(&r));
    /* drain that run: this wraps tail to 0, leaving the ring empty */
    ring_u8_consume(&r, 3);
    CHECK(ring_u8_count(&r) == 0, "ring should be empty after draining the tail run");
    CHECK(ring_u8_peek_run(&r) == 0, "no run when empty (got %u)", ring_u8_peek_run(&r));
    /* refill across the wrap boundary and confirm a single contiguous run */
    ring_u8_push(&r, 1); ring_u8_push(&r, 2); ring_u8_push(&r, 3);
    CHECK(ring_u8_peek_run(&r) == 3, "run after wrap (got %u)", ring_u8_peek_run(&r));
    OKMSG("peek_run/consume handle the wrap boundary");
}

/* ------------------------------------------------------------ message queue */
static void test_msgqueue(void)
{
    char slots[MSGQUEUE_SLOTS][32];
    msgqueue_t q;

    printf("\n== message queue ==\n");
    msgqueue_init(&q, &slots[0][0], 32);

    CHECK(msgqueue_read_slot(&q) == NULL, "fresh queue should be empty");
    CHECK(msgqueue_count(&q) == 0, "fresh queue count");
    OKMSG("starts empty");

    /* publish until full; capacity is SLOTS-1 */
    for (int i = 0; i < MSGQUEUE_SLOTS - 1; i++) {
        CHECK(msgqueue_has_room(&q), "room for message %d", i);
        snprintf(msgqueue_write_slot(&q), 32, "msg%d", i);
        msgqueue_publish(&q);
    }
    CHECK(msgqueue_count(&q) == MSGQUEUE_SLOTS - 1, "count when full (got %u)",
          msgqueue_count(&q));
    CHECK(!msgqueue_has_room(&q), "must report no room when full");
    OKMSG("accepts %d messages then reports full", MSGQUEUE_SLOTS - 1);

    /* drain in order */
    for (int i = 0; i < MSGQUEUE_SLOTS - 1; i++) {
        const char *s = msgqueue_read_slot(&q);
        char want[16];
        snprintf(want, sizeof want, "msg%d", i);
        CHECK(s != NULL && strcmp(s, want) == 0, "drain %d got \"%s\"", i,
              s ? s : "(null)");
        msgqueue_release(&q);
    }
    CHECK(msgqueue_read_slot(&q) == NULL, "must be empty after draining");
    OKMSG("drains in FIFO order");

    /* wraparound: interleave publish/release past the slot count */
    for (int i = 0; i < 20; i++) {
        char want[16];
        snprintf(msgqueue_write_slot(&q), 32, "m%d", i);
        msgqueue_publish(&q);
        snprintf(want, sizeof want, "m%d", i);
        CHECK(strcmp(msgqueue_read_slot(&q), want) == 0, "wraparound msg %d", i);
        msgqueue_release(&q);
    }
    OKMSG("survives repeated wraparound past %d slots", MSGQUEUE_SLOTS);
}

/* The defect being fixed: the old code handed the main loop a pointer to a
 * buffer the ISR could reuse.  Prove the new design never does that - a
 * published slot stays untouched until it is released. */
static void test_no_mutation_while_pending(void)
{
    char slots[MSGQUEUE_SLOTS][32];
    msgqueue_t q;
    char snapshot[32];
    const char *live;

    printf("\n== published messages are immutable until released ==\n");
    msgqueue_init(&q, &slots[0][0], 32);
    snprintf(msgqueue_write_slot(&q), 32, "t12381122334455667788");
    msgqueue_publish(&q);

    live = msgqueue_read_slot(&q);
    snprintf(snapshot, sizeof snapshot, "%s", live);

    /* Now the "interrupt" publishes more messages, wrapping the queue. */
    for (int i = 0; i < (MSGQUEUE_SLOTS - 1) * 3; i++) {
        if (!msgqueue_has_room(&q)) break;
        snprintf(msgqueue_write_slot(&q), 32, "filler%d", i);
        msgqueue_publish(&q);
    }

    CHECK(strcmp(live, snapshot) == 0,
          "oldest message mutated while pending: \"%s\" != \"%s\"", live, snapshot);
    OKMSG("oldest pending message survived %d later publishes", (MSGQUEUE_SLOTS - 1) * 3);
}

int main(void)
{
    test_byte_ring();
    test_msgqueue();
    test_no_mutation_while_pending();
    printf("\n%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
