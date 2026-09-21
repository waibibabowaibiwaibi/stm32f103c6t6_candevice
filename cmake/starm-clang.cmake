set(CMAKE_SYSTEM_NAME               Generic)
set(CMAKE_SYSTEM_PROCESSOR          arm)

set(CMAKE_C_COMPILER_ID Clang)
set(CMAKE_CXX_COMPILER_ID Clang)

# ---------------------------------------------------------------------------
# Toolchain locations.
#
# Supply toolchain locations on the command line or through the environment.
# No developer-specific path is used as a fallback:
#
#   cmake -DSTARM_TOOLCHAIN_PATH=/opt/ATfE \
#         -DGNU_TOOLCHAIN_ROOT=/usr -S . -B build
# ---------------------------------------------------------------------------

# try_compile() re-runs this file in a fresh cache, so the paths supplied
# via -D would otherwise be lost during compiler ABI checks.
set(CMAKE_TRY_COMPILE_PLATFORM_VARIABLES
    STARM_TOOLCHAIN_PATH
    GNU_TOOLCHAIN_ROOT
    STARM_TOOLCHAIN_CONFIG)

set(STARM_TOOLCHAIN_PATH "" CACHE PATH "Directory containing the ATfE/Clang executables")
if(NOT STARM_TOOLCHAIN_PATH)
    if(DEFINED ENV{STARM_TOOLCHAIN_PATH})
        set(STARM_TOOLCHAIN_PATH "$ENV{STARM_TOOLCHAIN_PATH}")
    endif()
endif()

if(STARM_TOOLCHAIN_PATH)
    find_program(STARM_CLANG
        NAMES clang clang.exe
        HINTS "${STARM_TOOLCHAIN_PATH}"
        NO_DEFAULT_PATH)
    find_program(STARM_CLANGXX
        NAMES clang++ clang++.exe
        HINTS "${STARM_TOOLCHAIN_PATH}"
        NO_DEFAULT_PATH)
else()
    find_program(STARM_CLANG NAMES clang clang.exe)
    find_program(STARM_CLANGXX NAMES clang++ clang++.exe)
endif()

if(NOT STARM_CLANG)
    message(FATAL_ERROR
        "ATfE/Clang not found. Put clang on PATH, set STARM_TOOLCHAIN_PATH, "
        "or pass -DSTARM_TOOLCHAIN_PATH=<toolchain>/bin.")
endif()
if(NOT STARM_CLANGXX)
    set(STARM_CLANGXX "${STARM_CLANG}")
endif()

set(CMAKE_C_COMPILER                "${STARM_CLANG}")
set(CMAKE_ASM_COMPILER              ${CMAKE_C_COMPILER})
set(CMAKE_CXX_COMPILER              "${STARM_CLANGXX}")
set(CMAKE_LINKER                    ${CMAKE_C_COMPILER})
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(CMAKE_C_COMPILER_WORKS 1)
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_ASM_COMPILER_WORKS 1)


set(CMAKE_EXECUTABLE_SUFFIX_ASM     ".elf")
set(CMAKE_EXECUTABLE_SUFFIX_C       ".elf")
set(CMAKE_EXECUTABLE_SUFFIX_CXX     ".elf")

set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

# STARM_TOOLCHAIN_CONFIG allows you to choose the toolchain configuration.
# Possible values are:
#  "STARM_HYBRID"   : Hybrid configuration using starm-clang Assembler and Compiler and GNU Linker
#  "STARM_NEWLIB"   : starm-clang toolchain with NEWLIB C library
#  "STARM_PICOLIBC" : starm-clang toolchain with PICOLIBC C library
set(STARM_TOOLCHAIN_CONFIG "STARM_HYBRID" CACHE STRING "ATfE toolchain configuration")

set(GNU_TOOLCHAIN_ROOT "" CACHE PATH "GNU Arm Embedded toolchain root")
if(NOT GNU_TOOLCHAIN_ROOT)
    if(DEFINED ENV{GNU_TOOLCHAIN_ROOT})
        set(GNU_TOOLCHAIN_ROOT "$ENV{GNU_TOOLCHAIN_ROOT}")
    endif()
endif()

if(GNU_TOOLCHAIN_ROOT)
    set(_GNU_HINTS "${GNU_TOOLCHAIN_ROOT}/bin")
endif()
find_program(ARM_NONE_EABI_GCC
    NAMES arm-none-eabi-gcc arm-none-eabi-gcc.exe
    HINTS ${_GNU_HINTS})
if(NOT ARM_NONE_EABI_GCC)
    message(FATAL_ERROR
        "GNU Arm Embedded toolchain not found. Put arm-none-eabi-gcc on PATH, "
        "set GNU_TOOLCHAIN_ROOT, or pass -DGNU_TOOLCHAIN_ROOT=<toolchain-root>.")
