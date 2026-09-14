/* USER CODE BEGIN Header */
/**
 ******************************************************************************
 * @file           : main.c
 * @brief          : Main program body
 ******************************************************************************
 * @attention
 *
 * Copyright (c) 2025 STMicroelectronics.
 * All rights reserved.
 *
 * This software is licensed under terms that can be found in the LICENSE file
 * in the root directory of this software component.
 * If no LICENSE file comes with this software, it is provided AS-IS.
 *
 ******************************************************************************
 */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>

#include "can_bitrate.h"
#include "can_codec.h"
#include "ringbuf.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
/* Longest legal frame is "T" + 8 hex id + dlc + 16 hex data = 26 characters;
   64 leaves generous room for a host that pads or adds trailing whitespace. */
#define UART_LINE_MAX 64
#define UART_LINE_SLOTS 4

#define UART_TX_BUF_SIZE 512

#define CAN_TX_TIMEOUT_MS 10u
#define CAN_UART_TX_CHUNK 32u
/* How often the main loop looks at the controller error state. */
#define CAN_ERROR_POLL_MS 20u
/* Back-off between bus-off recovery attempts. */
#define CAN_RECOVER_INTERVAL_MS 1000u
/* PC13 is active-low on common STM32F103 "Blue Pill" boards.  Stretch each
   activity event so it is visible without ever delaying CAN/UART handling. */
#define LED_ACTIVITY_HOLD_MS 35u
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
CAN_HandleTypeDef hcan;

UART_HandleTypeDef huart1;

/* USER CODE BEGIN PV */
/* ---- UART receive: line assembly + published-message queue ---------------- */
static char uart_line_slots[UART_LINE_SLOTS][UART_LINE_MAX];
static msgqueue_t uart_rxq;
static uint16_t uart_rx_idx;   /* bytes assembled into the current slot */
static uint8_t uart_rx_byte;   /* HAL_UART_Receive_IT landing byte      */

/* ---- UART transmit: ring buffer drained by the main loop ------------------ */
static uint8_t uart_tx_buf[UART_TX_BUF_SIZE];
static ring_u8_t uart_txq;

/* ---- Counters, readable with the 'V' status command ----------------------- */
static volatile uint32_t stat_can_rx;      /* frames forwarded CAN -> UART   */
static volatile uint32_t stat_can_tx;      /* frames accepted UART -> CAN    */
static volatile uint32_t stat_uart_drop;   /* bytes dropped, UART TX full    */
static volatile uint32_t stat_cmd_drop;    /* command lines dropped/overflow */
static volatile uint32_t stat_cmd_bad;     /* malformed command lines        */
static volatile uint32_t stat_can_tx_drop; /* no free CAN mailbox            */
static volatile uint32_t stat_uart_err;    /* USART1 error callbacks         */
static volatile uint32_t stat_can_recover; /* successful bus-off recoveries  */

static uint32_t can_last_error_poll;
static uint32_t can_last_recover;
static const can_bitrate_timing_t *can_active_bitrate;
static volatile uint8_t led_activity_requested;
static uint8_t led_activity_on;
static uint32_t led_activity_deadline;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_CAN_Init(void);
/* USER CODE BEGIN PFP */
static HAL_StatusTypeDef CAN_ApplyFilterConfig(void);
static HAL_StatusTypeDef CAN_StartWithFilter(void);
static HAL_StatusTypeDef CAN_ReconfigureBitrate(const can_bitrate_timing_t *timing);
static void CAN_ServiceErrors(void);
static void UART_TxService(void);
static void HandleCommand(const char *line);
static void UART_QueueBytes(const char *data, uint16_t len);
static void UART_ReplyBitrate(void);
static void LED_RequestActivity(void);
static void LED_Service(void);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
static HAL_StatusTypeDef CAN_ApplyFilterConfig(void)
{
    CAN_FilterTypeDef filterConfig;

    filterConfig.FilterBank           = 0;
    filterConfig.FilterMode           = CAN_FILTERMODE_IDMASK;
    filterConfig.FilterScale          = CAN_FILTERSCALE_32BIT;
    filterConfig.FilterIdHigh         = 0x0000;
    filterConfig.FilterIdLow          = 0x0000;
    filterConfig.FilterMaskIdHigh     = 0x0000;   /* mask 0 = accept everything */
    filterConfig.FilterMaskIdLow      = 0x0000;
    filterConfig.FilterFIFOAssignment = CAN_FILTER_FIFO0;
    filterConfig.FilterActivation     = ENABLE;
    filterConfig.SlaveStartFilterBank = 14;       /* unused: single CAN instance */

    return HAL_CAN_ConfigFilter(&hcan, &filterConfig);
}

