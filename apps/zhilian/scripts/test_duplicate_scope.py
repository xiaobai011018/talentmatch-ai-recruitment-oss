# -*- coding: utf-8 -*-
"""校验只认本岗位重复记录的辅助逻辑。"""
from backend.core.entity.candidate import _find_current_position_record, _position_id_matches


def main() -> None:
    assert _position_id_matches("8465", "8465") is True
    assert _position_id_matches("7339,8465", "8465") is True
    assert _position_id_matches("[7339|8465]", "8465") is True
    assert _position_id_matches("7339", "8465") is False

    records = [
        {"position_id": "7339", "id": 1},
        {"position_id": "8465", "id": 2},
    ]
    assert _find_current_position_record(records, "8465")["id"] == 2
    assert _find_current_position_record(records, "9999") is None
    print("duplicate scope assertions passed")


if __name__ == "__main__":
    main()
