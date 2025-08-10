from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
import subprocess
import os
import re
import sys
import json
import threading
import uuid
import time
import tempfile
import shutil

# -*- coding: utf-8 -*-
sys.stdout.reconfigure(encoding='utf-8')

# 初始化MCP服务器
mcp = FastMCP("garment-generator")

# 配置（仅作为后备；优先从环境变量读取）
PYTHON_PATH = r"D:\miniconda\envs\py39\python.exe"
PROJECT_DIR = r"D:\PythonProjects\garmentcode_project"


import sys




def _project_dir() -> str:
    return os.environ.get("PROJECT_DIR", PROJECT_DIR)



def extract_dataset_path(stdout: str) -> str:
    """从输出中提取数据集路径"""
    patterns = [
        r'(\w+_\d+_\d{6}-\d{2}-\d{2}-\d{2})',
        r'data_folder.*?(\w+_\d{6}-\d{2}-\d{2}-\d{2})',
        r'dataset.*?(\w+_\d{6}-\d{2}-\d{2}-\d{2})'
    ]

    for pattern in patterns:
        match = re.search(pattern, stdout)
        if match:
            folder_name = match.group(1)
            return f"{PROJECT_DIR}/datasets/{folder_name}"

    return None


# ==== 异步接口实现：start_generation / get_generation ====

_JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _preferred_tmp_dir() -> str:
    d = os.environ.get("TMP_JSON_DIR")
    if d:
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except Exception:
            pass
    proj = os.path.join(_project_dir(), "tmp")
    try:
        os.makedirs(proj, exist_ok=True)
        return proj
    except Exception:
        pass
    return tempfile.gettempdir()


def _make_tmp_json_path() -> str:
    d = _preferred_tmp_dir()
    fd, path = tempfile.mkstemp(suffix='.json', dir=d)
    os.close(fd)
    return path


def _jobs_dir() -> str:
    d = os.path.join(_preferred_tmp_dir(), "jobs")
    os.makedirs(d, exist_ok=True)
    return d


def _read_json_with_wait(path: str, max_wait_sec: float = 3.0, interval_sec: float = 0.1):
    deadline = time.time() + max_wait_sec
    last_err = None
    while time.time() < deadline:
        try:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            last_err = e
        time.sleep(interval_sec)
    if last_err:
        raise last_err
    raise FileNotFoundError(f"Result JSON not ready or empty: {path}")


def _resolve_runner() -> str | None:
    # 优先环境变量
    runner = os.environ.get("GARMENT_RUNNER")
    if runner and os.path.exists(runner):
        return runner
    # 同目录
    candidate = os.path.join(os.path.dirname(__file__), "run_in_py39.bat")
    if os.path.exists(candidate):
        return candidate
    # PATH
    return shutil.which("run_in_py39.bat")


def _build_cmd_and_env(count: int, garment_type: str, name_prefix: str, json_out: str):
    runner = _resolve_runner()
    if not runner:
        return None, None, {"success": False, "error": "未找到启动器 run_in_py39.bat，请设置 GARMENT_RUNNER 或将脚本置于同目录"}
    is_batch = runner.lower().endswith((".bat", ".cmd"))
    base = ["cmd.exe", "/c", runner] if is_batch else [runner]
    cmd = base + [
        "--size", str(count),
        "--name", f"{name_prefix}_{garment_type}",
        "--json_output_path", json_out,
    ]
    env = os.environ.copy()
    # 清理父进程 conda 变量，防污染
    for k in list(env.keys()):
        if k.upper().startswith("CONDA"):
            del env[k]
    # 统一编码
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "UTF-8"
    # 临时目录指向首选目录
    pref = _preferred_tmp_dir()
    env["TMP"] = pref
    env["TEMP"] = pref
    # 注入 cairo_dlls（Windows）
    cairo_dir = os.path.join(_project_dir(), "pygarment", "pattern", "cairo_dlls")
    if os.path.isdir(cairo_dir):
        env["PATH"] = cairo_dir + os.pathsep + env.get("PATH", "")
    return cmd, env, None


@mcp.tool()
def generate_garments(
        count: int,
        garment_type: str = "any",
        name_prefix: str = "generated"
) -> Dict[str, Any]:
    """同步生成（通过 .bat + --json_output_path）。长任务建议用异步。"""
    if not 1 <= count <= 100:
        return {"success": False, "error": "数量必须在1-100之间"}

    timeout_s = int(os.environ.get("GARMENT_TIMEOUT", "1200"))
    json_out = _make_tmp_json_path()
    try:
        cmd, env, err = _build_cmd_and_env(count, garment_type, name_prefix, json_out)
        if err:
            return err
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout_s,
            env=env
        )
        if result.returncode == 0:
            data = _read_json_with_wait(json_out)
            return {
                "success": True,
                "dataset_path": data.get("dataset_path"),
                "generated_count": count,
                "garment_type": garment_type,
                "message": f"成功生成 {count} 件服装",
                "logs": (result.stdout or '').split('\n')[-20:]
            }
        return {
            "success": False,
            "error": (result.stderr or "启动器执行失败"),
            "stdout_tail": (result.stdout or '').split('\n')[-50:],
            "stderr_tail": (result.stderr or '').split('\n')[-50:],
            "exit_code": result.returncode,
            "message": "生成失败"
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"生成超时（超过 {timeout_s} 秒）"}
    except Exception as e:
        return {"success": False, "error": f"意外错误: {str(e)}"}
    finally:
        try:
            if os.path.exists(json_out):
                os.remove(json_out)
        except Exception:
            pass