/* Start (or restart) the controller.  HAL_CAN_Stop() deactivates the filter
   banks, so the filter has to be reprogrammed on every restart - that is what
   the bus-off recovery path relies on. */
static HAL_StatusTypeDef CAN_StartWithFilter(void)
{
    if (CAN_ApplyFilterConfig() != HAL_OK || HAL_CAN_Start(&hcan) != HAL_OK)
    {
        return HAL_ERROR;
    }
    return HAL_CAN_ActivateNotification(&hcan,
                                        CAN_IT_RX_FIFO0_MSG_PENDING |
                                        CAN_IT_ERROR |
                                        CAN_IT_BUSOFF);
}

static uint32_t CAN_TimeSeg1Constant(uint8_t time_quanta)
{
    switch (time_quanta)
    {
        case 12u: return CAN_BS1_12TQ;
        case 15u: return CAN_BS1_15TQ;
        default:  return 0u;
    }
}

static uint32_t CAN_TimeSeg2Constant(uint8_t time_quanta)
{
    return time_quanta == 2u ? CAN_BS2_2TQ : 0u;
}

/* Stop bxCAN, update BTR through HAL_CAN_Init(), then restore the filter,
   notifications and normal operation.  If the new configuration cannot be
   started, put the previous configuration back before reporting failure. */
static HAL_StatusTypeDef CAN_ReconfigureBitrate(const can_bitrate_timing_t *timing)
{
    CAN_InitTypeDef previous_init;
    const can_bitrate_timing_t *previous_bitrate = can_active_bitrate;
    uint32_t time_seg1;
    uint32_t time_seg2;

    if (timing == NULL)
    {
        return HAL_ERROR;
    }
    if (can_active_bitrate == timing)
    {
        return HAL_OK;
    }

    time_seg1 = CAN_TimeSeg1Constant(timing->time_seg1_tq);
    time_seg2 = CAN_TimeSeg2Constant(timing->time_seg2_tq);
    if (time_seg1 == 0u || time_seg2 == 0u)
    {
        return HAL_ERROR;
    }
    if (HAL_CAN_Stop(&hcan) != HAL_OK)
    {
        return HAL_ERROR;
    }

    previous_init = hcan.Init;
    hcan.Init.Prescaler = timing->prescaler;
    hcan.Init.TimeSeg1 = time_seg1;
    hcan.Init.TimeSeg2 = time_seg2;
    if (HAL_CAN_Init(&hcan) == HAL_OK && CAN_StartWithFilter() == HAL_OK)
    {
        hcan.ErrorCode = HAL_CAN_ERROR_NONE;
        can_active_bitrate = timing;
        return HAL_OK;
    }

    /* A failed change must not strand the device at a half-applied rate. */
    (void)HAL_CAN_Stop(&hcan);
    hcan.Init = previous_init;
    if (HAL_CAN_Init(&hcan) == HAL_OK && CAN_StartWithFilter() == HAL_OK)
    {
        hcan.ErrorCode = HAL_CAN_ERROR_NONE;
    }
    can_active_bitrate = previous_bitrate;
    return HAL_ERROR;
}

/* Bring the controller back after it dropped off the bus.  Without this the
   node stays silent until someone power-cycles it. */
static void CAN_ServiceErrors(void)
{
    uint32_t now = HAL_GetTick();
    uint32_t err;

    if ((now - can_last_error_poll) < CAN_ERROR_POLL_MS)
    {
        return;
    }
    can_last_error_poll = now;

    err = HAL_CAN_GetError(&hcan);
    if (err == HAL_CAN_ERROR_NONE)
    {
        return;
    }
    if ((err & HAL_CAN_ERROR_BOF) == 0u)
    {
        /* Warning / error-passive only: the controller keeps working. */
        return;
    }
    if ((now - can_last_recover) < CAN_RECOVER_INTERVAL_MS)
    {
        return;
    }
    can_last_recover = now;

    if (HAL_CAN_Stop(&hcan) != HAL_OK)
    {
        return;
    }
    __HAL_CAN_CLEAR_FLAG(&hcan, CAN_FLAG_ERRI);
    hcan.ErrorCode = HAL_CAN_ERROR_NONE;

    if (CAN_StartWithFilter() == HAL_OK)
    {
        stat_can_recover++;
    }
}

