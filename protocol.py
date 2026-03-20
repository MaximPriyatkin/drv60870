import struct
from datetime import datetime
import const
from const import AsduTypeId
import common as cm

# pyright: reportOptionalMemberAccess=false

def enc_siq(ev):  # 1, 30, 45 single point 1 + q & single command
    return bytes([(int(ev.val) & 0x01) | (ev.q & 0xFE)])
def enc_diq(ev):  # 3, 31 double point 2 + q
    return bytes([(int(ev.val) & 0x03) | (ev.q & 0xFC)])
def enc_qds_float(ev):  # 36, 45 measured float 4 + q
    return struct.pack('<fB', float(ev.val), ev.q)
def enc_vti(ev):  # 5, 32 step position + q
    return struct.pack('<bB', int(ev.val), ev.q)
def enc_nva(ev):  # 9,34,11,35 normailized value, measurement scaled
    return struct.pack('<hB', int(ev.val), ev.q)
def enc_bsi(ev):  # 7,33 bitstring
    return struct.pack('<IB', int(ev.val), ev.q)
def enc_bcr(ev):  # 15, 37 binary counter
    return struct.pack('<iB', int(ev.val), ev.q)

ENCODERS = {
    # Без метки времени (Monitoring)
    AsduTypeId.M_SP_NA_1: (enc_siq, False),
    AsduTypeId.M_DP_NA_1: (enc_diq, False),
    AsduTypeId.M_ST_NA_1: (enc_vti, False),
    AsduTypeId.M_BO_NA_1: (enc_bsi, False),
    AsduTypeId.M_ME_NA_1: (enc_nva, False),
    AsduTypeId.M_ME_NB_1: (enc_nva, False),
    AsduTypeId.M_ME_NC_1: (enc_qds_float, False),
    AsduTypeId.M_IT_NA_1: (enc_bcr, False),

    # С меткой времени CP56Time2a (Monitoring)
    AsduTypeId.M_SP_TB_1: (enc_siq, True),
    AsduTypeId.M_DP_TB_1: (enc_diq, True),
    AsduTypeId.M_ST_TB_1: (enc_vti, True),
    AsduTypeId.M_BO_TB_1: (enc_bsi, True),
    AsduTypeId.M_ME_TD_1: (enc_nva, True),
    AsduTypeId.M_ME_TE_1: (enc_nva, True),
    AsduTypeId.M_ME_TF_1: (enc_qds_float, True),
    AsduTypeId.M_IT_TB_1: (enc_bcr, True),
    
    # Системные и команды
    AsduTypeId.C_IC_NA_1: (lambda ev: bytes([int(ev.val) & 0xFF]), False),
    AsduTypeId.C_SC_NA_1: (enc_siq, False), # Однокомандное
    AsduTypeId.C_DC_NA_1: (enc_diq, False), # Двухкомандное
}


def _enc_obj(t_asdu, ev) -> bytes | None:
    config = ENCODERS.get(t_asdu)
    if not config:
        return None
    enc_func, has_ts = config
    body = int.to_bytes(ev.ioa, 3, 'little')
    body += enc_func(ev)
    if has_ts:
        body += datetime_to_cp56(ev.ts)
    return body

def build_i_frame(state: cm.ClientState, events: list) -> bytes | None:
    if not events:
        return None
    t_asdu = events[0].asdu
    cot = events[0].cot
    parts = []
    for ev in events:
        obj = _enc_obj(t_asdu, ev)
        if obj is None:
            state.log.error(f'Тип ASDU {t_asdu} не поддерживается драйвером')
            return None
        parts.append(obj)
    cot_bytes = struct.pack('<H', cot)
    asdu = struct.pack('<BBBBH', t_asdu, len(events), cot_bytes[0], cot_bytes[1], state.ca) + b''.join(parts)
    send_sq = (state.send_sq << 1).to_bytes(2, 'little')
    rec_sq = (state.rec_sq << 1).to_bytes(2, 'little')
    return b'\x68' + bytes([len(asdu) + 4]) + send_sq + rec_sq + asdu


