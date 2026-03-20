from enum import IntEnum
from dataclasses import dataclass

# Константы МЭК 104
START_BYTE = 0x68
TESTFR_ACT = b'\x68\x04\x43\x00\x00\x00'

class UTypeId(IntEnum):
    STARTDT_ACT = 0x07
    STARTDT_CON = 0x0B
    STOPDT_ACT = 0x13
    STOPDT_CON = 0x17
    TESTFR_ACT = 0x43
    TESTFR_CON = 0x83

# Полные кадры подтверждения (U-Format Responses)
# Формат 104: [Start, Len, Type, 0, 0, 0]
U_RESP = {
    UTypeId.STARTDT_ACT: b'\x68\x04\x0B\x00\x00\x00',
    UTypeId.STOPDT_ACT:  b'\x68\x04\x17\x00\x00\x00',
    UTypeId.TESTFR_ACT:  b'\x68\x04\x83\x00\x00\x00',
}

# Причины передачи
class COT(IntEnum):
    PERIODIC = 1        # Циклическая передача
    BACKGROUND = 2      # Фоновая передача
    SPONTANEOUS = 3     # Спонтанная передача
    INITIALIZED = 4     # Инициализировано
    REQUEST = 5         # Запрос
    ACTIVATION = 6      # Активация
    DEACTIVATION = 8    # Деактивация
    ACTIVATION_CON = 7  # Подтверждение активации
    DEACTIVATION_CON = 9 # Подтверждение деактивации
    EXECUTED_CON = 10       # Подтверждение исполнения
    ACTIVATION_TERM = 10    # Завершение общего опроса
    UNKNOWN_TYPE_ID = 44    # Неизвестный тип