/* Push as much of the CAN->UART backlog out of the door as fits in one go.
   HAL_UART_Transmit() can return early on timeout, so the read pointer is
   advanced only when the whole run went out - a short write leaves the
   remaining bytes queued for the next pass instead of losing them. */
static void UART_TxService(void)
{
    uint16_t run = ring_u8_peek_run(&uart_txq);

    if (run == 0u)
    {
        return;
    }
    if (run > CAN_UART_TX_CHUNK)
    {
        run = CAN_UART_TX_CHUNK;
    }

    if (HAL_UART_Transmit(&huart1, &uart_tx_buf[uart_txq.tail], run,
                          CAN_TX_TIMEOUT_MS) == HAL_OK)
    {
        ring_u8_consume(&uart_txq, run);
    }
}

static void UART_QueueBytes(const char *data, uint16_t len)
{
    uint16_t i;

    for (i = 0u; i < len; i++)
    {
        if (!ring_u8_push(&uart_txq, (uint8_t)data[i]))
        {
            stat_uart_drop++;
            return;
        }
    }
}

/* Interrupt callbacks only set a byte flag.  The main loop performs the GPIO
   writes and extends the visible pulse, so no delay or HAL GPIO call is added
   to the CAN receive interrupt. */
static void LED_RequestActivity(void)
{
    led_activity_requested = 1u;
}

static void LED_Service(void)
{
    uint32_t now = HAL_GetTick();

    if (led_activity_requested != 0u)
    {
        led_activity_requested = 0u;
        led_activity_on = 1u;
        led_activity_deadline = now + LED_ACTIVITY_HOLD_MS;
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);
    }
    else if (led_activity_on != 0u &&
             (int32_t)(now - led_activity_deadline) >= 0)
    {
        led_activity_on = 0u;
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
    }
}

static void UART_ReplyBitrate(void)
{
    char reply[20];
    const can_bitrate_timing_t *active = can_active_bitrate;
    int n;

    if (active == NULL)
    {
        active = can_bitrate_default();
    }
    n = snprintf(reply, sizeof reply, "S %lu\r", (unsigned long)active->bitrate);
    if (n > 0)
    {
        UART_QueueBytes(reply, (uint16_t)n);
    }
}

