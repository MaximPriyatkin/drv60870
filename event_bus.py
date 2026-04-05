"""Event bus for data routing with per-signal filtering.

Subscribers receive (session_name, objects) where objects is a list of
(ioa, asdu, val, q, cot, coa, ts, iv) tuples — same format as
protocol.decode_i_frame_objects output.

Subscriber types:
- callback: any callable(session_name, objects)
- tcp: JSON-lines over TCP socket
- udp: JSON datagrams over UDP socket
- server_bridge: forwards to server's data_storage.update_val
"""

import json
import socket
from threading import Lock
from types import SimpleNamespace


def create_event_bus(log=None):
    """Create a central event bus with IOA-based filtering."""
    _lock = Lock()
    _subs = {}
    _counter = 0

    def subscribe(handler, ioa_filter=None, name='', close_fn=None):
        """Subscribe a handler. ioa_filter: set/list of IOA or None=all."""
        nonlocal _counter
        with _lock:
            _counter += 1
            sid = _counter
            ioa_set = frozenset(ioa_filter) if ioa_filter else None
            _subs[sid] = (name, ioa_set, handler, close_fn)
        if log:
            log.info(f"Bus: subscribed '{name}' id={sid} filter={ioa_set}")
        return sid

    def unsubscribe(sub_id):
        with _lock:
            entry = _subs.pop(sub_id, None)
        if not entry:
            return False
        name, _, _, close_fn = entry
        if close_fn:
            try:
                close_fn()
            except Exception:
                pass
        if log:
            log.info(f"Bus: unsubscribed '{name}' id={sub_id}")
        return True

    def publish(session_name, objects):
        with _lock:
            snapshot = list(_subs.values())
        for name, ioa_set, handler, _ in snapshot:
            filtered = [o for o in objects if o[0] in ioa_set] if ioa_set else objects
            if not filtered:
                continue
            try:
                handler(session_name, filtered)
            except Exception as e:
                if log:
                    log.error(f"Bus subscriber '{name}': {e}")

    def close():
        with _lock:
            entries = list(_subs.values())
            _subs.clear()
        for _, _, _, close_fn in entries:
            if close_fn:
                try:
                    close_fn()
                except Exception:
                    pass

    def list_subs():
        with _lock:
            return {sid: (n, ioa) for sid, (n, ioa, _, _) in _subs.items()}

    return SimpleNamespace(
        subscribe=subscribe, unsubscribe=unsubscribe,
        publish=publish, close=close, list_subs=list_subs,
    )


# ---- Serialization ----

def _obj_to_dict(session_name, obj):
    ioa, asdu, val, q, cot, coa, ts, iv = obj
    return {
        's': session_name, 'ioa': ioa, 'asdu': asdu, 'ca': coa,
        'val': val, 'q': q, 'iv': bool(iv), 'cot': cot,
        'ts': ts.isoformat(timespec='milliseconds') if ts else None,
    }


# ---- Sender factories ----

def create_tcp_sender(host, port):
    """JSON-lines over persistent TCP connection."""
    _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    _sock.connect((host, port))
    _lock = Lock()

    def send(session_name, objects):
        data = ''.join(
            json.dumps(_obj_to_dict(session_name, o)) + '\n' for o in objects
        )
        with _lock:
            _sock.sendall(data.encode())

    return SimpleNamespace(send=send, close=_sock.close)


def create_udp_sender(host, port):
    """JSON datagrams over UDP (one datagram per object)."""
    _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _addr = (host, port)

    def send(session_name, objects):
        for o in objects:
            _sock.sendto(json.dumps(_obj_to_dict(session_name, o)).encode(), _addr)

    return SimpleNamespace(send=send, close=_sock.close)


def create_server_bridge(data_storage):
    """Forward data to server's data_storage (same-process usage)."""
    def send(_session_name, objects):
        for ioa, _asdu, val, q, _cot, _coa, ts, iv in objects:
            data_storage.update_val(val, ioa=ioa, q=q, iv=iv, ts=ts)

    return SimpleNamespace(send=send, close=lambda: None)
