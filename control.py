from threading import Thread
from types import SimpleNamespace
from typing import Callable
import common as cm
import imit as im

def _cmd_exit(ctx, _args):
    ctx.log.info('Останавливаем сервер')
    ctx.stop_thread.set()
    return True

def _cmd_clients(ctx, _args):
    for addr, state in ctx.cl.get_clients().items():
        print(addr, state)

def _cmd_addr(ctx, args):
    print('!!', args[0])
    cm.print_signals(ctx.sg.get_signal_by_name(args[0]))

def _cmd_set(ctx, args):
    q = int(args[2],2)
    res = ctx.sg.update_val(float(args[0]), id=int(args[1]), q=q)
    if res:
        cm.print_signals(ctx.sg.get_signal(int(args[1])))

def _cmd_setioa(ctx, args):
    res = ctx.sg.update_val(float(args[0]), ioa=int(args[1]))
    if res:
        cm.print_signals(ctx.sg.get_all())

def _cmd_imit_rand(ctx, args):
    cnt_time, cnt_id = int(args[0]), int(args[1])
    def run():
        list_id = list(range(5, 100, 8))
        print(list_id)
        for _, sid, val, q in im.imit_rand(cnt_time=cnt_time, cnt_id=cnt_id, list_id=list_id, sleep_s=im.SIM_SLEEP):
            ctx.sg.update_val(val, id=sid, q=q)
        ctx.log.info('Имитация завершена')
    Thread(target=run, daemon=True).start()
    print('Имитация запущена в фоне')

def _cmd_imit_ladder(ctx, args):
    cnt_step = int(args[0])
    time_step, val_step, val_min, val_max = float(args[1]), float(args[2]), float(args[3]), float(args[4])
    name_sg = args[5]
    list_id = []    
    def run():
        for key, sg in ctx.sg.get_signal_by_name(args[5]).items():
            if sg.asdu == 36:
                list_id.append(key)
        for _, sid, val, q in im.imit_ladder(cnt_step=cnt_step, 
                                             time_step=time_step,
                                             val_step=val_step,
                                             val_min=val_min, 
                                             val_max=val_max,
                                             list_id=list_id):
            ctx.sg.update_val(val, id=sid, q=q)
        ctx.log.info('Имитация завершена')
    Thread(target=run, daemon=True).start()
    print(f'Имитация запущена в фоне по {len(list_id)} сигналам')

def _cmd_set_log_level(ctx, args):
    target = args[0].lower()
    level_str = args[1].upper()
    level_int = getattr(cm.logging, level_str, None)
    if (level_int is None or
        target not in ('file', 'console')):
        return

    #
    # logger = cm.logging.getLogger("DRV")
    logger = ctx.log
    for hdl in logger.handlers:
        if (target == 'file') and isinstance(hdl, cm.logging.FileHandler):
            hdl.setLevel(level_str)
            print(f"Уровень ФАЙЛА для всех изменен на {level_str}")
        elif (target == 'console' and type(hdl) is
            cm.logging.StreamHandler):
            hdl.setLevel(level_str)
            print(f"Уровень КОНСОЛИ для всех изменен на {level_str}")


def _cmd_help(ctx, _args):
    for name, (n, _) in COMMANDS.items():
        print(f"  {name}" + (f" <arg1> <arg2> ..." if n else ""))

# (число аргументов, обработчик; обработчик возвращает True только для exit)
COMMANDS = {
    "exit": (0, _cmd_exit),
    "clients": (0, _cmd_clients),
    "addr": (1, _cmd_addr),
    "set": (3, _cmd_set),
    "setioa": (2, _cmd_setioa),
    "imit_rand": (2, _cmd_imit_rand),
    "imit_ladder": (6, _cmd_imit_ladder),
    "log_level": (2, _cmd_set_log_level),    
    "help": (0, _cmd_help),
}

def server_handler(stop_thread: Callable, cl: Callable, sg: Callable, log):
    """Обработка пользовательского ввода: реестр команд, единый цикл разбора."""
    ctx = SimpleNamespace(stop_thread=stop_thread, cl=cl, sg=sg, log=log)
    while not stop_thread.is_set():
        try:
            line = input('> ').strip().lower()
        except EOFError:
            log.info('Ввод закрыт, останавливаем сервер')
            stop_thread.set()
            return
        except Exception as e:
            log.exception('Ошибка ввода: %s', e)
            continue
        if not line:
            continue
        parts = line.split()
        cmd_name, args = parts[0], parts[1:]
        entry = COMMANDS.get(cmd_name)
        if entry is None:
            log.info('Команда не распознана: %s', cmd_name)
            print('Команда не распознана. help — список команд.')
            continue
        n_args, handler = entry
        if len(args) != n_args:
            print(f'Ожидается {n_args} арг. для {cmd_name}, получено {len(args)}. help — список команд.')
            continue
        try:
            if handler(ctx, args):
                return
        except Exception as e:
            log.exception('Ошибка выполнения команды %s: %s', cmd_name, e)
            print('Ошибка:', e)