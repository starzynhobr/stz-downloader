import socket

from stz_downloader.runtime import (
    InstanceLock,
    RuntimeInfo,
    load_runtime,
    publish_runtime,
    remove_runtime,
    reserve_server_socket,
)


def test_runtime_record_round_trip_and_owned_cleanup(tmp_path):
    path = tmp_path / "runtime.json"
    info = RuntimeInfo(
        pid=123,
        host="127.0.0.1",
        port=49152,
        token="session-secret",
        instance_id="current-instance",
    )

    publish_runtime(info, path)
    assert load_runtime(path) == info

    remove_runtime("some-other-instance", path)
    assert path.exists()
    remove_runtime(info.instance_id, path)
    assert not path.exists()


def test_invalid_runtime_record_is_rejected(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text('{"app":"some-other-service"}', encoding="utf-8")
    assert load_runtime(path) is None


def test_busy_preferred_port_falls_back_to_reserved_dynamic_port():
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    busy_port = occupied.getsockname()[1]
    try:
        reserved, actual_port = reserve_server_socket("127.0.0.1", busy_port)
        try:
            assert actual_port != busy_port
            assert actual_port > 0
        finally:
            reserved.close()
    finally:
        occupied.close()


def test_instance_lock_does_not_depend_on_a_tcp_port(tmp_path):
    path = tmp_path / "instance.lock"
    first = InstanceLock(path)
    second = InstanceLock(path)
    assert first.acquire() is True
    try:
        assert second.acquire() is False
    finally:
        first.release()
    assert second.acquire() is True
    second.release()
