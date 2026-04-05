# todo list

- [X] - print timestamp of signals
- [ ] - imitation from table
- [X] - make quality input more convenient
- [ ] - automation tests
- [ ] - event bus: добавить binary формат (type = "tcp_bin") для высокочастотного обмена
  - Реализация: в `event_bus.py` добавить `create_tcp_bin_sender(host, port)`.
    Формат пакета: 4B длина + struct.pack('<HIBHBf?7s', ca, ioa, asdu, cot, q, val, iv, ts_cp56).
    Фиксированный размер 22 байта на объект vs ~130 байт JSON (~6x компактнее).
    В `setup_bus` добавить обработку `type = "tcp_bin"`. Обновить `bus_client.py` для приёма binary.
  - Оценка: JSON ~130 КБ/с при 1000 сиг/с, binary ~21 КБ/с. Для IEC 104 (<1000 сиг/с) JSON достаточен.
    Binary нужен при embedded/радио/GPRS каналах или >10000 сиг/с.

