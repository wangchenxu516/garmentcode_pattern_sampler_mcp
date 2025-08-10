# garment_mcp_server.py
from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
import subprocess
import os
import re
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 初始化MCP服务器
mcp = FastMCP("garment-generator")

# 配置
PYTHON_PATH = r"D:\miniconda\envs\py39\python.exe"
PROJECT_DIR = r"D:\PythonProjects\garmentcode_project"


import sys




@mcp.tool()
def generate_garments(
        count: int,
        garment_type: str = "any",
        name_prefix: str = "generated"
) -> Dict[str, Any]:
    """
    生成指定数量和类型的服装

    Args:
        count: 生成数量 (1-100)
        garment_type: 类型 ("any" - 目前只支持默认配置)
        name_prefix: 数据集名称前缀
    """
    print(f"🔧 收到请求: count={count}, type={garment_type}")
    if not 1 <= count <= 100:
        return {"success": False, "error": "数量必须在1-100之间"}

    try:
        cmd = [
            PYTHON_PATH, "pattern_sampler.py",
            "--size", str(count),
            "--name", f"{name_prefix}_{garment_type}"
        ]

        env = os.environ.copy()
        env['PYTHONPATH'] = PROJECT_DIR

        result = subprocess.run(
            cmd,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=600,
            env=env  # 🔧 传递环境变量
        )

        if result.returncode == 0:
            dataset_path = extract_dataset_path(result.stdout)

            return {
                "success": True,
                "dataset_path": dataset_path,
                "generated_count": count,
                "garment_type": garment_type,
                "message": f"✅ 成功生成 {count} 件服装",
                "logs": result.stdout.split('\n')[-10:]
            }
        else:
            return {
                "success": False,
                "error": result.stderr,
                "stdout": result.stdout,
                "message": "❌ 生成失败"
            }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "⏰ 生成超时（超过10分钟）"}
    except Exception as e:
        return {"success": False, "error": f"🔥 意外错误: {str(e)}"}



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


if __name__ == "__main__":
    mcp.run(transport='stdio')