def _job_worker(job_id: str, count: int, garment_type: str, name_prefix: str):
    with _JOBS_LOCK:
        _JOBS[job_id]["status"] = "running"
        _JOBS[job_id]["started_at"] = time.time()

    json_out = _make_tmp_json_path()
    cmd, env, err = _build_cmd_and_env(count, garment_type, name_prefix, json_out)
    if err:
        with _JOBS_LOCK:
            _JOBS[job_id].update({"status": "failed", "error": err.get("error"), "completed_at": time.time()})
        return

    # 为该任务准备日志文件
    job_dir = os.path.join(_jobs_dir(), job_id)
    os.makedirs(job_dir, exist_ok=True)
    stdout_path = os.path.join(job_dir, 'stdout.log')
    stderr_path = os.path.join(job_dir, 'stderr.log')

    try:
        with open(stdout_path, 'w', encoding='utf-8', errors='replace') as out_f, \
             open(stderr_path, 'w', encoding='utf-8', errors='replace') as err_f:
            proc = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(__file__),
                stdout=out_f,
                stderr=err_f,
                env=env
            )

            start = time.time()
            while True:
                rc = proc.poll()
                now = time.time()
                with _JOBS_LOCK:
                    # 观测信息
                    try:
                        st = os.stat(json_out)
                        _JOBS[job_id]["tmp_json_path"] = json_out
                        _JOBS[job_id]["tmp_json_exists"] = True
                        _JOBS[job_id]["tmp_json_size"] = st.st_size
                        _JOBS[job_id]["tmp_json_mtime"] = st.st_mtime
                    except Exception:
                        _JOBS[job_id]["tmp_json_path"] = json_out
                        _JOBS[job_id]["tmp_json_exists"] = False
                    try:
                        _JOBS[job_id]["stdout_size"] = os.path.getsize(stdout_path)
                        _JOBS[job_id]["stderr_size"] = os.path.getsize(stderr_path)
                    except Exception:
                        pass
                    _JOBS[job_id]["elapsed_sec"] = round(now - start, 2)

                if rc is not None:
                    break
                time.sleep(0.3)

        # 读取尾部日志
        try:
            with open(stdout_path, 'r', encoding='utf-8', errors='replace') as of:
                stdout_tail = of.read().splitlines()[-100:]
        except Exception:
            stdout_tail = []
        try:
            with open(stderr_path, 'r', encoding='utf-8', errors='replace') as ef:
                stderr_tail = ef.read().splitlines()[-100:]
        except Exception:
            stderr_tail = []

        if rc == 0:
            output_data = _read_json_with_wait(json_out, 3.0, 0.1)
            with _JOBS_LOCK:
                _JOBS[job_id].update({
                    "status": "succeeded",
                    "dataset_path": output_data.get("dataset_path"),
                    "stdout_tail": stdout_tail,
                    "stderr_tail": stderr_tail,
                    "completed_at": time.time()
                })
        else:
            with _JOBS_LOCK:
                _JOBS[job_id].update({
                    "status": "failed",
                    "error": f"子进程退出码 {rc}",
                    "stdout_tail": stdout_tail,
                    "stderr_tail": stderr_tail,
                    "exit_code": rc,
                    "completed_at": time.time()
                })
    except Exception as e:
        with _JOBS_LOCK:
            _JOBS[job_id].update({
                "status": "failed",
                "error": f"意外错误: {str(e)}",
                "completed_at": time.time()
            })
    finally:
        try:
            if os.path.exists(json_out):
                os.remove(json_out)
        except Exception:
            pass


@mcp.tool()
def start_generation(count: int, garment_type: str = "any", name_prefix: str = "generated") -> Dict[str, Any]:
    if not 1 <= count <= 100:
        return {"success": False, "error": "数量必须在1-100之间"}
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "status": "queued",
            "params": {"count": count, "garment_type": garment_type, "name_prefix": name_prefix},
            "created_at": time.time()
        }
    t = threading.Thread(target=_job_worker, args=(job_id, count, garment_type, name_prefix), daemon=True)
    t.start()
    return {"success": True, "job_id": job_id, "status": "queued"}


@mcp.tool()
def get_generation(job_id: str) -> Dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return {"success": False, "error": f"未知 job_id: {job_id}"}
        data = dict(job)
        if "started_at" in data and data.get("status") in ("running", "queued"):
            data["elapsed_sec"] = round(time.time() - data.get("started_at", data.get("created_at", time.time())), 2)
    data["success"] = (data.get("status") == "succeeded")
    return data


if __name__ == "__main__":
    mcp.run(transport='stdio')