def build_i_frame_ack(state:cm.ClientState, frame, cot):
    asdu = bytearray(frame[6:])
    asdu[2] = cot
    ctrl_ns = (state.send_sq << 1).to_bytes(2, 'little')
    ctrl_nr = (state.rec_sq << 1).to_bytes(2, 'little')
    header = b'\x68' + bytes([len(asdu) + 4]) + ctrl_ns + ctrl_nr
    state.send_sq = (state.send_sq + 1) % 32768
    return header + asdu


def proc_frame(frame: bytes, state: cm.ClientState):
    if not (frame[2] & 0x01):
        return 'I', handle_i_frame(frame, state)
    if (frame[2] & 0x02):
        return 'U', handle_u_frame(frame, state)
    return 'S', handle_s_frame(frame, state)

def handle_i_frame(frame: bytes, state: cm.ClientState):
    log = state.log        
    n_s = struct.unpack('<H', frame[2:4])[0] >> 1
    n_r = struct.unpack('<H', frame[4:6])[0] >> 1
    state.last_ack_nr = n_r  # клиент подтвердил приём наших I-кадров с N(S) < N(R)
    if n_s != state.rec_sq:
        log.error(f'C->S [SEQ ERROR] Ожидание N(S)={state.rec_sq} пришло {n_s}')
        # выполнить разрыв связи
    state.rec_sq = (state.rec_sq + 1) % 32768
    # проверить наши кадры на доставку
    asdu = frame[6:]
    type_id = asdu[0]
    vsq = asdu[1]
    cot = asdu[2]

    coa =  struct.unpack('<H', asdu[3:5])[0]
    # проверить coa!

    count = vsq & 0x7F # Количество объектов 0-6 бит
    is_seq = vsq & 0x80 # 7ой бит - тип последовательности
    offset = 6 # начало данных в asdu
    parsed_obj = []
    try:
        if is_seq:
            # один базовый ioa, затем значения
            base_ioa = struct.unpack('<I', asdu[offset:offset+3] + b'\x00')[0]
            offset += 3
            val_size = const.ASDU_DATA_SIZE.get(type_id, 1)
            for i in range(count):
                val_data = asdu[offset:offset+val_size]
                parsed_obj.append((base_ioa + i, val_data))
                offset += val_size
        else:
            # много базовых ioa
            val_size = const.ASDU_DATA_SIZE.get(type_id, 1)
            for _ in range(count):
                ioa = int.from_bytes(asdu[offset:offset+3], byteorder='little')
                offset += 3
                val_data = asdu[offset:offset+val_size]
                parsed_obj.append((ioa, val_data))
                offset += val_size
    except IndexError:
        log.error("C->S [ASDU] Ошибка длины: пакет обрезан")
        return None


    if type_id == AsduTypeId['C_IC_NA_1']: # общий опрос
        if state.on_gi and state.out_que:
            for event in state.on_gi():
                if event.asdu < 45: # не отправляем в общем опросе ТУ/ТР - можно спросить из конфигурации потом
                    state.out_que.put(event)
            state.out_que.put(cm.IecEvent(id=-1, ioa=0, asdu=100, val=0, ts=datetime.now(), cot=10))
            return build_i_frame_ack(state, frame, const.COT.ACTIVATION_CON)

    if type_id == AsduTypeId['C_SC_NA_1']: # команда однопозиционная
        for ioa, data in parsed_obj:
            val = data[0] & 0x01
            log.info(f'C->S [COMMAND] IOA:{ioa} VAL:{val}')
            if state.on_command:
                success = state.on_command(val, ioa)
                if not success:
                    log.warning(f'Команда на IOA {ioa} отклонена')
        return build_i_frame_ack(state, frame, const.COT.ACTIVATION_CON)
    if type_id == AsduTypeId['C_SE_NC_1']: # команда телерегулирования
        for ioa, data in parsed_obj:
            val, qos =  struct.unpack('<fB', data[:5]) 
            log.info(f'C->S [COMMAND] IOA:{ioa} VAL:{val}')
            if state.on_command:
                success = state.on_command(val, ioa)
                if not success:
                    log.warning(f'Команда на IOA {ioa} отклонена')
        return build_i_frame_ack(state, frame, const.COT.ACTIVATION_CON)
    return None



