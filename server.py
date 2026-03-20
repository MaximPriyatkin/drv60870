import socket
from threading import Thread, Event
import queue
import time
# ------------------------------
import const
import common as cm
import protocol as prt
import imit as im
from control import server_handler

# state в client_send/client_rec всегда инициализирован 
# pyright: reportOptionalMemberAccess=false

def client_send(state: cm.ClientState):
    log = state.log
    log.info('Поток отправки запущен')
    get_time = time.monotonic
    t = get_time()
    while not state.stop_event.is_set():
        try:  # обработка соединения
            try:  # обработка очереди кадров
                event = state.out_que.get(timeout=1.0)
                if not state.startdt_confirmed:
                    log.debug(f'Передача запрещена, событие {event} игнорируем')
                    time.sleep(0.01)  # так как не очень важно оставляем sleep
                    continue
                unack = (state.send_sq - state.last_ack_nr) % 32768
                if unack >= state.conf.prot_k:
                    state.out_que.put(event)
                    time.sleep(0.01)  # todo - сделать событие от приема кадра
                    continue
                batch = [event] # упаковка нескольких ASDU в один кадр для быстрой отправки
                obj_size = 3 + const.ASDU_DATA_SIZE.get(event.asdu, 1) # - 3 байта размер ASDU
                # 243 - число объектов в APDU, чтобы уместилось вне зависимости от типа ASDU
                # 127 - максимальное количество объектов
                max_obj = min(127, 243 // obj_size)
                # если в очереди подряд идут одинаковые ASDU - упаковываем их в один пакет  
                try:
                    while len(batch) < max_obj:
                        nxt = state.out_que.get_nowait()
                        if nxt.asdu == event.asdu and nxt.cot == event.cot:
                            batch.append(nxt)
                        else:
                            state.out_que.put(nxt)
                            break
                except queue.Empty:
                    pass
                packet = prt.build_i_frame(state, batch)
                if packet is not None:
                    state.conn.send(packet)
                state.last_send = get_time()  # для формирования отправки тестового кадра по прстою
                state.send_sq = (state.send_sq + 1) % 32768 # 32768 - защита от переполнения 2х байтного поля
                state.sent_obj += len(batch)  # для статистики, добавляем число отправленных ASDU в одном пакете
                n = state.conf.log_i_frame_stats_every  # через сколько пакетов отправлять статистику
                # Вывод статистики по переданным кадрам
                if n and state.sent_obj % n < len(batch) and get_time() - t > 0:
                    dt = get_time() - t
                    log.info(f"I-frame: кадров {state.send_sq}, объектов {state.sent_obj}, очередь {state.out_que.qsize()}, скорость {state.sent_obj/dt:.1f} obj/с")
                    t = get_time()
                    state.sent_obj = 0
                log.debug(f"S->C [I-FRAME] ASDU:{event.asdu} COUNT_OBJ:{len(batch)} V(S):{state.send_sq}")
            except queue.Empty:
                pass
            now = get_time()
            if state.conf and (now - state.last_send) >= state.conf.prot_t3:
                log.debug(f'S->C [TESTFR ACT] Канал простаивал {state.conf.prot_t3}c')
                state.conn.send(const.TESTFR_ACT)
                state.last_send = now
        except (socket.error, ConnectionError, BrokenPipeError) as e:
            log.error(f"Ошибка записи в сокет {e}")
            state.stop_event.set()
            break
    log.debug('Поток отправки остановлен')

def client_rec(state, remove_client, data_storage):
    log = state.log
    buffer = bytearray()
    state.conn.settimeout(1.0)
    with state.conn:
        try:
            while not state.stop_event.is_set():
                try:
                    data = state.conn.recv(1024)
                except socket.timeout:
                    continue
                if not data:
                     break
                log.debug(f'C->S [RAW] {data.hex(" ").upper()}')
                buffer.extend(data)
                if len(buffer) > state.conf.max_rx_buf:
                    log.error(f'Буфер переполнен, очищаем буфер {len(buffer)} > {state.conf.max_rx_buf}')
                    state.stop_event.set()
                    break
                while len(buffer) >= 6:
                    try:
                        start_idx = buffer.index(0x68)
                    except ValueError:
                        log.warning('В буфере нет стартового байта 0x68, очищаем буфер')
                        buffer.clear()
                        break
                    if start_idx > 0:
                        log.warning(f'Пропускаем {start_idx} байт(а) до стартового байта 0x68')
                        del buffer[:start_idx]
                    if len(buffer) < 2:
                        break
                    apdu_len = buffer[1]
                    total_frame_len = apdu_len + 2
                    if len(buffer) < total_frame_len:
                        log.debug(f'Ждем данные, сейчас {len(buffer)}, нужно {total_frame_len}')
                        break
                    frame = buffer[:total_frame_len]
                    del buffer[:total_frame_len]
                    f_type, response = prt.proc_frame(frame, state)
                    if f_type == 'I':
                        state.rec_count_since_send += 1
                    if response:
                        state.conn.send(response)
                        state.last_send = time.time()
                        state.rec_count_since_send = 0
                        if f_type == 'I' and frame[6] == const.AsduTypeId.C_IC_NA_1:
                            pass  # обработка ответа на общий опрос
                        log.debug(f'S->C [{f_type}-CON] {response.hex(" ").upper()}')
                    elif f_type == 'I' and state.rec_count_since_send >= state.conf.prot_w:
                        state.conn.send(prt.build_s_frame(state))
                        state.last_send = time.time()
                        state.rec_count_since_send = 0
                        log.debug(f'S->C [S-FRAME] N(R)={state.rec_sq}')
        except (ConnectionError, BrokenPipeError, socket.error):
            state.stop_event.set()
        finally:
            data_storage.unsubscribe(state.addr)
            remove_client(state.addr)    
    log.info(f'Отключился клиент {state.addr}')

def main():
    conf = cm.load_config()
    log = cm.setup_logging(conf)
    client_storage = cm.create_client_storage()
    data_storage = cm.create_data_storage()
    ca = int(conf.prot_ca)
    cm.load_signal(data_storage.add_signal, ca)
    stop_thread = Event()
    client_threads = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((conf.nw_bind_ip, conf.nw_port))
        sock.listen()
        sock.settimeout(1.0)
        log.info(f'Запущен сервер порт: {conf.nw_port}')
    except OSError as e:
        print(f'ошибка при создании сокета {e}')
        return
    # Старт потока управления сервером
    Thread(
        target=server_handler,
        args=(stop_thread, client_storage, data_storage, log),
        daemon=True).start()
    try:
        while not stop_thread.is_set():
            try:
                conn, addr = sock.accept() 
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                if addr[0] not in conf.nw_allow_ip:
                    log.warning(f'Клиент {addr} не в списке разрешенных IP')
                    conn.close()
                    continue    
                client_threads = [t for t in client_threads if t.is_alive()]
                log.info(f'Обслуживается потоков: {len(client_threads)}')
                log.info(f'Подключен клиент {addr}')
                state = cm.ClientState()
                state.ca = ca
                state.conn = conn
                state.addr = addr
                state.conf = conf
                state.log = cm.logging.getLogger(f'{conf.log_name}.{addr[0]}:{addr[1]}')
                state.out_que = queue.Queue()
                state.on_command = lambda val, ioa: data_storage.update_val(val, ioa=ioa)
                state.on_gi = data_storage.get_all_for_gi
                data_storage.subscribe(addr, state.out_que)
                client_storage.add_client(state)
                # Старт отправки данных 
                t = Thread(
                    target=client_send,
                    args=(state, ),
                    daemon=True)
                t.start()
                client_threads.append(t)
                # Старт потока чтения данных от сервера
                t = Thread(
                    target=client_rec,
                    args=(state, client_storage.remove_client, data_storage))
                t.start()
                client_threads.append(t)

            except socket.timeout:
                continue
    except KeyboardInterrupt:
        log.warning('cервер остановлен по ctrl-c')
    finally:
        stop_thread.set()
        client_storage.close_all()
        log.info('Ожидание завершения клиентских потоков')
        client_storage.close_all()
        for t in client_threads:
            t.join(timeout=2.0)
        sock.close()
        log.info('Сервер остановлен')

if __name__ == '__main__':
    main()