static void HandleCommand(const char *line)
{
    can_frame_t frame;
    can_decode_result_t result;
    const can_bitrate_timing_t *requested_bitrate;
    can_bitrate_command_t bitrate_command;

    bitrate_command = can_bitrate_parse_command(line, &requested_bitrate);
    if (bitrate_command == CAN_BITRATE_CMD_QUERY)
    {
        UART_ReplyBitrate();
        return;
    }
    if (bitrate_command == CAN_BITRATE_CMD_SET)
    {
        if (CAN_ReconfigureBitrate(requested_bitrate) == HAL_OK)
        {
            UART_ReplyBitrate();
        }
        else
        {
            UART_QueueBytes("E S\r", 4u);
        }
        return;
    }
    if (bitrate_command == CAN_BITRATE_CMD_INVALID)
    {
        stat_cmd_bad++;
        UART_QueueBytes("E S\r", 4u);
        return;
    }

    /* Keep-alive / identification, so a host can confirm the bridge is alive
       and see whether anything is being dropped. */
    if (line[0] == 'V' && line[1] == '\0')
    {
        char reply[96];
        int n = snprintf(reply, sizeof reply, "V %lu %lu %lu %lu %lu %lu %lu %lu\r",
                         (unsigned long)stat_can_rx,
                         (unsigned long)stat_can_tx,
                         (unsigned long)stat_uart_drop,
                         (unsigned long)stat_cmd_drop,
                         (unsigned long)stat_cmd_bad,
                         (unsigned long)stat_can_tx_drop,
                         (unsigned long)stat_uart_err,
                         (unsigned long)stat_can_recover);
        if (n > 0)
        {
            UART_QueueBytes(reply, (uint16_t)n);
        }
        return;
    }

    result = can_decode(line, &frame);
    if (result == CAN_DEC_NOT_FRAME)
    {
        return;   /* not a frame at all - ignore, do not count as an error */
    }
    if (result != CAN_DEC_OK)
    {
        stat_cmd_bad++;
        return;
    }

    {
        CAN_TxHeaderTypeDef tx_header;
        uint32_t mailbox;

        memset(&tx_header, 0, sizeof tx_header);
        tx_header.IDE = frame.ext ? CAN_ID_EXT : CAN_ID_STD;
        tx_header.RTR = frame.rtr ? CAN_RTR_REMOTE : CAN_RTR_DATA;
        tx_header.DLC = frame.dlc;
        tx_header.TransmitGlobalTime = DISABLE;
        if (frame.ext)
        {
            tx_header.ExtId = frame.id;
        }
        else
        {
            tx_header.StdId = frame.id;
        }

        if (HAL_CAN_AddTxMessage(&hcan, &tx_header, frame.data, &mailbox) == HAL_OK)
        {
            stat_can_tx++;
            LED_RequestActivity();
        }
        else
        {
            /* All three mailboxes busy - report it rather than silently
               dropping the frame on the floor. */
            stat_can_tx_drop++;
        }
    }
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART1_UART_Init();
  MX_CAN_Init();
  /* USER CODE BEGIN 2 */
    msgqueue_init(&uart_rxq, &uart_line_slots[0][0], UART_LINE_MAX);
    ring_u8_init(&uart_txq, uart_tx_buf, UART_TX_BUF_SIZE);
    can_active_bitrate = can_bitrate_default();

    if (CAN_StartWithFilter() != HAL_OK)
    {
        Error_Handler();
    }

    if (HAL_UART_Receive_IT(&huart1, &uart_rx_byte, 1) != HAL_OK)
    {
        Error_Handler();
    }

    can_last_error_poll = HAL_GetTick();

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
    while (1) {
        /* CAN -> UART backlog */
        UART_TxService();

        /* Recover the controller if it fell off the bus */
        CAN_ServiceErrors();

        /* UART -> CAN: handle every complete command line that is waiting */
        {
            const char *line = msgqueue_read_slot(&uart_rxq);
            if (line != NULL)
            {
                HandleCommand(line);
                msgqueue_release(&uart_rxq);
            }
        }

    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
        LED_Service();
    }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief CAN Initialization Function
  * @param None
  * @retval None
  */
static void MX_CAN_Init(void)
{

  /* USER CODE BEGIN CAN_Init 0 */

  /* USER CODE END CAN_Init 0 */

  /* USER CODE BEGIN CAN_Init 1 */

  /* USER CODE END CAN_Init 1 */
  hcan.Instance = CAN1;
  hcan.Init.Prescaler = 4;
  hcan.Init.Mode = CAN_MODE_NORMAL;
  hcan.Init.SyncJumpWidth = CAN_SJW_1TQ;
  hcan.Init.TimeSeg1 = CAN_BS1_15TQ;
  hcan.Init.TimeSeg2 = CAN_BS2_2TQ;
  hcan.Init.TimeTriggeredMode = DISABLE;
  hcan.Init.AutoBusOff = DISABLE;
  hcan.Init.AutoWakeUp = DISABLE;
  hcan.Init.AutoRetransmission = ENABLE;
  hcan.Init.ReceiveFifoLocked = DISABLE;
  hcan.Init.TransmitFifoPriority = DISABLE;
  if (HAL_CAN_Init(&hcan) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN CAN_Init 2 */

  /* USER CODE END CAN_Init 2 */

}

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART1_UART_Init(void)
{

  /* USER CODE BEGIN USART1_Init 0 */

  /* USER CODE END USART1_Init 0 */

  /* USER CODE BEGIN USART1_Init 1 */

  /* USER CODE END USART1_Init 1 */
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 115200;
  huart1.Init.WordLength = UART_WORDLENGTH_8B;
  huart1.Init.StopBits = UART_STOPBITS_1;
  huart1.Init.Parity = UART_PARITY_NONE;
  huart1.Init.Mode = UART_MODE_TX_RX;
  huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart1.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART1_Init 2 */

  /* USER CODE END USART1_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);

  /*Configure GPIO pin : PC13 */
  GPIO_InitStruct.Pin = GPIO_PIN_13;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/**
  * @brief  USART1 error recovery.
  *
  * An overrun (ORE) is a *blocking* error for the HAL: it disables the RX
  * interrupts and leaves the receiver needing an explicit restart.  The ORE
  * flag is only cleared by reading SR followed by DR.  Re-arming the reception
  * without doing that leaves ORE set, so the very next RXNE interrupt takes the
  * error path again - an interrupt storm that starves the main loop and
  * permanently kills reception.  That is what this function exists to prevent.
  */
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance != USART1)
    {
        return;
    }

    stat_uart_err++;

    if ((huart->ErrorCode & (HAL_UART_ERROR_ORE | HAL_UART_ERROR_FE |
                             HAL_UART_ERROR_NE | HAL_UART_ERROR_PE)) != 0u)
    {
        /* Reading SR then DR is the documented ORE clear sequence. */
        (void)huart->Instance->SR;
        (void)huart->Instance->DR;

        /* Drop the partially assembled line: its bytes are not trustworthy. */
        uart_rx_idx = 0u;
    }

    (void)HAL_UART_AbortReceive(huart);

    huart->ErrorCode = HAL_UART_ERROR_NONE;
    huart->RxState = HAL_UART_STATE_READY;
    huart->ReceptionType = HAL_UART_RECEPTION_STANDARD;

    if (HAL_UART_Receive_IT(&huart1, &uart_rx_byte, 1) != HAL_OK)
    {
        /* The HAL refused to restart the reception.  Record it so the 'V'
           status readout makes the failure visible. */
        huart->ErrorCode = HAL_UART_ERROR_ORE;
        stat_uart_err++;
    }
}

/**
  * @brief  USART1 byte received.  Assembles one command line, then publishes it
  *         to the queue.
  *
  * The slot is fully written and NUL-terminated *before* msgqueue_publish()
  * makes it visible, so the main loop can never observe a half-written line.
  */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        uint8_t b = uart_rx_byte;

        if (b == '\r' || b == '\n')
        {
            if (uart_rx_idx > 0u)
            {
                if (msgqueue_has_room(&uart_rxq))
                {
                    msgqueue_write_slot(&uart_rxq)[uart_rx_idx] = '\0';
                    msgqueue_publish(&uart_rxq);
                }
                else
                {
                    /* Every slot is still waiting to be handled. */
                    stat_cmd_drop++;
                }
                uart_rx_idx = 0u;
            }
        }
        else if (uart_rx_idx < (UART_LINE_MAX - 1u))
        {
            msgqueue_write_slot(&uart_rxq)[uart_rx_idx++] = (char)b;
        }
        else
        {
            /* Longer than any legal frame: resynchronise on the next
               terminator instead of silently wrapping. */
            stat_cmd_drop++;
            uart_rx_idx = 0u;
        }

        (void)HAL_UART_Receive_IT(&huart1, &uart_rx_byte, 1);
    }
}

