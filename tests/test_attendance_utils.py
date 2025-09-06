import importlib.util
import pathlib


spec = importlib.util.spec_from_file_location(
    "attendance_utils", pathlib.Path(__file__).resolve().parents[1] / "attendance_utils.py"
)
attendance_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(attendance_utils)


class FakeDocSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return self._data


class FakeSessionsCollection:
    def __init__(self, class_storage):
        self.class_storage = class_storage

    def document(self, session_id):
        class Ref:
            def __init__(self, store, sid):
                self.store = store
                self.sid = sid

            def set(self, data):
                self.store[self.sid] = data

        return Ref(self.class_storage, session_id)

    def stream(self):
        return [FakeDocSnapshot(sid, data) for sid, data in self.class_storage.items()]


class FakeClassDocument:
    def __init__(self, storage):
        self.storage = storage

    def collection(self, name):
        assert name == "sessions"
        return FakeSessionsCollection(self.storage)


class FakeAttendanceCollection:
    def __init__(self):
        self.storage = {}

    def document(self, class_name):
        class_storage = self.storage.setdefault(class_name, {})
        return FakeClassDocument(class_storage)


class FakeFirestore:
    def __init__(self):
        self.attendance = FakeAttendanceCollection()

    def collection(self, name):
        assert name == "attendance"
        return self.attendance


def _patch_db(monkeypatch, db):
    monkeypatch.setattr(attendance_utils, "_get_db", lambda: db)


def test_round_trip_save_and_load(monkeypatch):
    db = FakeFirestore()
    _patch_db(monkeypatch, db)

    attendance_map = {
        "0": {
            "label": "Week 1: Grammar",
            "students": {
                "S1": {"name": "Alice", "present": True},
                "S2": {"name": "Bob", "present": False},
            },
        }
    }

    attendance_utils.save_attendance_to_firestore("classA", attendance_map)
    loaded = attendance_utils.load_attendance_from_firestore("classA")
    assert loaded == attendance_map


def test_load_legacy_format(monkeypatch):
    db = FakeFirestore()
    db.attendance.storage["classA"] = {"0": {"S1": True, "S2": False}}
    _patch_db(monkeypatch, db)

    loaded = attendance_utils.load_attendance_from_firestore("classA")
    assert loaded == {
        "0": {
            "label": "",
            "students": {
                "S1": {"name": "", "present": True},
                "S2": {"name": "", "present": False},
            },
        }
    }

