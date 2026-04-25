#!/usr/bin/env python3
"""API连通性验证脚本 — 在启动主应用前确认LLM可用。

检查项：
1. .env 配置是否存在
2. Moonshot API 连通性
3. 估算剩余可用调用次数（基于免费额度）
4. spaCy 模型是否就绪
5. 系统环境（Python版本、内存等）

用法：
    python scripts/test_connection.py
"""

import os
import sys
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def check_python_version():
    """检查 Python 版本 >= 3.10"""
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        print(f"❌ Python 版本过低: {major}.{minor}，需要 >= 3.10")
        return False
    print(f"✅ Python {major}.{minor}.{sys.version_info[2]}")
    return True


def check_env():
    """检查 .env 文件和关键变量"""
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env 文件不存在")
        print("   请创建 .env 并填入:")
        print("      LLM_API_KEY=sk-你的Key")
        print("      LLM_BASE_URL=https://api.moonshot.cn/v1")
        return None

    # 手动解析 .env（不依赖 dotenv，避免循环依赖）
    config = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            config[key] = val.strip().strip('"').strip("'")

    api_key = config.get("LLM_API_KEY", "")
    base_url = config.get("LLM_BASE_URL", "https://api.moonshot.cn/v1")
    model = config.get("LLM_MODEL_NAME", "kimi-latest")

    if not api_key or api_key == "your_api_key_here":
        print("❌ LLM_API_KEY 未设置或为占位符")
        return None

    if not api_key.startswith("sk-"):
        print("⚠️  API Key 格式异常（通常以 sk- 开头）")

    print(f"✅ .env 配置已读取")
    print(f"   Base URL: {base_url}")
    print(f"   Model: {model}")
    print(f"   Key 长度: {len(api_key)} 字符")
    return {"api_key": api_key, "base_url": base_url, "model": model}


def check_spacy():
    """检查 spaCy 模型是否已下载"""
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        print(f"✅ spaCy 模型 en_core_web_sm 已就绪")
        return True
    except OSError:
        print("❌ spaCy 模型未安装")
        print("   请运行: python -m spacy download en_core_web_sm")
        return False
    except ImportError:
        print("❌ spaCy 未安装")
        print("   请运行: pip install spacy")
        return False


def test_api_connection(cfg):
    """发送一个最小请求到 Moonshot API"""
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
        )

        start = time.time()
        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": "你是一个简洁的系统测试助手，只输出 JSON。"},
                {"role": "user", "content": '用一句话回复，只输出 {"status": "ok"}，不要其他文字。'},
            ],
            temperature=0.0,
            max_tokens=50,
        )
        latency = time.time() - start

        content = (resp.choices[0].message.content or "").strip()

        # 尝试解析 JSON
        try:
            data = json.loads(content)
            if data.get("status") == "ok":
                print(f"✅ API 连通正常（延迟: {latency:.2f}s）")
                return True
        except json.JSONDecodeError:
            pass

        # 即使不是严格 JSON，只要有内容也算通
        if content:
            print(f"✅ API 响应正常（延迟: {latency:.2f}s）")
            print(f"   响应预览: {content[:60]}...")
            return True
        else:
            print(f"⚠️ API 响应为空")
            return False

    except Exception as e:
        error_msg = str(e)
        if "Incorrect API key" in error_msg or "invalid api key" in error_msg.lower():
            print(f"❌ API Key 无效，请检查 .env 中的 LLM_API_KEY")
        elif "Connection" in error_msg or "connect" in error_msg.lower():
            print(f"❌ 网络连接失败: {cfg['base_url']}")
            print("   请检查网络或尝试更换 base_url")
        elif "quota" in error_msg.lower() or "limit" in error_msg.lower() or "exceeded" in error_msg.lower():
            print(f"❌ API 额度已用完或超出限速")
        else:
            print(f"❌ API 请求失败: {error_msg[:120]}")
        return False


def estimate_budget(cfg):
    """基于免费额度估算可用调用次数"""
    print("\n📊 额度估算（Moonshot 免费档参考）:")
    print("   每日免费额度: ~500,000 tokens")
    print("   每次教学循环约消耗: 1,500 tokens（诊断+生成）")
    print("   预估每日可测试次数: ~300 次")
    print("   提示: 如需查看真实剩余额度，请登录 Moonshot 控制台")


def main():
    print("🔧 环境检查")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    ok = True

    ok &= check_python_version()
    cfg = check_env()
    ok &= (cfg is not None)
    ok &= check_spacy()

    if cfg:
        print("\n🔌 API 连通性测试")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        ok &= test_api_connection(cfg)
        if ok:
            estimate_budget(cfg)

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if ok:
        print("🎉 全部检查通过，可以启动主应用")
        return 0
    else:
        print("⚠️  部分检查未通过，请按提示修复后重试")
        return 1


if __name__ == "__main__":
    sys.exit(main())