/**
  * @brief  CAN frame received in FIFO0: forward it to the UART as ASCII.
  */
void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan)
{
    CAN_RxHeaderTypeDef rx_header;
    uint8_t rx_data[CAN_CODEC_MAX_DATA];
    can_frame_t frame;
    char msg[CAN_ENCODE_MAX];
    uint16_t len;
    uint16_t i;

    if (HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &rx_header, rx_data) != HAL_OK)
    {
        return;
    }
    LED_RequestActivity();

    /* Trust nothing that came off the bus: clamp the DLC and zero the payload
       so a remote frame can never leak stale bytes. */
    frame.ext = (rx_header.IDE == CAN_ID_EXT) ? 1u : 0u;
    frame.rtr = (rx_header.RTR == CAN_RTR_REMOTE) ? 1u : 0u;
    frame.id  = frame.ext ? rx_header.ExtId : rx_header.StdId;
    frame.dlc = (rx_header.DLC > CAN_CODEC_MAX_DATA)
                    ? (uint8_t)CAN_CODEC_MAX_DATA
                    : (uint8_t)rx_header.DLC;
    memset(frame.data, 0, sizeof frame.data);
    for (i = 0u; i < frame.dlc; i++)
    {
        frame.data[i] = rx_data[i];
    }

    len = can_encode(msg, &frame);

    for (i = 0u; i < len; i++)
    {
        if (!ring_u8_push(&uart_txq, (uint8_t)msg[i]))
        {
            /* Host is not draining fast enough; the rest of this frame is
               lost.  Counted so the 'V' status command can expose it. */
            stat_uart_drop++;
            break;
        }
    }
    stat_can_rx++;
}

/**
  * @brief  CAN error interrupt.  Bus-off recovery itself is handled by
  *         CAN_ServiceErrors() in the main loop, which can afford to call the
  *         blocking HAL_CAN_Stop()/HAL_CAN_Start() pair and reprogram the
  *         filter banks that HAL_CAN_Stop() deactivates.
  */
void HAL_CAN_ErrorCallback(CAN_HandleTypeDef *hcan)
{
    (void)hcan;
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
    /* LED on solid and stop.  Interrupts stay enabled so a debugger can still
       inspect the state that led here. */
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);
    while (1) {
    }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
    /* User can add his own implementation to report the file name and line number,
       ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
