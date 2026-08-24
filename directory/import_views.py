"""Temporary, token-protected data import endpoint.

This endpoint exists only to move the supplied private source files into the
deployment when the Coolify terminal and database port are unavailable. It is
intended to be removed after the one-time import is complete.
"""

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST


_STATE_PATH = Path(tempfile.gettempdir()) / "alumni_import_state.json"


def _authorized(request):
    expected = os.environ.get("ALUMNI_IMPORT_TOKEN", "").strip()
    supplied = request.headers.get("X-Alumni-Import-Token", "").strip()
    return bool(expected) and supplied == expected and not settings.DEBUG


def _read_state():
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return None


def _log_tail(path, lines=12):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return []


@csrf_exempt
@require_POST
def alumni_import(request):
    if not _authorized(request):
        return JsonResponse({"detail": "Not found."}, status=404)

    current = _read_state()
    if current and not Path(current.get("exit_code", "")).exists():
        return JsonResponse({"detail": "An import is already running."}, status=409)

    csv_file = request.FILES.get("csv")
    json_file = request.FILES.get("json")
    if not csv_file or not json_file:
        return JsonResponse({"detail": "Both csv and json files are required."}, status=400)

    work_dir = Path(tempfile.mkdtemp(prefix="alumni-import-"))
    csv_path = work_dir / "roster.csv"
    json_path = work_dir / "records.json"
    log_path = work_dir / "import.log"
    exit_path = work_dir / "exit_code"
    for upload, destination in ((csv_file, csv_path), (json_file, json_path)):
        with destination.open("wb") as output:
            for chunk in upload.chunks():
                output.write(chunk)

    command = " ".join(
        [
            shlex.quote(sys.executable),
            shlex.quote(str(settings.BASE_DIR / "manage.py")),
            "import_alumni",
            "--csv",
            shlex.quote(str(csv_path)),
            "--json",
            shlex.quote(str(json_path)),
            ">",
            shlex.quote(str(log_path)),
            "2>&1; code=$?; printf '%s' \"$code\" >",
            shlex.quote(str(exit_path)),
        ]
    )
    process = subprocess.Popen(
        ["/bin/sh", "-c", command],
        cwd=settings.BASE_DIR,
        start_new_session=True,
    )
    _STATE_PATH.write_text(
        json.dumps({"pid": process.pid, "exit_code": str(exit_path), "log": str(log_path)}),
        encoding="utf-8",
    )
    return JsonResponse({"accepted": True}, status=202)


@require_GET
def alumni_import_status(request):
    if not _authorized(request):
        return JsonResponse({"detail": "Not found."}, status=404)

    state = _read_state()
    if not state:
        return JsonResponse({"status": "idle"})
    exit_path = Path(state["exit_code"])
    if not exit_path.exists():
        return JsonResponse({"status": "running"})

    try:
        exit_code = int(exit_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        exit_code = 1
    return JsonResponse(
        {
            "status": "completed" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "output": _log_tail(state["log"]),
        }
    )
