/**
 ******************************************************************************
 * @file    ringbuf.h
 * @brief   Single-producer / single-consumer ring buffer.
 *
 * One writer and one reader only, which is exactly the pattern used here:
 *   - the CAN RX interrupt writes into the UART TX ring
 *   - the USART1 interrupt writes into the RX ring
 *   - the main loop reads both
 *
 * Each index has a single writer, so no locking is required beyond the fact
 * that reads and writes of the index variables are atomic (8-bit or 16-bit
 * aligned accesses on Cortex-M3).
 *
 * One slot is deliberately left unused so that "full" can be told apart from
 * "empty" without a separate count.
 ******************************************************************************
 */
#ifndef RINGBUF_H
#define RINGBUF_H

#include <stdint.h>

/* --------------------------------------------------------------------------
 * Byte ring buffer
 * ------------------------------------------------------------------------ */
typedef struct
{
    uint8_t *buf;
    uint16_t size;   /* capacity in bytes; usably size-1 */
    volatile uint16_t head; /* next write index */
    volatile uint16_t tail; /* next read index  */
} ring_u8_t;

static inline void ring_u8_init(ring_u8_t *r, uint8_t *storage, uint16_t size)
{
    r->buf = storage;
    r->size = size;
    r->head = 0;
    r->tail = 0;
}

static inline uint16_t ring_u8_count(const ring_u8_t *r)
{
    return (uint16_t)((r->head - r->tail) % r->size);
}

static inline uint16_t ring_u8_space(const ring_u8_t *r)
{
    return (uint16_t)(r->size - 1u - ring_u8_count(r));
}

/* Called from producer context only.  Returns 0 when the buffer is full. */
static inline int ring_u8_push(ring_u8_t *r, uint8_t b)
{
    uint16_t next = (uint16_t)((r->head + 1u) % r->size);
    if (next == r->tail)
    {
        return 0; /* full - caller decides whether to count the loss */
    }
    r->buf[r->head] = b;
    r->head = next;
    return 1;
}

/* Called from consumer context only.  Returns -1 when empty. */
static inline int ring_u8_pop(ring_u8_t *r, uint8_t *out)
{
    if (r->head == r->tail)
    {
        return -1;
    }
    *out = r->buf[r->tail];
    r->tail = (uint16_t)((r->tail + 1u) % r->size);
    return 0;
}

/* Contiguous run available for a single read, starting at tail.  Lets the
   consumer hand the UART a pointer instead of copying byte by byte. */
static inline uint16_t ring_u8_peek_run(const ring_u8_t *r)
{
    if (r->head >= r->tail)
    {
        return (uint16_t)(r->head - r->tail);
    }
    return (uint16_t)(r->size - r->tail);
}

/* Called from consumer context only.  Marks n bytes as consumed. */
static inline void ring_u8_consume(ring_u8_t *r, uint16_t n)
{
    r->tail = (uint16_t)((r->tail + n) % r->size);
}

/* --------------------------------------------------------------------------
 * Fixed-slot message queue (used for complete UART command lines)
 *
 * `head` and `tail` are slot indices in [0, slots).  Occupancy is derived from
 * them.  A message is only published by advancing `head` *after* the whole
 * payload has been written, which is what stops the consumer from ever
 * observing a half-written message - the defect the previous ping-pong
 * double buffer had.
 * ------------------------------------------------------------------------ */
#ifndef MSGQUEUE_SLOTS
#define MSGQUEUE_SLOTS 4
#endif

typedef struct
{
    char    *slots;  /* MSGQUEUE_SLOTS * MSGQUEUE_LEN bytes */
    uint16_t len;    /* bytes per slot */
    volatile uint8_t head; /* next slot to publish */
    volatile uint8_t tail; /* next slot to consume */
} msgqueue_t;

static inline void msgqueue_init(msgqueue_t *q, char *storage, uint16_t len)
{
    q->slots = storage;
    q->len = len;
    q->head = 0;
    q->tail = 0;
}

static inline uint8_t msgqueue_count(const msgqueue_t *q)
{
    return (uint8_t)((q->head - q->tail) % MSGQUEUE_SLOTS);
}

/* Producer: is there room to start writing into a fresh slot? */
static inline int msgqueue_has_room(const msgqueue_t *q)
{
    return msgqueue_count(q) < (MSGQUEUE_SLOTS - 1u);
}

/* Producer: pointer to the slot being filled. */
static inline char *msgqueue_write_slot(const msgqueue_t *q)
{
    return q->slots + ((uint16_t)q->head * q->len);
}

/* Producer: publish the slot once it is fully written.  Safe to call from an
   interrupt; this single store is what makes the message visible. */
static inline void msgqueue_publish(msgqueue_t *q)
{
    q->head = (uint8_t)((q->head + 1u) % MSGQUEUE_SLOTS);
}

/* Consumer: pointer to the oldest published slot, or NULL when empty. */
static inline const char *msgqueue_read_slot(const msgqueue_t *q)
{
    if (q->head == q->tail)
    {
        return 0;
    }
    return q->slots + ((uint16_t)q->tail * q->len);
}

/* Consumer: release the slot returned by msgqueue_read_slot(). */
static inline void msgqueue_release(msgqueue_t *q)
{
    q->tail = (uint8_t)((q->tail + 1u) % MSGQUEUE_SLOTS);
}

#endif /* RINGBUF_H */