class AsduTypeId(IntEnum):
    # Типы ASDU
    # ============= МОНИТОРНОЕ НАПРАВЛЕНИЕ =============
    # Базовые типы (без времени)
    M_SP_NA_1 = 0x01   # 1 Однопозиционный сигнал
    M_DP_NA_1 = 0x03   # 2 Двухпозиционный сигнал
    M_ST_NA_1 = 0x05   # 5 Шаговая позиция
    M_BO_NA_1 = 0x07   # 7 Битовой строки 32 бита
    M_ME_NA_1 = 0x09   # 9 Измерение, нормализованное значение
    M_ME_NB_1 = 0x0B   # 11 Измерение, масштабированное значение
    M_ME_NC_1 = 0x0D   # 13 Измерение, значение с плавающей точкой
    M_IT_NA_1 = 0x0F   # 15 Счетчик
    M_EP_TA_1 = 0x11   # 17 Событие защиты с меткой времени
    M_EP_TB_1 = 0x12   # 18 Упакованные события пуска защиты
    M_EP_TC_1 = 0x13   # 19 Упакованная информация выходных цепей защиты
    M_PS_NA_1 = 0x14   # 20 Упакованная однобитовая информация
    M_ME_ND_1 = 0x15   # 21 Измерение, нормализованное значение без дескриптора качества
    # Типы с длинной меткой времени CP56Time2a (7 байт)
    M_SP_TB_1 = 0x1E   # 30 Однопозиционный сигнал с меткой времени CP56Time2a
    M_DP_TB_1 = 0x1F   # 31 Двухпозиционный сигнал с меткой времени CP56Time2a
    M_ST_TB_1 = 0x20   # 32 Шаговая позиция с меткой времени CP56Time2a
    M_BO_TB_1 = 0x21   # 33 Битовой строки 32 бита с меткой времени CP56Time2a
    M_ME_TD_1 = 0x22   # 34 Измерение, нормализованное значение с меткой времени CP56Time2a
    M_ME_TE_1 = 0x23   # 35 Измерение, масштабированное значение с меткой времени CP56Time2a
    M_ME_TF_1 = 0x24   # 36 Измерение, значение с плавающей точкой с меткой времени CP56Time2a
    M_IT_TB_1 = 0x25   # 37 Счетчик с меткой времени CP56Time2a
    M_EP_TD_1 = 0x26   # 38 Событие защиты с меткой времени CP56Time2a
    M_EP_TE_1 = 0x27   # 39 Упакованные события пуска защиты с меткой времени CP56Time2a
    M_EP_TF_1 = 0x28   # 40 Упакованная информация выходных цепей защиты с меткой времени CP56Time2a
    # ============= КОМАНДНОЕ НАПРАВЛЕНИЕ =============
    # Команды (без времени)
    C_SC_NA_1 = 0x2D   # 45 Однопозиционная команда (ТУ)
    C_DC_NA_1 = 0x2E   # 46 Двухпозиционная команда (ТУ)
    C_RC_NA_1 = 0x2F   # 47 Команда шагового регулирования
    C_SE_NA_1 = 0x30   # 49 Команда уставки, нормализованное значение
    C_SE_NB_1 = 0x31   # 50 Команда уставки, масштабированное значение
    C_SE_NC_1 = 0x32   # 51 Команда уставки, значение с плавающей точкой
    C_BO_NA_1 = 0x33   # 52 Команда битовой строки 32 бита
    # Команды с меткой времени CP56Time2a
    C_SC_TA_1 = 0x3A   # 58 Одиночная команда с меткой времени CP56Time2a
    C_DC_TA_1 = 0x3B   # 59 Двойная команда с меткой времени CP56Time2a
    C_RC_TA_1 = 0x3C   # 60 Команда шагового регулирования с меткой времени CP56Time2a
    C_SE_TA_1 = 0x3D   # 61 Команда уставки, нормализованное значение с меткой времени CP56Time2a
    C_SE_TB_1 = 0x3E   # 62 Команда уставки, масштабированное значение с меткой времени CP56Time2a
    C_SE_TC_1 = 0x3F   # 63 Команда уставки, значение с плавающей точкой с меткой времени CP56Time2a
    C_BO_TA_1 = 0x40   # 64 Команда битовой строки 32 бита с меткой времени CP56Time2a
    # ============= СИСТЕМНАЯ ИНФОРМАЦИЯ =============
    # Мониторное направление
    M_EI_NA_1 = 0x46   # 70 Окончание инициализации
    # Направление управления
    C_IC_NA_1 = 0x64   # 100 Команда общего опроса (100 decimal)
    C_CI_NA_1 = 0x65   # 101 Команда опроса счетчиков
    C_RD_NA_1 = 0x66   # 102 Команда чтения
    C_CS_NA_1 = 0x67   # 103 Команда синхронизации времени
    C_TS_NA_1 = 0x68   # 104 Тестовая команда
    C_RP_NA_1 = 0x69   # 105 Команда сброса процесса
    C_CD_NA_1 = 0x6A   # 106 Команда измерения задержки
    C_TS_TA_1 = 0x6B   # 107 Тестовая команда с меткой времени CP56Time2a
    # ============= ПАРАМЕТРЫ =============
    P_ME_NA_1 = 0x6E   # 110 Параметр измерения, нормализованное значение
    P_ME_NB_1 = 0x6F   # 111 Параметр измерения, масштабированное значение
    P_ME_NC_1 = 0x70   # 112 Параметр измерения, значение с плавающей точкой
    P_AC_NA_1 = 0x71   # 113 Активация параметра
    # ============= ПЕРЕДАЧА ФАЙЛОВ =============
    F_FR_NA_1 = 0x78   # 120 Файл готов
    F_SR_NA_1 = 0x79   # 121 Секция готова
    F_SC_NA_1 = 0x7A   # 122 Вызов каталога / выбор файла
    F_LS_NA_1 = 0x7B   # 123 Последняя секция / последний сегмент
    F_AF_NA_1 = 0x7C   # 124 Подтверждение файла / секции
    F_SG_NA_1 = 0x7D   # 125 Сегмент
    F_DR_TA_1 = 0x7E   # 126 Каталог