def handle_u_frame(frame: bytes, state: cm.ClientState):
    u_type_byte = frame[2]
    log = state.log
    try:
        u_cmd = const.UTypeId(u_type_byte)
        if u_cmd == const.UTypeId.STARTDT_ACT:
            log.info(f'C->S [STARTDT ACT] {frame.hex(" ").upper()}')
            state.startdt_confirmed = True
        elif u_cmd == const.UTypeId.STOPDT_ACT:
            log.info(f'C->S [STOPTDT ACT] {frame.hex(" ").upper()}')
            state.startdt_confirmed = False
        elif u_cmd == const.UTypeId.TESTFR_ACT:
            log.info(f'C->S [TESTFR ACT] {frame.hex(" ").upper()}')
        return const.U_RESP.get(u_cmd)
    except ValueError:
         log.warning(f'C->S [U-FRAME] Ошибочный байт {frame.hex(" ").upper()}')

def build_s_frame(state: cm.ClientState) -> bytes:
    """S-кадр: подтверждение приёма I-кадров до N(R). Формат 104: 68 04 01 00 N(R)<<1."""
    nr = (state.rec_sq << 1).to_bytes(2, 'little')
    return b'\x68\x04\x01\x00' + nr

def handle_s_frame(frame: bytes, state: cm.ClientState) -> None:
    """Приём S-кадра: парсинг N(R) — клиент подтвердил приём наших I-кадров с N(S) < N(R)."""
    if len(frame) < 6:
        if state.log:
            state.log.warning('C->S [S-FRAME] Слишком короткий кадр')
        return None
    n_r = struct.unpack('<H', frame[4:6])[0] >> 1
    state.last_ack_nr = n_r
    if state.log:
        state.log.debug(f'C->S [S-FRAME] N(R)={n_r}')
    return None

def datetime_to_cp56(dt: datetime, iv = False) -> bytes:
    # ms в текущей минуте (little-endian)
    ms_total = (dt.second * 1000 + dt.microsecond // 1000) % 60000  # UTC, 0-59999
    ms_low = ms_total & 0xFF
    ms_high = (ms_total >> 8) & 0xFF
    res = bytearray(7)
    res[0] = ms_low
    res[1] = ms_high
    res[2] = dt.minute & 0x3F
    if iv:
        res[2] |= 0x80
    res[3] = dt.hour & 0x1F
    res[4] = (dt.day & 0x1F) | ((dt.isoweekday() & 0x07) << 5)
    res[5] = dt.month & 0x0F
    res[6] = (dt.year - 2000) & 0x7F  # Явно -2000
    return bytes(res)

def datetime_from_cp56(dt_bt):
    if len(dt_bt) < 7:
        raise ValueError('не достаточно данных в cp56')
    ms_total = (dt_bt[1] << 8) | dt_bt[0]
    sec = ms_total // 1000
    msec = ms_total % 1000
    mins = dt_bt[2] & 0x3F
    iv = (dt_bt[2] & 0x80) != 0

    hour = dt_bt[3] & 0x1F
    day = dt_bt[4] & 0x1F
    month = dt_bt[5] & 0x0F
    year = 2000 + (dt_bt[6] & 0x7F)
    try:
        dt = datetime(year, month, day, hour, mins, sec, microsecond=msec*1000)
        return dt , iv
    except ValueError as e:
        return None, None
    





if __name__ == '__main__':
    b = datetime_to_cp56(datetime.now())
    print(b)
    c = datetime_from_cp56(b)
    print(c)
    

