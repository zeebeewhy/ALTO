#!/usr/bin/env python3
"""API连通性验证脚本 — 在启动主应用前确认LLM可用。

支持多Provider自动检测：
- Kimi Code API (https://api.kimi.com/coding/v1)
- Moonshot Open Platform (https://api.moonshot.cn/v1)
- OpenAI / DeepSeek / OpenRouter / 任意兼容端点

用法：
    uv run python scripts/test_connection.py
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
    """检查 .env 文件和关键变量（.env 优先于系统环境变量）"""
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env 文件不存在")
        print("   请复制 .env.example 为 .env，并按注释填入你的API Key")
        return None

    # 手动解析 .env 文件，并强制覆盖到 os.environ（.env 优先）
    config = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key_part, val = line.split("=", 1)
            config[key_part] = val.strip().strip('"').strip("'")

    # .env 里的变量强制覆盖系统环境变量，保证读取的是用户显式配置
    for k, v in config.items():
        if v:  # 只覆盖有值的，避免空值覆盖系统变量
            os.environ[k] = v
        elif k in os.environ and os.environ[k]:
            # .env 里显式设为空值，也要覆盖掉系统变量，避免误用
            os.environ[k] = v

    # 使用ALTO的解析逻辑
    from alto.config import _resolve_api_key

    key, base_url, model_name = _resolve_api_key()

    if not key:
        print("❌ 未找到任何API Key配置")
        print("   请检查 .env 中是否设置了以下之一：")
        print("      KIMI_CODE_API_KEY=sk-kimi-...  (Kimi Code订阅)")
        print("      MOONSHOT_API_KEY=sk-...        (Moonshot开放平台)")
        print("      OPENAI_API_KEY=sk-...          (OpenAI/DeepSeek等)")
        return None

    # 检测Provider类型
    provider = "Unknown"
    if base_url == "https://api.kimi.com/coding/v1":
        provider = "Kimi Code API (会员订阅)"
    elif base_url == "https://api.moonshot.cn/v1":
        provider = "Moonshot Open Platform (按量计费)"
    elif "openai" in base_url:
        provider = "OpenAI"
    elif "deepseek" in base_url:
        provider = "DeepSeek"
    elif "openrouter" in base_url:
        provider = "OpenRouter"

    print(f"✅ .env 配置已读取")
    print(f"   Provider: {provider}")
    print(f"   Base URL: {base_url}")
    print(f"   Model:    {model_name}")
    print(f"   Key:      {key[:15]}... ({len(key)}字符)")

    return {"api_key": key, "base_url": base_url, "model": model_name, "provider": provider}


def check_spacy():
    """检查 spaCy 模型是否已下载"""
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        print(f"✅ spaCy 模型 en_core_web_sm 已就绪")
        return True
    except OSError:
        print("❌ spaCy 模型未安装")
        print("   请运行: uv run python -m spacy download en_core_web_sm")
        return False
    except ImportError:
        print("❌ spaCy 未安装")
        print("   请运行: uv add spacy")
        return False


def test_api_connection(cfg):
    """发送一个最小请求到配置好的API端点"""
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
            print(f"❌ API Key 无效，请检查 .env 中的配置")
        elif "Connection" in error_msg or "connect" in error_msg.lower():
            print(f"❌ 网络连接失败: {cfg['base_url']}")
            print("   请检查网络或尝试更换 base_url")
        elif "quota" in error_msg.lower() or "limit" in error_msg.lower() or "exceeded" in error_msg.lower():
            print(f"❌ API 额度已用完或超出限速")
        elif "model" in error_msg.lower() and ("not found" in error_msg.lower() or "does not exist" in error_msg.lower()):
            print(f"❌ 模型名称错误: {cfg['model']}")
            if "kimi-for-coding" in cfg["model"]:
                print("   提示: kimi-for-coding 是 Kimi Code 专用模型ID")
                print("   请确认你使用的是 Kimi Code API (api.kimi.com/coding/v1)")
            elif "kimi" in cfg["model"]:
                print("   可用模型: kimi-latest, kimi-k2.6, kimi-for-coding")
        else:
            print(f"❌ API 请求失败: {error_msg[:120]}")
        return False


def estimate_budget(cfg):
    """基于Provider类型给出额度说明"""
    print(f"\n📊 额度说明:")

    if "Kimi Code" in cfg["provider"]:
        print("   Provider: Kimi Code API (会员订阅额度)")
        print("   - 额度与Kimi会员套餐绑定 (Moderato/Allegretto等)")
        print("   - 每次教学循环约消耗 1,500 tokens")
        print("   - 具体剩余额度请登录 https://www.kimi.com/code/console 查看")
        print("   - 提示: Kimi Code 与 Moonshot 开放平台额度不互通")
    elif "Moonshot" in cfg["provider"]:
        print("   Provider: Moonshot Open Platform (按量计费)")
        print("   - 新用户有免费额度 (~500K tokens/天)")
        print("   - 每次教学循环约消耗 1,500 tokens")
        print("   - 超出免费额度后按量计费")
        print("   - 具体余额请登录 https://platform.moonshot.cn 查看")
    else:
        print(f"   Provider: {cfg['provider']}")
        print("   请参考对应平台的计费说明")


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