endif()

if(NOT GNU_TOOLCHAIN_ROOT)
    get_filename_component(_GNU_BIN_DIR "${ARM_NONE_EABI_GCC}" DIRECTORY)
    get_filename_component(GNU_TOOLCHAIN_ROOT "${_GNU_BIN_DIR}" DIRECTORY)
endif()

# ATfE's Clang driver does not currently understand GNU Arm's multilib table.
# Ask GCC for the Cortex-M3 runtime directories explicitly; otherwise Clang
# silently links the ARM-state libraries from the toolchain root, which fault
# immediately on a Thumb-only Cortex-M processor.
execute_process(
    COMMAND "${ARM_NONE_EABI_GCC}" -mcpu=cortex-m3 -mthumb -print-file-name=libc.a
    OUTPUT_VARIABLE GNU_CORTEX_M_LIBC
    OUTPUT_STRIP_TRAILING_WHITESPACE)
execute_process(
    COMMAND "${ARM_NONE_EABI_GCC}" -mcpu=cortex-m3 -mthumb -print-file-name=libgcc.a
    OUTPUT_VARIABLE GNU_CORTEX_M_LIBGCC
    OUTPUT_STRIP_TRAILING_WHITESPACE)
if(NOT EXISTS "${GNU_CORTEX_M_LIBC}" OR NOT EXISTS "${GNU_CORTEX_M_LIBGCC}")
    message(FATAL_ERROR "Unable to locate the GNU Cortex-M3 Thumb runtime libraries.")
endif()
get_filename_component(GNU_CORTEX_M_LIBC_DIR "${GNU_CORTEX_M_LIBC}" DIRECTORY)
get_filename_component(GNU_CORTEX_M_LIBGCC_DIR "${GNU_CORTEX_M_LIBGCC}" DIRECTORY)

find_program(CMAKE_OBJCOPY
    NAMES arm-none-eabi-objcopy arm-none-eabi-objcopy.exe
    HINTS "${GNU_TOOLCHAIN_ROOT}/bin"
    REQUIRED)
find_program(CMAKE_SIZE
    NAMES arm-none-eabi-size arm-none-eabi-size.exe
    HINTS "${GNU_TOOLCHAIN_ROOT}/bin"
    REQUIRED)

if(STARM_TOOLCHAIN_CONFIG STREQUAL "STARM_HYBRID")
  # Hybrid: starm-clang compiler + GNU linker/runtime
  set(TOOLCHAIN_MULTILIBS "")
elseif (STARM_TOOLCHAIN_CONFIG STREQUAL "STARM_NEWLIB")
  set(TOOLCHAIN_MULTILIBS "--config=newlib.cfg")
endif()

# MCU specific flags. Cortex-M processors execute Thumb instructions only, so
# this must also be present while linking to select the Thumb multilib runtime.
set(TARGET_FLAGS "--target=arm-none-eabi -mcpu=cortex-m3 -mthumb ${TOOLCHAIN_MULTILIBS}")

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${TARGET_FLAGS}")
set(CMAKE_ASM_FLAGS "${CMAKE_C_FLAGS} -x assembler-with-cpp -MP")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -fdata-sections -ffunction-sections")

set(CMAKE_C_FLAGS_DEBUG "-Og -g3")
set(CMAKE_C_FLAGS_RELEASE "-Os -g0")
set(CMAKE_CXX_FLAGS_DEBUG "-Og -g3")
set(CMAKE_CXX_FLAGS_RELEASE "-Os -g0")

set(CMAKE_CXX_FLAGS "${CMAKE_C_FLAGS} -fno-rtti -fno-exceptions -fno-threadsafe-statics")

set(CMAKE_EXE_LINKER_FLAGS "${TARGET_FLAGS}")

if (STARM_TOOLCHAIN_CONFIG STREQUAL "STARM_HYBRID")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -rtlib=libgcc --gcc-toolchain=\"${GNU_TOOLCHAIN_ROOT}\"")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -nostdlib")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -L\"${GNU_CORTEX_M_LIBC_DIR}\" -L\"${GNU_CORTEX_M_LIBGCC_DIR}\"")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -lc_nano -lm -lgcc")
  set(TOOLCHAIN_LINK_LIBRARIES "")
elseif(STARM_TOOLCHAIN_CONFIG STREQUAL "STARM_NEWLIB")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -lcrt0-nosys")
elseif (STARM_TOOLCHAIN_CONFIG STREQUAL "STARM_PICOLIBC")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -lcrt0-hosted")

endif()

set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -T \"${CMAKE_SOURCE_DIR}/STM32F103XX_FLASH.ld\"")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,-Map=${CMAKE_PROJECT_NAME}.map -Wl,--gc-sections")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -z noexecstack")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,--print-memory-usage ")
