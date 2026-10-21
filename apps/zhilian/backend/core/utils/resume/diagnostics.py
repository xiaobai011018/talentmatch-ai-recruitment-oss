import hashlib
import json
import os
import platform
import sys


try:
    _executable_stat = os.stat(sys.executable)
    _executable_size = _executable_stat.st_size
    _executable_mtime_ns = _executable_stat.st_mtime_ns
except OSError:
    _executable_size = None
    _executable_mtime_ns = None

_RUNTIME_FIELDS = {
    "diagnostic_schema_version": 1,
    "process_id": os.getpid(),
    "hostname": platform.node(),
    "frozen": bool(getattr(sys, "frozen", False)),
    "executable": os.path.basename(sys.executable),
    "executable_size": _executable_size,
    "executable_mtime_ns": _executable_mtime_ns,
}


def stable_data_sha256(value) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def summarize_education_experiences(items):
    summaries = []
    for index, item in enumerate(items or []):
        if not isinstance(item, dict):
            summaries.append({"index": index, "invalid_type": type(item).__name__})
            continue
        summaries.append({
            "index": index,
            "school_name": item.get("schoolName", ""),
            "major": item.get("major", item.get("majorName", "")),
            "education_label": item.get("educationLabel", item.get("educationLevel", "")),
            "begin_time": item.get("beginTime", item.get("beginDate", "")),
            "end_time": item.get("endTime", item.get("endDate", "")),
            "time_label": item.get("educationTimeLabel", ""),
        })
    return summaries


def summarize_http_response(response):
    summary = {
        "status_code": getattr(response, "status_code", None),
    }
    if response is None:
        return summary
    try:
        body = response.json()
    except Exception:
        return summary
    if not isinstance(body, dict):
        return summary

    summary["code"] = body.get("code")
    data = body.get("data")
    if isinstance(data, list):
        summary["result_ids"] = [
            item.get("id") if isinstance(item, dict) else item
            for item in data[:10]
        ]
    elif isinstance(data, dict):
        summary["result_ids"] = [
            data.get(key)
            for key in ("id", "resume_id", "screening_id")
            if data.get(key) not in (None, "")
        ]
    elif data not in (None, ""):
        summary["result_ids"] = [data]
    return summary


def log_resume_diagnostic(logger, event: str, **fields):
    payload = {
        "event": event,
        **_RUNTIME_FIELDS,
    }
    payload.update(fields)
    logger.info(
        "resume_diagnostic %s",
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
    )