# Типы с целочисленным значением (дискретные, команды ТУ и т.п.)
INT_ASDU = (
    AsduTypeId.M_SP_NA_1,
    AsduTypeId.M_DP_NA_1,
    AsduTypeId.M_SP_TB_1,
    AsduTypeId.M_DP_TB_1,
    AsduTypeId.C_SC_NA_1,
    AsduTypeId.C_DC_NA_1,
    AsduTypeId.C_RC_NA_1,
    AsduTypeId.C_SC_TA_1,
    AsduTypeId.C_DC_TA_1,
    AsduTypeId.C_RC_TA_1,
    AsduTypeId.C_BO_NA_1,
    AsduTypeId.C_BO_TA_1,
    AsduTypeId.C_IC_NA_1,
    AsduTypeId.C_CI_NA_1,
    AsduTypeId.C_RD_NA_1,
    AsduTypeId.C_CS_NA_1,
    AsduTypeId.C_TS_NA_1,
    AsduTypeId.C_RP_NA_1,
    AsduTypeId.C_CD_NA_1,
    AsduTypeId.C_TS_TA_1,
)

# Типы с плавающим значением (ТИ, ТР)
FLOAT_ASDU = (
    AsduTypeId.M_ME_NC_1,
    AsduTypeId.M_ME_TF_1,
    AsduTypeId.C_SE_NA_1,
    AsduTypeId.C_SE_NB_1,
    AsduTypeId.C_SE_NC_1,
    AsduTypeId.C_SE_TA_1,
    AsduTypeId.C_SE_TB_1,
    AsduTypeId.C_SE_TC_1,
)

# Команды (ТУ/ТР и др.) — без deadband, threshold=0
COMMAND_ASDU = (
    AsduTypeId.C_SC_NA_1,
    AsduTypeId.C_DC_NA_1,
    AsduTypeId.C_RC_NA_1,
    AsduTypeId.C_SE_NA_1,
    AsduTypeId.C_SE_NB_1,
    AsduTypeId.C_SE_NC_1,
    AsduTypeId.C_BO_NA_1,
    AsduTypeId.C_SC_TA_1,
    AsduTypeId.C_DC_TA_1,
    AsduTypeId.C_RC_TA_1,
    AsduTypeId.C_SE_TA_1,
    AsduTypeId.C_SE_TB_1,
    AsduTypeId.C_SE_TC_1,
    AsduTypeId.C_BO_TA_1,
    AsduTypeId.C_IC_NA_1,
    AsduTypeId.C_CI_NA_1,
    AsduTypeId.C_RD_NA_1,
    AsduTypeId.C_CS_NA_1,
    AsduTypeId.C_TS_NA_1,
    AsduTypeId.C_RP_NA_1,
    AsduTypeId.C_CD_NA_1,
    AsduTypeId.C_TS_TA_1,
)


# Длина данных объекта (Value + Quality + Timestamp) БЕЗ учета 3 байт IOA
ASDU_DATA_SIZE = {
    # --- Без метки времени ---
    1:  1,  # M_SP_NA_1: 1 байт (SIQ)
    3:  1,  # M_DP_NA_1: 1 байт (DIQ)
    13: 5,  # M_ME_NC_1: 4 байта (float) + 1 байт (QDS)
    45: 1,  # C_SC_NA_1: 1 байт (SCO)
    50: 5,  # C_SE_NC_1: 4 байта (float) + 1 байт (QDS)
    
    # --- С меткой времени CP56Time2a (7 байт) ---
    30: 8,  # M_SP_TB_1: 1 байт (SIQ) + 7 байт (Time)
    31: 8,  # M_DP_TB_1: 1 байт (DIQ) + 7 байт (Time)
    36: 12, # M_ME_TF_1: 4 байта (float) + 1 байт (QDS) + 7 байт (Time)
}
